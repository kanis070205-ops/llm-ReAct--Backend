
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from tools.registry import TOOL_REGISTRY, CATEGORY_TOOLS
from pprint import pprint

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

def _build_prefix(agent_row: dict) -> str:
    def _escape(text: str) -> str:
        return text.replace("{", "{{").replace("}", "}}") if text else ""

    name = _escape(agent_row.get("name", "Agent"))
    description = _escape(agent_row.get("description", ""))

    MAX_SKILLS = 1000
    skills = _escape((agent_row.get("skills") or "")[:MAX_SKILLS])

    return (
    f"You are {name}.\n"
    f"{description}\n\n"
    f"Your skills include: {skills}\n\n"

    "STRICT RULES:\n"
    "- Maximum 2 tool calls\n"
    "- Never repeat the same tool\n"
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
def build_agent_executor(agent_row: dict, llm_cfg: dict):
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
        agent_kwargs={"prefix": _build_prefix(agent_row)},
        handle_parsing_errors=True,
        max_iterations=3,
        early_stopping_method="force",
        return_intermediate_steps=True,
    )


def run_agent(agent_row: dict, llm_cfg: dict, prompt: str) -> str:
    """Run the agent and return the final output string."""
    executor = build_agent_executor(agent_row, llm_cfg)

    result = executor.invoke({"input": prompt})
    output = result.get("output", "").strip()

    # If LLM got stuck and returned empty output, grab the last tool observation
    if not output or output in ("", "Agent stopped due to iteration limit or time limit."):
        steps = result.get("intermediate_steps", [])
        if steps:
            last_observation = steps[-1][1]  # (AgentAction, observation)
            return str(last_observation).strip()

    return output

