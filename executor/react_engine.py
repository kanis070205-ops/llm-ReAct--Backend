"""
ReAct engine — runs entirely inside the container.
Flow: Thought → Action → Observation → ... → Final Answer
LLM is called via raw HTTP (OpenAI-compatible or Anthropic).
"""

import re
import requests
from tools.registry import TOOLS, describe_tools

MAX_ITERATIONS = 6

SYSTEM_TEMPLATE = """\
You are a helpful AI agent. Solve the task using the ReAct pattern.

Available tools:
{tool_descriptions}

Strictly follow this format for EVERY response:
Thought: <your reasoning>
Action: <tool_name>
Action Input: <tool input>

When you have enough information to answer, respond ONLY with:
Thought: I now know the final answer.
Final Answer: <your answer>

Rules:
- Only use tools listed above.
- Never fabricate tool outputs.
- Stop as soon as you have a Final Answer.
"""


# ---------------- LLM CALL ---------------- #

def _call_llm(messages: list[dict], llm_cfg: dict) -> str:
    provider = llm_cfg.get("provider", "").lower().strip()

    if provider == "anthropic":
        return _call_anthropic(messages, llm_cfg)

    # Provider defaults
    PROVIDER_DEFAULTS = {
        "openai": "https://api.openai.com/v1",
        "groq": "https://api.groq.com/openai/v1",
        "ollama": "http://localhost:11434/v1",
    }

    api_url = (llm_cfg.get("api_url") or "").strip().rstrip("/")
    if not api_url:
        api_url = PROVIDER_DEFAULTS.get(provider)

    if not api_url:
        raise ValueError(f"No api_url configured for provider '{provider}'")

    api_key = llm_cfg.get("api_key")
    if not api_key:
        raise ValueError("Missing API key for LLM")

    # Base payload
    payload = {
        "model": llm_cfg["model"],
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024,
    }

    # Only OpenAI supports stop properly
    if provider == "openai":
        payload["stop"] = ["Observation:"]

    print(f"[ReAct] calling {provider} → {api_url}")
    print(f"[DEBUG] Payload: {payload}")

    resp = requests.post(
        f"{api_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=60,
    )

    # Debug response if failure
    if not resp.ok:
        print("[ERROR] Response:", resp.text)

    resp.raise_for_status()

    return resp.json()["choices"][0]["message"]["content"].strip()


# ---------------- ANTHROPIC ---------------- #

def _call_anthropic(messages: list[dict], llm_cfg: dict) -> str:
    api_key = llm_cfg.get("api_key")
    if not api_key:
        raise ValueError("Missing API key for Anthropic")

    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    human_msgs = [m for m in messages if m["role"] != "system"]

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": llm_cfg["model"],
            "system": system,
            "messages": human_msgs,
            "temperature": 0,
            "max_tokens": 1024,
            "stop_sequences": ["Observation:"],
        },
        timeout=60,
    )

    if not resp.ok:
        print("[ERROR] Anthropic Response:", resp.text)

    resp.raise_for_status()

    return resp.json()["content"][0]["text"].strip()


# ---------------- PARSING ---------------- #

def _parse_action(text: str):
    action = re.search(r"Action:\s*(.+)", text)
    action_input = re.search(r"Action Input:\s*(.+)", text, re.DOTALL)
    if action and action_input:
        return action.group(1).strip(), action_input.group(1).strip()
    return None, None


def _parse_final_answer(text: str):
    match = re.search(r"Final Answer:\s*(.+)", text, re.DOTALL)
    return match.group(1).strip() if match else None


def _extract_thought(text: str) -> str:
    match = re.search(r"Thought:\s*(.+?)(?:\nAction:|$)", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


# ---------------- MAIN ENGINE ---------------- #

def run_react(data: dict) -> dict:
    prompt = data["prompt"]
    agent_cfg = data.get("agent", {})
    llm_cfg = data["llm"]

    tool_names = agent_cfg.get("tools", [])
    extra_system = agent_cfg.get("system_prompt", "")

    print(
        f"[ReAct] provider={llm_cfg.get('provider')} "
        f"model={llm_cfg.get('model')} "
        f"api_url={llm_cfg.get('api_url') or '(default)'}"
    )

    system_content = SYSTEM_TEMPLATE.format(
        tool_descriptions=describe_tools(tool_names)
    )

    if extra_system:
        system_content += f"\nAdditional instructions: {extra_system}"

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Task: {prompt}"},
    ]

    steps = []
    final_answer = None

    for _ in range(MAX_ITERATIONS):
        llm_output = _call_llm(messages, llm_cfg)
        messages.append({"role": "assistant", "content": llm_output})

        print("[ReAct] LLM Output:", llm_output)

        final_answer = _parse_final_answer(llm_output)
        if final_answer:
            break

        action, action_input = _parse_action(llm_output)

        if not action:
            final_answer = llm_output
            break

        fn = TOOLS.get(action)

        if fn:
            try:
                observation = fn(action_input)
            except Exception as e:
                observation = f"Tool error: {e}"
        else:
            observation = f"Unknown tool '{action}'. Available: {', '.join(tool_names)}"

        steps.append({
            "thought": _extract_thought(llm_output),
            "action": action,
            "action_input": action_input,
            "observation": observation,
        })

        messages.append({"role": "user", "content": f"Observation: {observation}"})

    if not final_answer:
        final_answer = steps[-1]["observation"] if steps else "No answer produced."

    return {"steps": steps, "final_answer": final_answer}