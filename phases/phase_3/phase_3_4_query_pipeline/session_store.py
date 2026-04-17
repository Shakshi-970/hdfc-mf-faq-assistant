"""
phases/phase_3_4_query_pipeline/session_store.py
-------------------------------------------------
Thin proxy — all session management is delegated to
phases.phase_3_5_session_manager.

This module exists so that pipeline.py, app.py, and other Phase 3.4
modules can use short relative imports (from .session_store import ...)
without knowing about the Phase 3.5 package layout.

Backend selection (in-memory vs Redis) is controlled by the
REDIS_URL environment variable — see phase_3_5_session_manager/manager.py.
"""

from ..phase_3_5_session_manager import (  # noqa: F401
    Session,
    active_session_count,
    append_message,
    create_session,
    delete_session,
    get_session,
    set_scheme_context,
)

__all__ = [
    "Session",
    "create_session",
    "get_session",
    "append_message",
    "set_scheme_context",
    "delete_session",
    "active_session_count",
]
