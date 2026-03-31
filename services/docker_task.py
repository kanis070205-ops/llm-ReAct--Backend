"""
Builds the container payload from live Supabase data and launches the Docker container.
The LLM config is always fetched fresh from DB — nothing is hardcoded.
"""
from core.docker_manager import run_task_container
from services.llm_service import get_llm_config


def execute_task(prompt: str, agent_row: dict, llm_config_id: str) -> dict:
    """
    Fetch LLM config from Supabase, build input.json payload, run container.

    agent_row: full agent record from DB (name, description, skills, tools, llm_config_id)
    llm_config_id: ID of the llm_configs row to use
    """
    llm_cfg = get_llm_config(llm_config_id)

    # Validate required LLM fields before sending to container
    missing = [f for f in ("provider", "api_key", "model") if not llm_cfg.get(f)]
    if missing:
        raise ValueError(f"LLM config (id={llm_config_id}) is missing fields: {missing}")

    # Build system prompt from agent's DB fields
    name        = agent_row.get("name", "Agent")
    description = agent_row.get("description", "")
    skills      = agent_row.get("skills", "")
    system_prompt = f"You are {name}.\n{description}"
    if skills:
        system_prompt += f"\nYour skills include: {skills}"

    # tools is stored as a list of names in the DB
    tools = agent_row.get("tools") or []

    payload = {
        "prompt": prompt,
        "agent": {
            "system_prompt": system_prompt,
            "tools": tools,
        },
        "llm": {
            "provider": llm_cfg["provider"],
            "api_url":  llm_cfg.get("api_url") or "",   # container maps "" → provider default
            "api_key":  llm_cfg["api_key"],
            "model":    llm_cfg["model"],
        },
    }

    # Log what's being sent (key redacted)
    print(
        f"[docker_task] agent={name!r} "
        f"provider={llm_cfg['provider']!r} "
        f"model={llm_cfg['model']!r} "
        f"api_url={llm_cfg.get('api_url') or '(provider default)'!r} "
        f"tools={tools}"
    )

    return run_task_container(payload)
