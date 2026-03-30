from fastapi import APIRouter, HTTPException
from core.database import supabase
from schemas.scheduler import ScheduleCreate, ManualRunRequest
from services.scheduler_service import (
    execute_task,
    _register_schedule,
    unregister_schedule,
)
from services.scheduler_service import _get_task, _get_agent_llm_config_id
from services.task_service import dry_run_task
from services.scheduler_service import record_run
router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


# ── Schedules CRUD ────────────────────────────────────────────────────────────

@router.get("/schedules")
def get_schedules():
    return supabase.table("schedules").select("*").order("created_at", desc=True).execute().data


@router.post("/schedules", status_code=201)
def create_schedule(body: ScheduleCreate):
    data = supabase.table("schedules").insert({
        "task_id": body.task_id,
        "trigger_type": body.trigger_type,
        "interval_seconds": body.interval_seconds,
        "cron_expression": body.cron_expression,
        "watch_path": body.watch_path,
        "watch_table": body.watch_table,
        "prompt": body.prompt,
        "enabled": body.enabled if body.enabled is not None else True,
    }).execute()
    row = data.data[0]
    if row.get("enabled"):
        _register_schedule(row)
    return row


@router.patch("/schedules/{schedule_id}/toggle")
def toggle_schedule(schedule_id: str):
    result = supabase.table("schedules").select("*").eq("id", schedule_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Schedule not found")
    s = result.data[0]
    new_enabled = not s["enabled"]
    supabase.table("schedules").update({"enabled": new_enabled}).eq("id", schedule_id).execute()
    if new_enabled:
        _register_schedule({**s, "enabled": True})
    else:
        unregister_schedule(schedule_id, s["trigger_type"])
    return {"enabled": new_enabled}


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str):
    result = supabase.table("schedules").select("trigger_type").eq("id", schedule_id).execute()
    if result.data:
        unregister_schedule(schedule_id, result.data[0]["trigger_type"])
    supabase.table("schedules").delete().eq("id", schedule_id).execute()


# ── Manual run ────────────────────────────────────────────────────────────────

@router.post("/run")
def manual_run(body: ManualRunRequest):
    """Immediately execute a task and record it in history."""
    task_result = supabase.table("tasks").select("id").eq("id", body.task_id).execute()
    if not task_result.data:
        raise HTTPException(status_code=404, detail="Task not found")
    # Run in foreground so we can return the result
    task = _get_task(body.task_id)
    agent_ids = task.get("agent_ids", [])
    llm_config_id = _get_agent_llm_config_id(agent_ids)
    if not llm_config_id:
        raise HTTPException(status_code=400, detail="No LLM config found on assigned agents")

    prompt = body.prompt or task.get("description", "Run this task.")
    try:
        results = dry_run_task(
            task["name"], task["description"], agent_ids,
            task.get("workflow"), #llm_config_id, 
            prompt,
        )
        record_run(body.task_id, "manual", prompt, "success", results)
        return {"status": "success", "results": results}
    except Exception as e:
        record_run(body.task_id, "manual", prompt, "error", {}, str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history")
def get_history(task_id: str = None, limit: int = 100):
    query = supabase.table("task_runs").select("*, tasks(name)").order("ran_at", desc=True).limit(limit)
    if task_id:
        query = query.eq("task_id", task_id)
    return query.execute().data


@router.get("/history/{run_id}")
def get_run_detail(run_id: str):
    result = supabase.table("task_runs").select("*, tasks(name)").eq("id", run_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Run not found")
    return result.data[0]


@router.delete("/history/{run_id}", status_code=204)
def delete_run(run_id: str):
    supabase.table("task_runs").delete().eq("id", run_id).execute()
