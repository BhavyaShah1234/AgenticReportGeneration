"""FastAPI application: all routes under /api (see docs/API.md)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.routes import router as agent_router
from app.auth.routes import router as auth_router
from app.catalog.routes import router as catalog_router
from app.config import get_settings
from app.db import init_db
from app.formats.routes import router as formats_router
from app.runs.routes import router as runs_router
from app.snowflake.routes import router as snowflake_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("snowflake.connector").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Agentic Report Generation API", version="0.1.0", lifespan=lifespan)

_settings = get_settings()
_origins = {_settings.frontend_url.rstrip("/"), "http://localhost:3000", "http://127.0.0.1:3000"}
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict:
    return {"ok": True}


for r in (auth_router, snowflake_router, catalog_router, formats_router, runs_router, agent_router):
    api.include_router(r)

app.include_router(api)
