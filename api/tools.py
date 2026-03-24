from fastapi import APIRouter
from schemas.tool import ToolRead
from tools.registry import TOOL_REGISTRY
from core.database import supabase

router = APIRouter(prefix="", tags=["Tools"])


# ── List Available Tools ───────────────────────────

@router.get("/tools", response_model=list[ToolRead])
def list_tools():
    return [
        {
            "name": name,
            "description": tool.description
        }
        for name, tool in TOOL_REGISTRY.items()
    ]


# ── Assign Tools to Agent ──────────────────────────

@router.post("/agents/{agent_id}/tools")
def assign_tools(agent_id: str, tools: list[str]):

    supabase.table("agents").update({
        "tools": tools
    }).eq("id", agent_id).execute()

    return {"message": "Tools assigned successfully"}