from pydantic import BaseModel
from typing import Optional


class AgentCreate(BaseModel):
    name: str
    description: str
    category: str
    skills: Optional[str] = None
    llm_config_id: str


class AgentRead(BaseModel):
    id: str
    name: str
    description: str
    category: str
    skills: Optional[str] = None
    llm_config_id: str


class DryRunRequest(BaseModel):
    description: str
    category: str           # needed to pick the right tools
    skills: Optional[str] = None
    llm_config_id: str
    prompt: str


class RunAgentRequest(BaseModel):
    agent_id: str
    prompt: str
