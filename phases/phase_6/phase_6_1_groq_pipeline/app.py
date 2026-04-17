"""
phases/phase_6/phase_6_1_groq_pipeline/app.py
----------------------------------------------
FastAPI application — Phase 6 (Groq / configurable LLM provider).

Same REST contract as Phase 3.4 — the UI and any API client can point to either
backend without code changes.  The only additions are:

  • GET  /health  now returns `llm_provider` field
  • POST /chat/{session_id} response now returns `llm_provider` field

Endpoints:
  GET    /health                  — liveness check (includes llm_provider)
  POST   /sessions/new            — create a new chat session, returns UUID
  POST   /chat/{session_id}       — submit a query, returns answer + citation
  DELETE /sessions/{session_id}   — expire a session

Run:
  python -m phases.phase_6.phase_6_1_groq_pipeline      # port 8001 by default

Required environment variables:
  GROQ_API_KEY          — Groq API key (when LLM_PROVIDER=groq, the default)
  CHROMA_API_KEY / CHROMA_TENANT / CHROMA_DATABASE

Optional:
  LLM_PROVIDER          — "groq" (default) or "claude"
  GROQ_MODEL            — Groq model ID (default: llama-3.3-70b-versatile)
  LLM_MAX_TOKENS        — max output tokens (default: 512)
  API_PORT              — HTTP port (default: 8001)
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .pipeline import run_query, _get_llm
from phases.phase_3.phase_3_4_query_pipeline.retriever import (
    _get_collection,
    _get_model,
)
from phases.phase_3.phase_3_5_session_manager import (
    active_session_count,
    create_session,
    delete_session,
    get_session,
)

# ── Phase 10: API Gateway — rate limiting + request cache ────────────────────
from phases.phase_10.phase_10_2_rate_limiting.middleware import RateLimitMiddleware
from phases.phase_10.phase_10_3_request_cache.cache import (
    cache_stats,
    get_cached_response,
    set_cached_response,
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
# Lifespan — warm up LLM client on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm all lazy-loaded resources so the first request is fast
    try:
        llm = _get_llm()
        logger.info("LLM provider: %s", llm.provider_name)
    except EnvironmentError as exc:
        logger.error("LLM client failed to initialise: %s", exc)

    import asyncio

    # Run all blocking/sync initialisation in a thread pool so they don't
    # conflict with the async event loop (Chroma and sentence-transformers
    # both use synchronous httpx clients).
    loop = asyncio.get_event_loop()

    try:
        logger.info("Loading embedding model (BAAI/bge-small-en-v1.5)...")
        await loop.run_in_executor(None, _get_model)
        logger.info("Embedding model loaded.")
    except Exception as exc:
        logger.error("Embedding model failed to load: %s", exc)

    try:
        logger.info("Connecting to Chroma Cloud...")
        await loop.run_in_executor(None, _get_collection)
        logger.info("Chroma Cloud ready.")
    except Exception as exc:
        logger.error("Chroma connection failed at startup (will retry on first request): %s", exc)

    logger.info("Mutual Fund FAQ Assistant ready.")
    yield
    logger.info(
        "Shutting down. Active sessions at shutdown: %d",
        active_session_count(),
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mutual Fund FAQ Assistant — Phase 6 + 10",
    description=(
        "Facts-only FAQ assistant for HDFC Mutual Fund schemes. "
        "Phase 6 backend: Groq inference (llama-3.3-70b-versatile by default) "
        "with configurable LLM_PROVIDER env var. "
        "No investment advice — factual information only."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow the static HTML test UI (and any local origin) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # open for local testing
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Phase 10 — rate limiting middleware (applied to all routes)
app.add_middleware(RateLimitMiddleware)


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
    llm_provider: str | None = None   # e.g. "groq/llama-3.3-70b-versatile"


class SessionResponse(BaseModel):
    session_id: str


class HealthResponse(BaseModel):
    status: str
    version: str
    active_sessions: int
    llm_provider: str   # which LLM is powering this instance
    cache: dict         # Phase 10 — cache backend + current entry count


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
)
def health():
    try:
        provider = _get_llm().provider_name
    except Exception:
        provider = "unavailable"
    return {
        "status": "ok",
        "version": "2.0.0",
        "active_sessions": active_session_count(),
        "llm_provider": provider,
        "cache": cache_stats(),
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
    - Response includes `llm_provider` so the caller knows which model answered.
    """
    if get_session(session_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired. Create a new session via POST /sessions/new.",
        )

    query = request.query.strip()

    # Phase 10 — check response cache before hitting the retriever + LLM
    cached = get_cached_response(query)
    if cached:
        logger.debug("Cache hit for session=%s query='%.50s'", session_id, query)
        return ChatResponse(
            session_id=session_id,
            answer=cached["answer"],
            source_url=cached.get("source_url"),
            last_updated=cached.get("last_updated"),
            query_class=cached.get("query_class"),
            llm_provider=cached.get("llm_provider"),
        )

    result = run_query(session_id, query)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result["error"],
        )

    # Phase 10 — store successful factual answers in cache
    set_cached_response(query, result)

    return ChatResponse(
        session_id=session_id,
        answer=result["answer"],
        source_url=result.get("source_url"),
        last_updated=result.get("last_updated"),
        query_class=result.get("query_class"),
        llm_provider=result.get("llm_provider"),
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
