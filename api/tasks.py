from fastapi import APIRouter, HTTPException
from core.database import supabase
from schemas.task import TaskCreate, WorkflowRequest, TaskDryRunRequest
from services.task_service import generate_workflow, dry_run_task

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
    }).execute()
    return data.data[0]


@router.get("/check-name")
def check_task_name(name: str):
    data = supabase.table("tasks").select("id").eq("name", name).execute()
    return {"exists": len(data.data) > 0}


@router.post("/generate-workflow")
def get_workflow(req: WorkflowRequest):
    """Ask the LLM to generate a workflow for the task."""
    # Fetch agent names for context
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


@router.post("/dry-run")
def task_dry_run(req: TaskDryRunRequest):
    """Run the task prompt through all assigned agents."""
    if not req.agent_ids:
        raise HTTPException(status_code=400, detail="No agents assigned to this task.")
    try:
        results = dry_run_task(
            req.task_name,
            req.task_description,
            req.agent_ids,
            req.workflow,
            req.llm_config_id,
            req.prompt,
        )
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dry run failed: {e}")


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str):
    supabase.table("tasks").delete().eq("id", task_id).execute()
