from pydantic import BaseModel
from typing import Optional, List


class TaskCreate(BaseModel):
    name: str
    description: str
    agent_ids: List[str]
    workflow: Optional[str] = None
    enabled: Optional[bool] = True


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    agent_ids: Optional[List[str]] = None
    workflow: Optional[str] = None
    enabled: Optional[bool] = None


class TaskRead(BaseModel):
    id: str
    name: str
    description: str
    agent_ids: List[str]
    workflow: Optional[str] = None


class WorkflowRequest(BaseModel):
    task_name: str
    task_description: str
    agent_ids: List[str]
    llm_config_id: str


class TaskDryRunRequest(BaseModel):
    task_name: str
    task_description: str
    agent_ids: List[str]
    workflow: Optional[str] = None
    prompt: str
