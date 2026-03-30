from core.database import supabase
from services.llm_service import get_llm_config
from services.agent_service import run_agent, run_final_agent

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

def dry_run_task(task_name: str, task_description: str, agent_ids: list[str], workflow: str | None, prompt: str) -> dict:
    """
    Orchestrated multi-agent pipeline:
    - First agent gets the raw prompt.
    - Intermediate agents get prior context and are told NOT to redo prior work.
    - Last agent runs as a pure LLM call (no tools) to synthesize/report.
    """
    results = {}
    context_so_far = ""
    total = len(agent_ids)

    for i, agent_id in enumerate(agent_ids):
        is_first = i == 0
        is_last = i == total - 1

        agent_result = supabase.table("agents").select("*").eq("id", agent_id).execute()
        if not agent_result.data:
            results[agent_id] = "Agent not found"
            continue

        agent_row = agent_result.data[0]
        cfg = get_llm_config(agent_row["llm_config_id"])

        # Build role hint so the agent knows its position in the pipeline
        if total == 1:
            role_hint = ""
        elif is_first:
            role_hint = (
                "You are the FIRST agent in this pipeline. "
                "Gather or process the data needed for the task. "
                "Do not write a final report — just produce your findings."
            )
        elif is_last:
            role_hint = ""  # not used — last agent bypasses ReAct
        else:
            role_hint = (
                f"You are agent {i + 1} of {total} in this pipeline. "
                "Previous agents have already done some work (see context below). "
                "Build on their outputs — do NOT repeat searches or work already done. "
                "Focus only on what your role adds."
            )

        # Build the enriched prompt
        if is_first or not context_so_far:
            enriched_prompt = f"Task: {task_name}\n{prompt}"
        else:
            enriched_prompt = (
                f"Task: {task_name}\n"
                f"Original request: {prompt}\n\n"
                f"--- Context from previous agents ---\n{context_so_far}\n"
                f"--- End of context ---\n\n"
                f"Based on the above context, perform your specific role. "
                f"Do NOT repeat any work already done above."
            )

        try:
            # Last agent: pure LLM synthesis, no tools
            if is_last and total > 1:
                synthesis_prompt = (
                    f"Task: {task_name}\n"
                    f"Original request: {prompt}\n\n"
                    f"--- Outputs from all previous agents ---\n{context_so_far}\n"
                    f"--- End of outputs ---\n\n"
                    f"Write a complete, well-structured final response based on the above."
                )
                output = run_final_agent(agent_row, cfg, synthesis_prompt)
            else:
                output = run_agent(agent_row, cfg, enriched_prompt, role_hint)

            results[agent_row["name"]] = output
            context_so_far += f"\n[{agent_row['name']}]: {output}"
        except Exception as e:
            error_msg = f"Error: {e}"
            results[agent_row["name"]] = error_msg
            context_so_far += f"\n[{agent_row['name']}]: {error_msg}"

    return results
