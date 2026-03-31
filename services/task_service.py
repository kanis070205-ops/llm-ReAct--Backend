from services.llm_service import get_llm_config


def generate_workflow(task_name: str, task_description: str, agent_names: list[str], llm_config_id: str) -> str:
    """Ask the LLM to suggest a workflow for the task given the assigned agents."""
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic

    cfg = get_llm_config(llm_config_id)
    provider = cfg["provider"].lower()

    agents_str = ", ".join(agent_names) if agent_names else "no agents"
    prompt = (
        f"You are a workflow planner.\n"
        f"Task: {task_name}\nDescription: {task_description}\n"
        f"Assigned agents: {agents_str}\n\n"
        f"Suggest a concise step-by-step workflow. Return only numbered steps."
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

    return llm.invoke(prompt).content
