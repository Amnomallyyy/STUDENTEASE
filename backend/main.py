"""CareerLens API entry point. Run with:

    uvicorn backend.main:app --reload

Registers one router per module (see docs/api.md), CORS for the Vite dev server (override with
CORS_ORIGINS), and two housekeeping routes: GET /health and GET /built-with.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

try:  # <repo root>/.env: blank values keep the code defaults, variables already set in the shell win
    from dotenv import dotenv_values

    for _key, _value in dotenv_values(Path(__file__).resolve().parents[1] / ".env").items():
        if _value:
            os.environ.setdefault(_key, _value)
except ImportError:  # python-dotenv is optional: set the variables in the shell instead
    pass

from backend.api import analyzer, career, chat, geo, jobs, profile
from backend.built_with import BUILT_WITH
from backend.services import data, session

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

app = FastAPI(
    title="CareerLens API",
    version="0.1.0",
    description="Upload your CV, and in two minutes know exactly what to fix, where to apply, and how to answer.",
)


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def bind_session(request: Request, call_next):
    """One profile per browser tab: the frontend sends X-Session-Id; services read it from session.current."""
    token = session.current.set(session.session_id_from_header(request.headers.get("x-session-id")))
    try:
        return await call_next(request)
    finally:
        session.current.reset(token)


app.include_router(profile.router)
app.include_router(career.router)
app.include_router(chat.router)
app.include_router(jobs.router)
app.include_router(geo.router)
app.include_router(analyzer.router)

try:  # M3's interview router is optional until it lands.
    from backend.api import interview
except ImportError:
    interview = None
else:
    app.include_router(interview.router)


def _count(loader) -> int | None:
    """Number of items in a dataset, or None if the file is missing or malformed."""
    try:
        return len(loader())
    except data.DataError:
        return None


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    """Liveness check for Render plus a quick view of which provider and datasets are in use."""
    return {
        "status": "ok",
        "llm_provider": os.getenv("LLM_PROVIDER", "anthropic").lower(),
        "embed_provider": os.getenv("EMBED_PROVIDER", "local").lower(),
        "data": {
            "roles": _count(data.load_roles),
            "jobs": _count(data.load_jobs),
            "resources": _count(data.load_resources),
        },
    }


@app.get("/built-with", tags=["meta"])
def built_with() -> list[dict[str, str]]:
    """Every model, API, dataset and library with its licence, for the in-app 'Built with' page."""
    return [{"name": i["name"], "kind": i["kind"], "licence": i["licence"], "url": i["url"]} for i in BUILT_WITH]
