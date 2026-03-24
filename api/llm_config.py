from fastapi import APIRouter
from core.database import supabase
from core.security import encrypt
from schemas.llm import LLMConfigCreate, LLMConfigRead

router = APIRouter(prefix="/llm-config", tags=["LLM Config"])


@router.post("", status_code=201)
def save_config(config: LLMConfigCreate):
    data = supabase.table("llm_configs").insert({
        "provider": config.provider,
        "api_url": config.api_url,
        "api_key": encrypt(config.api_key),
        "model": config.model,
    }).execute()
    return {"message": "Saved", "data": data.data[0] if data.data else {}}


@router.get("", response_model=list[LLMConfigRead])
def get_configs():
    data = supabase.table("llm_configs").select("id, provider, api_url, model").execute()
    return data.data
