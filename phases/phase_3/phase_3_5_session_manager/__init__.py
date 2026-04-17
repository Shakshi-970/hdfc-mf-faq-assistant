"""
phases/phase_3_5_session_manager
---------------------------------
Session Manager — public interface.

Supports multiple independent chat threads simultaneously.

  session_id (UUID)
      ├── conversation_history[]  ← ephemeral, in-memory only (no PII stored)
      ├── active_scheme_context   ← last mentioned scheme name
      └── created_at / last_active

Properties:
  - Sessions are fully isolated — no cross-contamination between threads
  - No PII is stored in any session state
  - Session context expires after configurable inactivity TTL (default 30 min)
  - Backed by in-memory dict (dev) or Redis (prod horizontal scaling)

Backend selection (automatic):
  REDIS_URL set   → RedisSessionBackend  (production)
  REDIS_URL unset → InMemorySessionBackend (development)

Usage:
    from phases.phase_3_5_session_manager import (
        create_session, get_session, append_message,
        set_scheme_context, delete_session, active_session_count,
        Session,
    )
"""

from .manager import (
    active_session_count,
    append_message,
    create_session,
    delete_session,
    get_session,
    set_scheme_context,
)
from .session import Session

__all__ = [
    "Session",
    "create_session",
    "get_session",
    "append_message",
    "set_scheme_context",
    "delete_session",
    "active_session_count",
]
