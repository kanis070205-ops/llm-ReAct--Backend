"""
Scheduler service — APScheduler + task execution + history recording.
"""
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from core.database import supabase
from services.docker_task import execute_task as docker_execute

scheduler = BackgroundScheduler(timezone="UTC")
_file_watchers: dict[str, threading.Thread] = {}
_file_watcher_stop: dict[str, threading.Event] = {}


def _get_task(task_id: str) -> Optional[dict]:
    result = supabase.table("tasks").select("*").eq("id", task_id).execute()
    return result.data[0] if result.data else None


def record_run(task_id: str, trigger_type: str, prompt: str, status: str, output: dict, error: str = None):
    """Insert a task_runs row into Supabase."""
    supabase.table("task_runs").insert({
        "task_id": task_id,
        "trigger_type": trigger_type,
        "prompt": prompt or "",
        "status": status,
        "output": output or {},
        "error": error or "",
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def execute_task(task_id: str, trigger_type: str, prompt: str = ""):
    """Run a task inside a Docker container and record the result."""
    task = _get_task(task_id)
    if not task:
        record_run(task_id, trigger_type, prompt, "error", {}, "Task not found")
        return

    agent_ids = task.get("agent_ids", [])
    if not agent_ids:
        record_run(task_id, trigger_type, prompt, "error", {}, "No agents assigned")
        return

    # Load first agent
    agent_res = supabase.table("agents").select("*").eq("id", agent_ids[0]).execute()
    if not agent_res.data:
        record_run(task_id, trigger_type, prompt, "error", {}, "Agent not found")
        return
    agent = agent_res.data[0]

    effective_prompt = prompt or task.get("description", "Run this task.")

    try:
        result = docker_execute(
            prompt=effective_prompt,
            agent_row=agent,
            llm_config_id=agent["llm_config_id"],
        )
        record_run(task_id, trigger_type, effective_prompt, "success", result)
    except Exception as e:
        record_run(task_id, trigger_type, effective_prompt, "error", {}, str(e))


# ── File watcher ──────────────────────────────────────────────────────────────

def _watch_file(schedule_id: str, task_id: str, watch_path: str, prompt: str, stop_event: threading.Event):
    """Poll a file's mtime and trigger task on change."""
    BASE_DIR = os.path.join(os.getcwd(), "workspace")
    full_path = os.path.abspath(os.path.join(BASE_DIR, watch_path))
    last_mtime = None
    while not stop_event.is_set():
        try:
            if os.path.exists(full_path):
                mtime = os.path.getmtime(full_path)
                if last_mtime is not None and mtime != last_mtime:
                    execute_task(task_id, "file_watch", prompt or f"File changed: {watch_path}")
                last_mtime = mtime
        except Exception:
            pass
        stop_event.wait(5)  # poll every 5 seconds


def start_file_watcher(schedule_id: str, task_id: str, watch_path: str, prompt: str):
    stop_event = threading.Event()
    t = threading.Thread(
        target=_watch_file,
        args=(schedule_id, task_id, watch_path, prompt, stop_event),
        daemon=True,
    )
    _file_watcher_stop[schedule_id] = stop_event
    _file_watchers[schedule_id] = t
    t.start()


def stop_file_watcher(schedule_id: str):
    if schedule_id in _file_watcher_stop:
        _file_watcher_stop[schedule_id].set()
        del _file_watcher_stop[schedule_id]
    _file_watchers.pop(schedule_id, None)


# ── DB watcher ────────────────────────────────────────────────────────────────

def _watch_db(schedule_id: str, task_id: str, watch_table: str, prompt: str, stop_event: threading.Event):
    """Poll a Supabase table row count and trigger on change."""
    last_count = None
    while not stop_event.is_set():
        try:
            result = supabase.table(watch_table).select("id", count="exact").execute()
            count = result.count if hasattr(result, "count") else len(result.data)
            if last_count is not None and count != last_count:
                execute_task(task_id, "db_watch", prompt or f"DB table '{watch_table}' changed")
            last_count = count
        except Exception:
            pass
        stop_event.wait(10)  # poll every 10 seconds


def start_db_watcher(schedule_id: str, task_id: str, watch_table: str, prompt: str):
    stop_event = threading.Event()
    t = threading.Thread(
        target=_watch_db,
        args=(schedule_id, task_id, watch_table, prompt, stop_event),
        daemon=True,
    )
    _file_watcher_stop[schedule_id] = stop_event
    _file_watchers[schedule_id] = t
    t.start()


def stop_db_watcher(schedule_id: str):
    stop_file_watcher(schedule_id)  # same dict


# ── Schedule management ───────────────────────────────────────────────────────

def load_schedules():
    """Load all enabled schedules from DB and register them."""
    result = supabase.table("schedules").select("*").eq("enabled", True).execute()
    for s in result.data:
        _register_schedule(s)


def _register_schedule(s: dict):
    sid = s["id"]
    task_id = s["task_id"]
    prompt = s.get("prompt") or ""
    trigger_type = s["trigger_type"]

    if trigger_type == "interval" and s.get("interval_seconds"):
        scheduler.add_job(
            execute_task,
            trigger=IntervalTrigger(seconds=s["interval_seconds"]),
            args=[task_id, "interval", prompt],
            id=sid,
            replace_existing=True,
        )
    elif trigger_type == "cron" and s.get("cron_expression"):
        parts = s["cron_expression"].split()
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
            scheduler.add_job(
                execute_task,
                trigger=CronTrigger(
                    minute=minute, hour=hour, day=day,
                    month=month, day_of_week=day_of_week
                ),
                args=[task_id, "cron", prompt],
                id=sid,
                replace_existing=True,
            )
    elif trigger_type == "file_watch" and s.get("watch_path"):
        start_file_watcher(sid, task_id, s["watch_path"], prompt)
    elif trigger_type == "db_watch" and s.get("watch_table"):
        start_db_watcher(sid, task_id, s["watch_table"], prompt)


def unregister_schedule(schedule_id: str, trigger_type: str):
    if trigger_type in ("interval", "cron"):
        try:
            scheduler.remove_job(schedule_id)
        except Exception:
            pass
    elif trigger_type in ("file_watch", "db_watch"):
        stop_file_watcher(schedule_id)


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
    load_schedules()
