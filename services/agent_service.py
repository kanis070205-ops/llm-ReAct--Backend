"""
Agent Service — builds and runs a LangChain ReAct agent with real tools.
Both dry-run and run go through the same agent executor so tools are
always active — the only difference is dry-run doesn't persist the agent.
"""
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


def _build_prefix(agent_row: dict) -> str:
    """Build the ReAct system prefix from the agent's DB fields."""
    skills_block = f"\nSkills: {agent_row['skills']}" if agent_row.get("skills") else ""
    return (
        f"You are {agent_row['name']}, an AI agent.\n"
        f"Description: {agent_row.get('description', '')}{skills_block}\n\n"
        "You have access to tools. Use them whenever they help answer the request.\n"
        "Think step by step using Thought / Action / Action Input / Observation.\n"
        "When you have enough information, respond with Final Answer."
    )


def build_agent_executor(agent_row: dict, llm_cfg: dict):
    """
    Build a LangChain ReAct agent executor wired with the correct tools
    for the agent's category. Shared by both dry-run and run endpoints.
    """
    llm = _build_llm(llm_cfg)
    category = agent_row.get("category", "")
    tool_names = agent_row.get("tools")
    # fall back to all tools if category not mapped
    if tool_names:
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
        max_iterations=6,
    )


def run_agent(agent_row: dict, llm_cfg: dict, prompt: str) -> str:
    """Run the agent and return the final output string."""
    executor = build_agent_executor(agent_row, llm_cfg)
    result = executor.invoke({"input": prompt})
    return result.get("output", str(result))
