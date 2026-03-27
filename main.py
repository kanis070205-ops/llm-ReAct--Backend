from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import llm_config, agents, tools, tasks
from api import scheduler as scheduler_api
from services.scheduler_service import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield


app = FastAPI(title="AI Console API", version="1.0.0", lifespan=lifespan)

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
app.include_router(tasks.router)
app.include_router(scheduler_api.router)
