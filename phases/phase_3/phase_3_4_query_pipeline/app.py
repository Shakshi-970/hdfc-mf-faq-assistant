"""
phases/phase_3_4_query_pipeline/app.py
---------------------------------------
FastAPI REST application for the Mutual Fund FAQ Assistant.

Endpoints:
  GET    /health                  — liveness check
  POST   /sessions/new            — create a new chat session, returns UUID
  POST   /chat/{session_id}       — submit a query, returns answer + citation
  DELETE /sessions/{session_id}   — expire a session

Run locally:
  python -m phases.phase_3_4_query_pipeline
  # or
  uvicorn phases.phase_3_4_query_pipeline.app:app --reload --port 8000

Required environment variables (set before starting):
  ANTHROPIC_API_KEY : Anthropic Claude API key
  CHROMA_API_KEY    : Chroma Cloud authentication key
  CHROMA_TENANT     : Chroma Cloud tenant identifier
  CHROMA_DATABASE   : Chroma Cloud database name
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .pipeline import run_query
from .session_store import (
    active_session_count,
    create_session,
    delete_session,
    get_session,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Mutual Fund FAQ Assistant starting up.")
    yield
    logger.info(
        "Mutual Fund FAQ Assistant shutting down. Active sessions at shutdown: %d",
        active_session_count(),
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mutual Fund FAQ Assistant",
    description=(
        "Facts-only FAQ assistant for HDFC Mutual Fund schemes. "
        "Answers objective, verifiable queries using data scraped from Groww.in. "
        "No investment advice — factual information only."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="User query")


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    source_url: str | None = None
    last_updated: str | None = None
    query_class: str | None = None


class SessionResponse(BaseModel):
    session_id: str


class HealthResponse(BaseModel):
    status: str
    version: str
    active_sessions: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
)
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "active_sessions": active_session_count(),
    }


@app.post(
    "/sessions/new",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
def new_session():
    """
    Create a new isolated chat session.
    Returns a `session_id` UUID that must be passed to `/chat/{session_id}`.
    Sessions expire after 30 minutes of inactivity.
    """
    session_id = create_session()
    logger.info("New session created: %s", session_id)
    return {"session_id": session_id}


@app.post(
    "/chat/{session_id}",
    response_model=ChatResponse,
    summary="Submit a query",
)
def chat(session_id: str, request: ChatRequest):
    """
    Submit a query within an existing session.

    - Factual queries return an answer grounded in the latest scraped data,
      with a source citation and ingestion date.
    - Advisory or out-of-scope queries return a polite refusal.
    - Queries containing PII are rejected for security.
    """
    if get_session(session_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired. Create a new session via POST /sessions/new.",
        )

    result = run_query(session_id, request.query.strip())

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result["error"],
        )

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        source_url=result.get("source_url"),
        last_updated=result.get("last_updated"),
        query_class=result.get("query_class"),
    )


@app.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Expire a session",
)
def expire_session(session_id: str):
    """
    Immediately expire and delete a session.
    All conversation history is discarded — no data is persisted.
    """
    if not delete_session(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    logger.info("Session deleted: %s", session_id)
