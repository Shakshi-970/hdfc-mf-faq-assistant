"""
phases/phase_3_5_session_manager/manager.py
--------------------------------------------
Session manager — backend factory and public API.

Backend selection (automatic, based on environment):
  REDIS_URL set   → RedisSessionBackend  (prod, horizontal scaling)
  REDIS_URL unset → InMemorySessionBackend (dev, single instance)

The backend is initialised once on first call and cached for the process
lifetime.  Callers never interact with backends directly — they use the
module-level functions exported from __init__.py.

Environment variables:
  REDIS_URL          : Redis connection URL (enables Redis backend)
                       e.g. redis://localhost:6379/0
  SESSION_TTL_SECONDS: Override default 30-min TTL (optional)
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Union

from .session import DEFAULT_TTL_SECONDS, Session

logger = logging.getLogger(__name__)

# Type alias for either backend
_BackendType = Union[
    "InMemorySessionBackend",   # noqa: F821 — resolved at runtime
    "RedisSessionBackend",       # noqa: F821 — resolved at runtime
]

_backend: Optional[_BackendType] = None


def _get_backend() -> _BackendType:
    """
    Initialise and return the singleton backend instance.
    Selection is based on REDIS_URL environment variable.
    """
    global _backend
    if _backend is not None:
        return _backend

    ttl = int(os.environ.get("SESSION_TTL_SECONDS", DEFAULT_TTL_SECONDS))
    redis_url = os.environ.get("REDIS_URL", "").strip()

    if redis_url:
        from .backends.redis_backend import RedisSessionBackend
        logger.info("Session backend: Redis (%s)", redis_url)
        _backend = RedisSessionBackend(redis_url=redis_url, ttl_seconds=ttl)
    else:
        from .backends.memory import InMemorySessionBackend
        logger.info("Session backend: in-memory (dev mode)")
        _backend = InMemorySessionBackend(ttl_seconds=ttl)

    return _backend


# ---------------------------------------------------------------------------
# Public API — thin wrappers over the selected backend
# ---------------------------------------------------------------------------

def create_session() -> str:
    """Create a new isolated session. Returns the UUID session_id."""
    return _get_backend().create_session()


def get_session(session_id: str) -> Optional[Session]:
    """
    Return the Session for session_id.
    Returns None if the session does not exist or has expired.
    """
    return _get_backend().get_session(session_id)


def append_message(session_id: str, role: str, content: str) -> None:
    """
    Append a {role, content} message to the session history.
    role must be "user" or "assistant".
    Refreshes the session TTL.
    """
    _get_backend().append_message(session_id, role, content)


def set_scheme_context(session_id: str, scheme_name: str) -> None:
    """
    Store the most recently identified scheme name in the session.
    Used by the retriever to bias future searches to the active scheme.
    Refreshes the session TTL.
    """
    _get_backend().set_scheme_context(session_id, scheme_name)


def delete_session(session_id: str) -> bool:
    """
    Immediately delete a session and all its history.
    Returns True if the session existed, False otherwise.
    """
    return _get_backend().delete_session(session_id)


def active_session_count() -> int:
    """Return the number of sessions currently within their TTL."""
    return _get_backend().active_session_count()
