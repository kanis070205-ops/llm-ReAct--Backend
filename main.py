from fastapi import FastAPI
from client import supabase
from schemas import LLMConfig
from fastapi.middleware.cors import CORSMiddleware
from crypto import encrypt, decrypt

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/llm-config")
def save_config(config: LLMConfig):
    encrypted_key = encrypt(config.api_key)
    data = supabase.table("llm_configs").insert({
        "provider": config.provider,
        "api_url": config.api_url,
        "api_key": encrypted_key,   # 🔐 encrypted
        "model": config.model
    }).execute()

    return {"message": "Saved", "data": data.data}

@app.get("/llm-config")
def get_configs():
    data = supabase.table("llm_configs").select("*").execute()
    return data.data