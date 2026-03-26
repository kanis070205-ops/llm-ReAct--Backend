from core.database import supabase
from services.llm_service import get_llm_config
from services.agent_service import run_agent


def generate_workflow(task_name: str, task_description: str, agent_names: list[str], llm_config_id: str) -> str:
    """Ask the LLM to suggest a workflow for the task given the assigned agents."""
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic

    cfg = get_llm_config(llm_config_id)
    provider = cfg["provider"].lower()

    agents_str = ", ".join(agent_names) if agent_names else "no agents"
    prompt = (
        f"You are a workflow planner.\n"
        f"Task: {task_name}\n"
        f"Description: {task_description}\n"
        f"Assigned agents: {agents_str}\n\n"
        f"Suggest a concise step-by-step workflow for how these agents should collaborate to complete this task. "
        f"Be specific and practical. Return only the workflow steps, numbered."
    )

    if provider == "anthropic":
        llm = ChatAnthropic(model=cfg["model"], anthropic_api_key=cfg["api_key"], temperature=0)
    else:
        llm = ChatOpenAI(
            model=cfg["model"],
            openai_api_key=cfg["api_key"],
            openai_api_base=cfg["api_url"].rstrip("/"),
            temperature=0,
        )

    result = llm.invoke(prompt)
    return result.content


def dry_run_task(task_name: str, task_description: str, agent_ids: list[str], workflow: str | None, llm_config_id: str, prompt: str) -> dict:
    """Run the task prompt through each assigned agent and collect outputs."""
    results = {}
    for agent_id in agent_ids:
        agent_result = supabase.table("agents").select("*").eq("id", agent_id).execute()
        if not agent_result.data:
            results[agent_id] = "Agent not found"
            continue
        agent_row = agent_result.data[0]
        cfg = get_llm_config(agent_row["llm_config_id"])
        try:
            output = run_agent(agent_row, cfg, prompt)
            results[agent_row["name"]] = output
        except Exception as e:
            results[agent_row["name"]] = f"Error: {e}"
    return results
