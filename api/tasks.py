from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.database import supabase
from schemas.task import TaskCreate, TaskUpdate, WorkflowRequest, TaskDryRunRequest
from services.task_service import generate_workflow
from services.docker_task import execute_task as docker_execute

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("")
def get_tasks():
    return supabase.table("tasks").select("*").execute().data


@router.post("", status_code=201)
def create_task(task: TaskCreate):
    data = supabase.table("tasks").insert({
        "name": task.name,
        "description": task.description,
        "agent_ids": task.agent_ids,
        "workflow": task.workflow,
        "enabled": task.enabled if task.enabled is not None else True,
    }).execute()
    return data.data[0]


@router.get("/check-name")
def check_task_name(name: str):
    data = supabase.table("tasks").select("id").eq("name", name).execute()
    return {"exists": len(data.data) > 0}


@router.post("/generate-workflow")
def get_workflow(req: WorkflowRequest):
    agent_names = []
    for agent_id in req.agent_ids:
        result = supabase.table("agents").select("name").eq("id", agent_id).execute()
        if result.data:
            agent_names.append(result.data[0]["name"])
    try:
        workflow = generate_workflow(req.task_name, req.task_description, agent_names, req.llm_config_id)
        return {"workflow": workflow}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow generation failed: {e}")


def _get_first_agent(agent_ids: list) -> dict:
    """Fetch the first agent from DB or raise."""
    if not agent_ids:
        raise HTTPException(status_code=400, detail="No agents assigned.")
    res = supabase.table("agents").select("*").eq("id", agent_ids[0]).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return res.data[0]


@router.post("/dry-run")
def task_dry_run(req: TaskDryRunRequest):
    """Run the task prompt through Docker container (ReAct loop)."""
    agent = _get_first_agent(req.agent_ids)
    try:
        result = docker_execute(
            prompt=req.prompt,
            agent_row=agent,
            llm_config_id=agent["llm_config_id"],
        )
        return {"results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Docker run failed: {e}")


@router.post("/run-task")
def run_task(req: TaskDryRunRequest):
    """Run a saved task by task_id through Docker."""
    task_res = supabase.table("tasks").select("*").eq("id", req.task_name).execute()
    if not task_res.data:
        raise HTTPException(status_code=404, detail="Task not found.")
    task = task_res.data[0]
    agent = _get_first_agent(task.get("agent_ids") or [])
    try:
        result = docker_execute(
            prompt=req.prompt,
            agent_row=agent,
            llm_config_id=agent["llm_config_id"],
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Container execution failed: {e}")


@router.patch("/{task_id}/toggle")
def toggle_task(task_id: str):
    result = supabase.table("tasks").select("enabled").eq("id", task_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Task not found.")
    current = result.data[0].get("enabled", True)
    updated = supabase.table("tasks").update({"enabled": not current}).eq("id", task_id).execute()
    return updated.data[0]


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str):
    supabase.table("tasks").delete().eq("id", task_id).execute()


@router.patch("/{task_id}")
def update_task(task_id: str, updates: TaskUpdate):
    payload = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update.")
    result = supabase.table("tasks").update(payload).eq("id", task_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Task not found.")
    return result.data[0]
