from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from client import supabase
from schemas import LLMConfig, AgentSchema, DryRunSchema
from crypto import encrypt, decrypt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── LLM Config ──────────────────────────────────────────────

@app.post("/llm-config")
def save_config(config: LLMConfig):
    encrypted_key = encrypt(config.api_key)
    data = supabase.table("llm_configs").insert({
        "provider": config.provider,
        "api_url": config.api_url,
        "api_key": encrypted_key,
        "model": config.model,
    }).execute()
    return {"message": "Saved", "data": data.data[0] if data.data else {}}


@app.get("/llm-config")
def get_configs():
    # never return api_key to frontend
    data = supabase.table("llm_configs").select("id, provider, api_url, model").execute()
    return data.data


# ── Agents ───────────────────────────────────────────────────

@app.post("/agents")
def create_agent(agent: AgentSchema):
    data = supabase.table("agents").insert({
        "name": agent.name,
        "description": agent.description,
        "category": agent.category,
        "skills": agent.skills,
        "llm_config_id": agent.llm_config_id,
    }).execute()
    return data.data[0]


@app.get("/agents")
def get_agents():
    data = supabase.table("agents").select("*").execute()
    return data.data


@app.get("/agents/check-name")
def check_name(name: str):
    data = supabase.table("agents").select("id").eq("name", name).execute()
    return {"exists": len(data.data) > 0}


# ── Dry Run (real LLM via ReAct prompt) ──────────────────────

def _get_llm_config(llm_config_id: str) -> dict:
    """Fetch LLM config row and decrypt the api_key."""
    result = supabase.table("llm_configs").select("*").eq("id", llm_config_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="LLM config not found")
    cfg = result.data[0]
    cfg["api_key"] = decrypt(cfg["api_key"])
    return cfg


def _build_react_prompt(description: str, skills: str, user_prompt: str) -> str:
    skills_block = f"\nAgent Skills:\n{skills}" if skills else ""
    return f"""You are an AI agent operating in ReAct (Reasoning + Acting) style.

Agent Description: {description}{skills_block}

Use the following format strictly:
Thought: <your reasoning about the problem>
Action: <what you would do or look up>
Observation: <what you find or conclude>
... (repeat Thought/Action/Observation as needed)
Final Answer: <your final response to the user>

User Prompt: {user_prompt}"""


def _call_llm(cfg: dict, system_prompt: str) -> str:
    """Call the LLM API. Supports OpenAI-compatible endpoints (OpenAI, Groq, Ollama, Azure, Anthropic-openai-compat)."""
    provider = cfg["provider"].lower()
    api_url = cfg["api_url"].rstrip("/")
    api_key = cfg["api_key"]
    model = cfg["model"]

    headers = {"Content-Type": "application/json"}

    if provider == "anthropic":
        # Anthropic native API
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": system_prompt}],
        }
        url = f"{api_url}/v1/messages"
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
    else:
        # OpenAI-compatible: OpenAI, Groq, Ollama, Azure
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": system_prompt}],
            "temperature": 0.3,
        }
        url = f"{api_url}/chat/completions"
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


@app.post("/agents/dry-run")
def dry_run(data: DryRunSchema):
    cfg = _get_llm_config(data.llm_config_id)
    system_prompt = _build_react_prompt(data.description, data.skills, data.prompt)
    try:
        output = _call_llm(cfg, system_prompt)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM API error {e.response.status_code}: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach LLM API: {str(e)}")
    return {"output": output}
