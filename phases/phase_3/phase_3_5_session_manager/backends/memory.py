"""
phases/phase_3_5_session_manager/backends/memory.py
-----------------------------------------------------
In-memory session backend (development / single-instance deployment).

All sessions live in a module-level dict keyed by session_id.
TTL eviction is lazy — expired sessions are removed on access, not on
a background timer.  This avoids threading complexity while keeping
memory usage bounded in practice (each query access clears its own
session if stale).

Not suitable for horizontally-scaled deployments — use RedisSessionBackend
for multi-instance setups.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from ..session import DEFAULT_TTL_SECONDS, Session

logger = logging.getLogger(__name__)


class InMemorySessionBackend:
    """
    Thread-safe*-ish in-memory session store.

    CPython's GIL provides adequate protection for the dict operations
    performed here (single dict reads/writes are atomic in CPython).
    For true multi-threaded safety in other runtimes, wrap with a Lock.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._store: dict[str, Session] = {}
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evict_if_expired(self, session_id: str) -> bool:
        """
        Remove session if expired. Returns True if it was evicted.
        """
        session = self._store.get(session_id)
        if session is not None and session.is_expired(self._ttl):
            del self._store[session_id]
            logger.debug("Session %s evicted (TTL exceeded).", session_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_session(self) -> str:
        """Create a new session and return its UUID."""
        session_id = str(uuid.uuid4())
        self._store[session_id] = Session(session_id=session_id)
        logger.debug("Session created: %s", session_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """Return the session, or None if not found or expired."""
        self._evict_if_expired(session_id)
        return self._store.get(session_id)

    def append_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to history and refresh last_active."""
        session = self.get_session(session_id)
        if session:
            session.history.append({"role": role, "content": content})
            session.touch()

    def set_scheme_context(self, session_id: str, scheme_name: str) -> None:
        """Update the active scheme context and refresh last_active."""
        session = self.get_session(session_id)
        if session:
            session.active_scheme_context = scheme_name
            session.touch()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        if session_id in self._store:
            del self._store[session_id]
            logger.debug("Session deleted: %s", session_id)
            return True
        return False

    def active_session_count(self) -> int:
        """Count sessions that have not yet exceeded their TTL."""
        now = time.time()
        return sum(
            1 for s in self._store.values()
            if (now - s.last_active) <= self._ttl
        )
