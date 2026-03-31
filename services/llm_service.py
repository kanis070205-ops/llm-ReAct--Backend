"""
LLM Service — fetches and decrypts LLM config from DB.
"""
from fastapi import HTTPException
from core.database import supabase
from core.security import decrypt


def get_llm_config(llm_config_id: str) -> dict:
    """Fetch a config row from DB and return it with decrypted api_key."""
    result = supabase.table("llm_configs").select("*").eq("id", llm_config_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="LLM config not found")
    cfg = dict(result.data[0])
    cfg["api_key"] = decrypt(cfg["api_key"])
    return cfg
