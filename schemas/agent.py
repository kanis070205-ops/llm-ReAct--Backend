from pydantic import BaseModel
from typing import Optional


class AgentCreate(BaseModel):
    name: str
    description: str
    category: str
    skills: Optional[str] = None
    llm_config_id: str
    tools: Optional[list[str]] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    skills: Optional[str] = None
    llm_config_id: Optional[str] = None
    tools: Optional[list[str]] = None


class AgentRead(BaseModel):
    id: str
    name: str
    description: str
    category: str
    skills: Optional[str] = None
    llm_config_id: str


class DryRunRequest(BaseModel):
    description: str
    category: str
    skills: Optional[str] = None
    llm_config_id: str
    prompt: str
    tools: Optional[list[str]] = None


class RunAgentRequest(BaseModel):
    agent_id: str
    prompt: str
