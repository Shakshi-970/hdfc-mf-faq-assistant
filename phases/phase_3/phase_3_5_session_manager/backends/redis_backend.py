"""
phases/phase_3_5_session_manager/backends/redis_backend.py
-----------------------------------------------------------
Redis session backend (production / horizontally-scaled deployment).

Each session is stored as a JSON string under the key:
    mf_faq:session:<session_id>

Redis native TTL is used for automatic expiry — no background thread needed.

Active session count is tracked via a Redis Sorted Set:
    mf_faq:active_sessions
  score = last_active Unix timestamp
  member = session_id

This allows O(log N) lookups and range queries by timestamp.

Usage:
    Set the REDIS_URL environment variable to enable this backend.
    Example: redis://localhost:6379/0
             redis://:<password>@redis-host:6379/0

Requirements:
    redis[hiredis] — pip install redis[hiredis]
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Optional

from ..session import DEFAULT_TTL_SECONDS, Session

logger = logging.getLogger(__name__)

_KEY_PREFIX = "mf_faq:session:"
_ACTIVE_SET = "mf_faq:active_sessions"


class RedisSessionBackend:
    """
    Redis-backed session store that supports multiple FastAPI instances
    sharing state without sticky sessions.

    Parameters
    ----------
    redis_url    : Redis connection URL (e.g. redis://localhost:6379/0).
    ttl_seconds  : Inactivity TTL for session keys (default 30 min).
    """

    def __init__(
        self,
        redis_url: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        import redis as redis_lib

        self._redis = redis_lib.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds
        logger.info("RedisSessionBackend connected: %s", redis_url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _session_key(self, session_id: str) -> str:
        return f"{_KEY_PREFIX}{session_id}"

    def _write_session(self, session: Session) -> None:
        """Serialise and write session to Redis with TTL."""
        key = self._session_key(session.session_id)
        self._redis.set(key, json.dumps(session.to_dict()), ex=self._ttl)
        # Update score in active set
        self._redis.zadd(_ACTIVE_SET, {session.session_id: session.last_active})

    def _read_session(self, session_id: str) -> Optional[Session]:
        """Read and deserialise a session from Redis. Returns None if missing."""
        raw = self._redis.get(self._session_key(session_id))
        if raw is None:
            # Key expired or never existed — clean up active set
            self._redis.zrem(_ACTIVE_SET, session_id)
            return None
        return Session.from_dict(json.loads(raw))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create_session(self) -> str:
        """Create a new session, persist to Redis, return UUID."""
        session_id = str(uuid.uuid4())
        session = Session(session_id=session_id)
        self._write_session(session)
        logger.debug("Session created (Redis): %s", session_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """Return session from Redis, or None if expired / not found."""
        return self._read_session(session_id)

    def append_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session history and refresh TTL."""
        session = self._read_session(session_id)
        if session:
            session.history.append({"role": role, "content": content})
            session.touch()
            self._write_session(session)

    def set_scheme_context(self, session_id: str, scheme_name: str) -> None:
        """Update active scheme context and refresh TTL."""
        session = self._read_session(session_id)
        if session:
            session.active_scheme_context = scheme_name
            session.touch()
            self._write_session(session)

    def delete_session(self, session_id: str) -> bool:
        """Delete session from Redis. Returns True if it existed."""
        deleted = self._redis.delete(self._session_key(session_id))
        self._redis.zrem(_ACTIVE_SET, session_id)
        if deleted:
            logger.debug("Session deleted (Redis): %s", session_id)
        return bool(deleted)

    def active_session_count(self) -> int:
        """
        Count sessions active within the TTL window.
        Uses the sorted set score (last_active timestamp) to filter.
        """
        cutoff = time.time() - self._ttl
        return self._redis.zcount(_ACTIVE_SET, cutoff, "+inf")
