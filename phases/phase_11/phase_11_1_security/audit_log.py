"""
phases/phase_11/phase_11_1_security/audit_log.py
-------------------------------------------------
Privacy-safe audit logging — Section 11, Security and Privacy Controls.

Architecture requirement:
  "No logging of user queries — Query logs contain only session_id + timestamp"

The pipeline previously emitted log lines containing up to 50 characters of
the raw query string.  This module provides replacement logging functions
that record only non-PII operational fields:

  session_id   — opaque UUID, not linked to any user identity
  query_class  — classifier output (factual / advisory / out_of_scope / pii_risk)
  provider     — which LLM answered (e.g. "groq/llama-3.3-70b-versatile")
  latency_ms   — wall-clock time for monitoring (integer, optional)
  cache_hit    — whether the response came from cache (optional)
  rewritten    — whether query rewriting fired (boolean, no rewritten text)

Fields that are NEVER logged:
  • Raw query text
  • Rewritten query text
  • LLM answer text
  • Any PAN / Aadhaar / account numbers that may appear in a pii_risk query

Public API
----------
log_query_event(logger, session_id, query_class, *, provider, latency_ms, cache_hit)
log_session_event(logger, event, session_id)
log_rewrite_event(logger, session_id, rewritten)
"""

from __future__ import annotations

import logging


def log_query_event(
    logger: logging.Logger,
    session_id: str,
    query_class: str,
    *,
    provider: str = "unknown",
    latency_ms: int | None = None,
    cache_hit: bool = False,
) -> None:
    """
    Emit a structured INFO log for a completed query — no query text included.

    Parameters
    ----------
    logger      : Logger instance from the calling module.
    session_id  : UUID of the active session.
    query_class : Classifier output (factual / advisory / out_of_scope / pii_risk).
    provider    : LLM provider name (e.g. "groq/llama-3.3-70b-versatile").
    latency_ms  : End-to-end latency in milliseconds (omitted if None).
    cache_hit   : True when the response was served from the request cache.

    Log format (no query text)::

        session=<uuid> class=<class> provider=<p> cache_hit=<bool> latency_ms=<n>
    """
    parts = [
        f"session={session_id}",
        f"class={query_class}",
        f"provider={provider}",
        f"cache_hit={cache_hit}",
    ]
    if latency_ms is not None:
        parts.append(f"latency_ms={latency_ms}")
    logger.info(" ".join(parts))


def log_session_event(
    logger: logging.Logger,
    event: str,
    session_id: str,
) -> None:
    """
    Emit an INFO log for a session lifecycle event.

    Parameters
    ----------
    logger     : Logger instance.
    event      : One of "created", "expired", "deleted".
    session_id : UUID of the session.

    Log format::

        session_event=<event> session=<uuid>
    """
    logger.info("session_event=%s session=%s", event, session_id)


def log_rewrite_event(
    logger: logging.Logger,
    session_id: str,
    rewritten: bool,
) -> None:
    """
    Emit a DEBUG log indicating whether the query rewriter fired.

    The rewritten query text itself is NOT logged — only the boolean
    indicating that a rewrite occurred.

    Parameters
    ----------
    logger     : Logger instance.
    session_id : UUID of the active session.
    rewritten  : True when the rewriter produced a different string.
    """
    if rewritten:
        logger.debug("session=%s query_rewritten=true", session_id)
