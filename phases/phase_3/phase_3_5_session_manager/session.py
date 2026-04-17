"""
phases/phase_3_5_session_manager/session.py
--------------------------------------------
Session dataclass — the unit of state managed by both backends.

A Session holds only:
  - conversation_history  : ephemeral list of {role, content} dicts
  - active_scheme_context : last scheme mentioned (drives retrieval filter)
  - created_at / last_active : timestamps for TTL management

No user identity, PAN, Aadhaar, account number, or any PII is ever
stored in a session. Sessions are fully isolated — there is no way to
access another session's history.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

# Inactivity timeout — sessions older than this are evicted.
# Can be overridden by setting SESSION_TTL_SECONDS in the environment.
DEFAULT_TTL_SECONDS: int = 30 * 60  # 30 minutes


@dataclass
class Session:
    """
    Represents one isolated chat session.

    Attributes
    ----------
    session_id            : UUID string assigned at creation.
    history               : Ordered list of {role, content} message dicts.
                            Roles are "user" or "assistant".
    active_scheme_context : Scheme name inferred from the most recent
                            retrieval result — used to bias future searches.
    created_at            : Unix timestamp of session creation.
    last_active           : Unix timestamp of the most recent interaction.
    """

    session_id: str
    history: list[dict] = field(default_factory=list)
    active_scheme_context: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def is_expired(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
        """Return True if the session has exceeded its inactivity TTL."""
        return (time.time() - self.last_active) > ttl_seconds

    def touch(self) -> None:
        """Refresh last_active to now."""
        self.last_active = time.time()

    def to_dict(self) -> dict:
        """Serialise to a plain dict (for Redis JSON storage)."""
        return {
            "session_id": self.session_id,
            "history": self.history,
            "active_scheme_context": self.active_scheme_context,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Deserialise from a plain dict (from Redis JSON storage)."""
        return cls(
            session_id=data["session_id"],
            history=data.get("history", []),
            active_scheme_context=data.get("active_scheme_context"),
            created_at=data.get("created_at", time.time()),
            last_active=data.get("last_active", time.time()),
        )
