"""
phases/phase_6/phase_6_1_groq_pipeline/pipeline.py
---------------------------------------------------
Query Pipeline Orchestrator — Phase 6 (Groq / configurable LLM provider)

Identical pipeline steps to Phase 3.4, but Step 6 (LLM generation) uses
the provider-switchable LLMClient instead of being hardcoded to Claude.

All Phase 3 components are imported directly — nothing is duplicated:
  Step 1 : classify_query     ← phases.phase_3.phase_3_4_query_pipeline
  Step 2 : refusal guard      ← same refusal messages as Phase 3
  Step 3 : rewrite_query      ← phases.phase_3.phase_3_4_query_pipeline
  Step 4 : retrieve           ← phases.phase_3.phase_3_4_query_pipeline
  Step 5 : build_messages     ← phases.phase_3.phase_3_4_query_pipeline
  Step 6 : LLM generate       ← llm_client.get_llm_client()  ← NEW (Phase 6)
  Step 7 : store in session   ← phases.phase_3.phase_3_5_session_manager

Required environment variables:
  GROQ_API_KEY          when LLM_PROVIDER=groq   (default)
  ANTHROPIC_API_KEY     when LLM_PROVIDER=claude
  CHROMA_API_KEY / CHROMA_TENANT / CHROMA_DATABASE  (always required)
"""

from __future__ import annotations

import logging
from collections import Counter

# ── Reuse all Phase 3 components unchanged ──────────────────────────────────
from phases.phase_3.phase_3_4_query_pipeline.classifier import classify_query
from phases.phase_3.phase_3_4_query_pipeline.prompt_builder import (
    SYSTEM_PROMPT,
    build_messages,
)
from phases.phase_3.phase_3_4_query_pipeline.retriever import retrieve
from phases.phase_3.phase_3_4_query_pipeline.rewriter import (
    rewrite_query,
    _SCHEME_ALIASES,
)
from phases.phase_3.phase_3_5_session_manager import (
    append_message,
    get_session,
    set_scheme_context,
)

# ── Phase 6: configurable LLM client ────────────────────────────────────────
from .llm_client import LLMClient, get_llm_client

# ── Phase 8: response formatter + post-generation guardrail ─────────────────
from phases.phase_8.phase_8_1_response_formatter.formatter import (
    format_response,
    _NO_INFO_PATTERNS,
)
from phases.phase_8.phase_8_1_response_formatter.guardrail import sanitize_output

# ── Phase 11: privacy-safe audit logging (no query text in logs) ─────────────
from phases.phase_11.phase_11_1_security.audit_log import (
    log_query_event,
    log_rewrite_event,
)

# ── Phase 12: ambiguous scheme clarification + real-time NAV redirect ─────────
from phases.phase_12.phase_12_1_clarification.scheme_resolver import (
    clarification_message,
    detect_ambiguous_schemes,
    is_realtime_nav_query,
    nav_redirect_message,
)

logger = logging.getLogger(__name__)


def _detect_scheme(query: str) -> str | None:
    """
    Return the canonical scheme name if the query explicitly names one HDFC scheme,
    else None.  Used to clear a stale session context when the user switches schemes.
    """
    for pattern, canonical in _SCHEME_ALIASES:
        if pattern.search(query):
            return canonical
    return None

# ---------------------------------------------------------------------------
# Module-level LLM client (lazy-initialised on first call)
# ---------------------------------------------------------------------------

_llm: LLMClient | None = None


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = get_llm_client()
        logger.info("LLM client initialised: provider=%s", _llm.provider_name)
    return _llm


# ---------------------------------------------------------------------------
# Refusal messages — identical to Phase 3
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
# Public interface
# ---------------------------------------------------------------------------

def run_query(session_id: str, query: str) -> dict:
    """
    Run the full query pipeline for a session and user query.

    Identical contract to phases.phase_3.phase_3_4_query_pipeline.pipeline.run_query —
    drop-in replacement for the FastAPI app layer.

    Parameters
    ----------
    session_id : Active session UUID.
    query      : Raw user query string.

    Returns
    -------
    dict with keys:
      answer       : str  — LLM-generated or refusal answer
      source_url   : str  — top chunk source URL  (factual queries only)
      last_updated : str  — ingestion_date of top chunk (factual only)
      query_class  : str  — classifier output
      llm_provider : str  — which LLM was used (e.g. "groq/llama-3.3-70b-versatile")
      session_id   : str  — echoed back
      error        : str  — set only if a service error occurred
    """
    session = get_session(session_id)
    if session is None:
        return {
            "error": "Session not found or expired. Please create a new session.",
            "session_id": session_id,
        }

    # --- Step 1: Classify ---
    query_class = classify_query(query)
    # Phase 11 — privacy-safe log: session_id + class only, NO query text
    log_query_event(
        logger,
        session_id,
        query_class,
        provider=_get_llm().provider_name if _llm else "uninitialised",
    )

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

    # --- Step 2.5: Ambiguous scheme clarification + real-time NAV redirect ---
    # Phase 12 — Section 12 mitigations: ask clarifying question for vague
    # HDFC queries; redirect to Groww page for live NAV requests.
    if query_class == "factual":
        ambiguous = detect_ambiguous_schemes(query)
        if ambiguous:
            answer = clarification_message(ambiguous)
            append_message(session_id, "user", query)
            append_message(session_id, "assistant", answer)
            return {
                "answer": answer,
                "query_class": "ambiguous_scheme",
                "session_id": session_id,
            }

        if is_realtime_nav_query(query):
            answer = nav_redirect_message(session.active_scheme_context)
            append_message(session_id, "user", query)
            append_message(session_id, "assistant", answer)
            return {
                "answer": answer,
                "query_class": "realtime_nav",
                "session_id": session_id,
            }

    # --- Step 3: Rewrite ---
    rewritten = rewrite_query(query)
    # Phase 11 — log rewrite boolean only, NOT the rewritten query text
    log_rewrite_event(logger, session_id, rewritten != query)

    # --- Step 4: Retrieve ---
    # If the query explicitly names a scheme that differs from the session context,
    # use the query's scheme as the filter (clears stale context for multi-scheme sessions).
    detected_scheme = _detect_scheme(query)
    if detected_scheme:
        scheme_filter = detected_scheme
    else:
        scheme_filter = session.active_scheme_context

    try:
        chunks = retrieve(rewritten, scheme_filter=scheme_filter)
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
    llm = _get_llm()
    try:
        answer = llm.generate(SYSTEM_PROMPT, messages)
    except EnvironmentError as exc:
        logger.error("LLM env error: %s", exc)
        return {"error": str(exc), "session_id": session_id}
    except Exception as exc:
        logger.error("LLM generation failed [%s]: %s", llm.provider_name, exc, exc_info=True)
        return {
            "error": "Answer generation service unavailable. Please try again shortly.",
            "session_id": session_id,
        }

    # --- Step 6.5: Post-generation guardrail + response formatter ---
    top = chunks[0]
    source_url = top["metadata"].get("source_url", "https://groww.in")
    ingestion_date = top["metadata"].get("ingestion_date", "")

    answer, was_sanitized = sanitize_output(answer)
    if was_sanitized:
        logger.warning(
            "session=%s Advisory language detected in LLM output — sanitized.",
            session_id,
        )

    answer = format_response(answer, source_url, ingestion_date)

    # --- Step 7: Store in session ---
    append_message(session_id, "user", query)
    append_message(session_id, "assistant", answer)

    # Only expose source_url to the frontend when the bot couldn't answer —
    # if the answer has real content, the citation pill should not appear.
    cant_answer = bool(_NO_INFO_PATTERNS.search(answer))

    return {
        "answer": answer,
        "source_url": source_url if cant_answer else None,
        "last_updated": ingestion_date if cant_answer else None,
        "query_class": query_class,
        "llm_provider": llm.provider_name,
        "session_id": session_id,
    }
