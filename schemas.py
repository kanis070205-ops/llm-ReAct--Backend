from pydantic import BaseModel

class LLMConfig(BaseModel):
    provider: str
    api_url: str
    api_key: str
    model: str