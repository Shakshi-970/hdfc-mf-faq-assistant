"""
phases/phase_3_4_query_pipeline/pipeline.py
--------------------------------------------
Query Pipeline Orchestrator

Runs the full pipeline for one user query within a session:

  Step 1 : classify_query    — factual / advisory / out_of_scope / pii_risk
  Step 2 : refusal guard     — return pre-written message for non-factual queries
  Step 3 : rewrite_query     — expand abbreviations, normalise scheme names
  Step 4 : retrieve          — embed + Chroma Cloud search + re-rank (top-3)
  Step 5 : build_messages    — construct LLM prompt with retrieved context
  Step 6 : call Claude       — generate grounded, citation-backed answer
  Step 7 : store in session  — append user query + assistant answer to history

Required environment variable:
  ANTHROPIC_API_KEY : Anthropic Claude API key
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from typing import Optional

from .classifier import classify_query
from .prompt_builder import SYSTEM_PROMPT, build_messages
from .retriever import retrieve
from .rewriter import rewrite_query
from .session_store import append_message, get_session, set_scheme_context

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512

# ---------------------------------------------------------------------------
# Refusal messages (Steps 2 — non-factual classes)
# ---------------------------------------------------------------------------

_REFUSALS: dict[str, str] = {
    "advisory": (
        "This assistant provides verified facts only and cannot offer investment "
        "advice or fund recommendations. For personalised guidance, please consult "
        "a SEBI-registered investment adviser or visit the AMFI investor education "
        "portal: https://www.amfiindia.com/investor-corner/knowledge-center"
    ),
    "out_of_scope": (
        "This query is outside the scope of this assistant. I can answer factual "
        "questions about the following HDFC Mutual Fund schemes: "
        "HDFC Large Cap Fund, HDFC Equity Fund, HDFC ELSS Tax Saver Fund, "
        "HDFC Mid-Cap Fund, and HDFC Focused Fund (all Direct Growth plans)."
    ),
    "pii_risk": (
        "For your security, please do not share personal information such as "
        "PAN, Aadhaar numbers, account numbers, or OTPs here. "
        "This assistant only answers factual questions about mutual fund schemes."
    ),
}

# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_claude(messages: list[dict]) -> str:
    """Call Claude and return the text response."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_query(session_id: str, query: str) -> dict:
    """
    Run the full query pipeline for a session and user query.

    Parameters
    ----------
    session_id : Active session UUID.
    query      : Raw user query string.

    Returns
    -------
    dict with keys:
      answer       : str   — LLM-generated or refusal answer
      source_url   : str   — top chunk source URL (factual queries only)
      last_updated : str   — ingestion_date of top chunk (factual only)
      query_class  : str   — classifier output
      session_id   : str   — echoed back
      error        : str   — set only if a service error occurred
    """
    session = get_session(session_id)
    if session is None:
        return {
            "error": "Session not found or expired. Please create a new session.",
            "session_id": session_id,
        }

    # --- Step 1: Classify ---
    query_class = classify_query(query)
    logger.info("session=%s query='%.50s...' class=%s", session_id, query, query_class)

    # --- Step 2: Refusal guard ---
    if query_class in _REFUSALS:
        answer = _REFUSALS[query_class]
        append_message(session_id, "user", query)
        append_message(session_id, "assistant", answer)
        return {
            "answer": answer,
            "query_class": query_class,
            "session_id": session_id,
        }

    # --- Step 3: Rewrite ---
    rewritten = rewrite_query(query)
    if rewritten != query:
        logger.debug("Rewritten query: '%.80s'", rewritten)

    # --- Step 4: Retrieve ---
    try:
        chunks = retrieve(rewritten, scheme_filter=session.active_scheme_context)
    except EnvironmentError as exc:
        logger.error("Retrieval env error: %s", exc)
        return {"error": str(exc), "session_id": session_id}
    except Exception as exc:
        logger.error("Retrieval failed: %s", exc, exc_info=True)
        return {
            "error": "Retrieval service unavailable. Please try again shortly.",
            "session_id": session_id,
        }

    if not chunks:
        answer = (
            "I could not find relevant information for your query in the available "
            "data. Please check the Groww scheme pages directly for the latest details."
        )
        append_message(session_id, "user", query)
        append_message(session_id, "assistant", answer)
        return {
            "answer": answer,
            "query_class": query_class,
            "session_id": session_id,
        }

    # Update active scheme context from dominant chunk scheme
    scheme_names = [
        c["metadata"].get("scheme_name")
        for c in chunks
        if c["metadata"].get("scheme_name")
    ]
    if scheme_names:
        dominant = Counter(scheme_names).most_common(1)[0][0]
        set_scheme_context(session_id, dominant)

    # --- Step 5 + 6: Prompt + Generate ---
    messages = build_messages(query, chunks)
    try:
        answer = _call_claude(messages)
    except EnvironmentError as exc:
        logger.error("LLM env error: %s", exc)
        return {"error": str(exc), "session_id": session_id}
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc, exc_info=True)
        return {
            "error": "Answer generation service unavailable. Please try again shortly.",
            "session_id": session_id,
        }

    # --- Step 7: Store in session ---
    append_message(session_id, "user", query)
    append_message(session_id, "assistant", answer)

    top = chunks[0]
    return {
        "answer": answer,
        "source_url": top["metadata"].get("source_url"),
        "last_updated": top["metadata"].get("ingestion_date"),
        "query_class": query_class,
        "session_id": session_id,
    }
