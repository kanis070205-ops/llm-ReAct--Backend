
import os
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from tools.registry import TOOL_REGISTRY, CATEGORY_TOOLS

def _build_llm(cfg: dict):
    """Instantiate the correct LangChain chat model from a decrypted config row."""
    provider = cfg["provider"].lower()
    if provider == "anthropic":
        return ChatAnthropic(
            model=cfg["model"],
            anthropic_api_key=cfg["api_key"],
            temperature=0,
        )
    # OpenAI-compatible: openai, groq, ollama, azure
    return ChatOpenAI(
        model=cfg["model"],
        openai_api_key=cfg["api_key"],
        openai_api_base=cfg["api_url"].rstrip("/"),
        temperature=0,
    )

def _build_prefix(agent_row: dict, role_hint: str = "") -> str:
    def _escape(text: str) -> str:
        return text.replace("{", "{{").replace("}", "}}") if text else ""

    name = _escape(agent_row.get("name", "Agent"))
    description = _escape(agent_row.get("description", ""))

    MAX_SKILLS = 1000
    skills = _escape((agent_row.get("skills") or "")[:MAX_SKILLS])

    role_section = f"\n{_escape(role_hint)}\n" if role_hint else ""

    return (
        f"You are {name}.\n"
        f"{description}\n\n"
        f"Your skills include: {skills}\n"
        f"{role_section}\n"
        "STRICT RULES:\n"
        "- Maximum 2 tool calls\n"
        "- Never repeat the same tool\n"
        "- If previous agents already gathered the data you need, use it directly — do NOT search again\n"
        "- If you get useful data → STOP immediately\n"
        "- ALWAYS produce Final Answer after first successful tool call\n"
        "- Do NOT continue thinking after getting the answer\n\n"
        "FORMAT:\n"
        "Question: {input}\n"
        "Thought: ...\n"
        "Action: tool_name\n"
        "Action Input: ...\n"
        "Observation: ...\n"
        "Thought: ...\n"
        "Final Answer: <answer>\n"
    )
def build_agent_executor(agent_row: dict, llm_cfg: dict, role_hint: str = ""):
    """
    Build a LangChain ReAct agent executor wired with the correct tools
    for the agent's category. Shared by both dry-run and run endpoints.
    """
    llm = _build_llm(llm_cfg)
    category = agent_row.get("category", "")
    tool_names = agent_row.get("tools")
    # If tools is explicitly set (even empty list), use it; otherwise fall back to category defaults
    if tool_names is not None:
        tools = [TOOL_REGISTRY[name] for name in tool_names if name in TOOL_REGISTRY]
    else:
        tools = CATEGORY_TOOLS.get(category, list(TOOL_REGISTRY.values()))
    print("Agent:", agent_row.get("name"))
    print("Assigned tool names:", tool_names)
    print("Loaded tool objects:", [t.name for t in tools])
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        agent_kwargs={"prefix": _build_prefix(agent_row, role_hint)},
        handle_parsing_errors=True,
        max_iterations=3,
        early_stopping_method="force",
        return_intermediate_steps=True,
    )


def run_agent(agent_row: dict, llm_cfg: dict, prompt: str, role_hint: str = "") -> str:
    """Run the agent and return the final output string."""
    # Expose LLM config as env vars so code_generator tool can use the same provider
    os.environ["CODE_GEN_PROVIDER"] = llm_cfg.get("provider", "openai")
    os.environ["CODE_GEN_API_KEY"]  = llm_cfg.get("api_key", "")
    os.environ["CODE_GEN_API_URL"]  = llm_cfg.get("api_url", "")
    os.environ["CODE_GEN_MODEL"]    = llm_cfg.get("model", "gpt-4o-mini")

    executor = build_agent_executor(agent_row, llm_cfg, role_hint)

    result = executor.invoke({"input": prompt})
    output = result.get("output", "").strip()

    # If LLM got stuck and returned empty output, grab the last tool observation
    if not output or output in ("", "Agent stopped due to iteration limit or time limit."):
        steps = result.get("intermediate_steps", [])
        if steps:
            last_observation = steps[-1][1]  # (AgentAction, observation)
            return str(last_observation).strip()

    return output


def run_final_agent(agent_row: dict, llm_cfg: dict, prompt: str) -> str:
    """
    Run the last agent in a pipeline as a pure LLM call — no tools.
    Used when the agent's job is to synthesize/report on prior outputs,
    not to gather new data.
    """
    llm = _build_llm(llm_cfg)
    name = agent_row.get("name", "Agent")
    description = agent_row.get("description", "")
    skills = (agent_row.get("skills") or "")

    system = (
        f"You are {name}.\n"
        f"{description}\n\n"
        f"Your skills include: {skills}\n\n"
        "You are the final agent in a pipeline. Previous agents have already gathered all necessary data.\n"
        "Your job is ONLY to synthesize, summarize, or report on the provided context.\n"
        "Do NOT use any tools. Do NOT search for new information.\n"
        "Write a clear, well-structured final answer based solely on the context given."
    )

    from langchain_core.messages import SystemMessage, HumanMessage
    result = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
    return result.content.strip()

