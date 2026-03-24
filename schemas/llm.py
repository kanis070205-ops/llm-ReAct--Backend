from pydantic import BaseModel


class LLMConfigCreate(BaseModel):
    provider: str
    api_url: str
    api_key: str
    model: str


class LLMConfigRead(BaseModel):
    id: str
    provider: str
    api_url: str
    model: str
