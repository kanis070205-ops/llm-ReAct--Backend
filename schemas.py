from pydantic import BaseModel, Field
from typing import Optional

class LLMConfig(BaseModel):
    provider: str
    api_url: str
    api_key: str
    model: str

class AgentSchema(BaseModel):
    name: str
    description: str
    category: str
    skills: Optional[str] = None
    llm_config_id: str  # mandatory now

class DryRunSchema(BaseModel):
    description: str
    llm_config_id: str  # mandatory — needed to call real LLM
    prompt: str
    skills: Optional[str] = None
