from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class ScheduleCreate(BaseModel):
    task_id: str
    trigger_type: Literal["manual", "interval", "cron", "file_watch", "db_watch"]
    # interval: run every N seconds/minutes/hours
    interval_seconds: Optional[int] = None
    # cron: standard cron expression e.g. "0 9 * * 1-5"
    cron_expression: Optional[str] = None
    # file_watch: path inside workspace to watch
    watch_path: Optional[str] = None
    # db_watch: supabase table to watch for changes
    watch_table: Optional[str] = None
    # prompt to pass to agents when triggered
    prompt: Optional[str] = None
    enabled: Optional[bool] = True


class ScheduleRead(BaseModel):
    id: str
    task_id: str
    trigger_type: str
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None
    watch_path: Optional[str] = None
    watch_table: Optional[str] = None
    prompt: Optional[str] = None
    enabled: bool
    created_at: Optional[str] = None


class ManualRunRequest(BaseModel):
    task_id: str
    prompt: Optional[str] = None
