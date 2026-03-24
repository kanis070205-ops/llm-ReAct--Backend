from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import llm_config, agents, tools

app = FastAPI(title="AI Console API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(llm_config.router)
app.include_router(agents.router)
app.include_router(tools.router)
