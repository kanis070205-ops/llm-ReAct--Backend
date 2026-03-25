from fastapi import APIRouter, HTTPException
from core.database import supabase
from schemas.agent import AgentCreate, DryRunRequest, RunAgentRequest
from services.llm_service import get_llm_config
from services.agent_service import run_agent

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", status_code=201)
def create_agent(agent: AgentCreate):
    data = supabase.table("agents").insert({
        "name": agent.name,
        "description": agent.description,
        "category": agent.category,
        "skills": agent.skills,
        "llm_config_id": agent.llm_config_id,
        "tools": agent.tools or [],
    }).execute()
    return data.data[0]


@router.get("")
def get_agents():
    return supabase.table("agents").select("*").execute().data


@router.get("/check-name")
def check_name(name: str):
    data = supabase.table("agents").select("id").eq("name", name).execute()
    return {"exists": len(data.data) > 0}


@router.post("/dry-run")
def dry_run(req: DryRunRequest):
    """
    Test the agent with real tools before saving.
    Builds a temporary agent row from the form fields and runs it
    through the same LangChain ReAct executor as /run.
    """
    llm_cfg = get_llm_config(req.llm_config_id)

    # Construct a temporary agent row — same shape as a DB row
    temp_agent = {
        "name": "Preview Agent",
        "description": req.description,
        "category": req.category,
        "skills": req.skills,
        "tools": req.tools or [],
    }
    
    try:
        output = run_agent(temp_agent, llm_cfg, req.prompt)
        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dry run error: {e}")


@router.post("/run")
def run_saved_agent(req: RunAgentRequest):
    """Run a saved agent with LangChain ReAct + tools."""
    agent_result = supabase.table("agents").select("*").eq("id", req.agent_id).execute()
    if not agent_result.data:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent_row = agent_result.data[0]
    llm_cfg = get_llm_config(agent_row["llm_config_id"])

    try:
        output = run_agent(agent_row, llm_cfg, req.prompt)
        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {e}")
