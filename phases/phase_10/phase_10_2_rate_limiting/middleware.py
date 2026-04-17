"""
phases/phase_10/phase_10_2_rate_limiting/middleware.py
------------------------------------------------------
Sliding-window rate limiting middleware for the FastAPI application.

Applied at the app layer as a second line of defence behind the Nginx
rate limiting zones defined in nginx.conf.  Useful when running the
backend directly (without Nginx), in development, or in unit tests.

Limits (configurable via env vars):
  /chat/{session_id}  — RATE_LIMIT_SESSION_RPM  (default: 10 req / min per session)
  all endpoints       — RATE_LIMIT_IP_RPM        (default: 60 req / min per IP)

Returns HTTP 429 with Retry-After header when a limit is exceeded.

Public API
----------
RateLimitMiddleware  — add to a FastAPI app with app.add_middleware(...)
SlidingWindowCounter — standalone counter; exported for unit tests
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_SESSION_RPM: int = int(os.environ.get("RATE_LIMIT_SESSION_RPM", "10"))
_IP_RPM:      int = int(os.environ.get("RATE_LIMIT_IP_RPM",      "60"))
_WINDOW:    float = 60.0   # sliding window size in seconds


# ---------------------------------------------------------------------------
# Sliding-window counter
# ---------------------------------------------------------------------------

class SlidingWindowCounter:
    """
    In-memory sliding-window rate counter.

    Tracks timestamps of recent requests per key and prunes entries
    outside the current window on every call — O(1) amortised.

    Parameters
    ----------
    limit  : Maximum number of requests allowed within *window* seconds.
    window : Rolling time window in seconds (default 60).
    """

    def __init__(self, limit: int, window: float = 60.0) -> None:
        self.limit  = limit
        self.window = window
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check whether a request from *key* is within the rate limit.

        Parameters
        ----------
        key : Arbitrary string identifier (session_id, IP address, etc.).

        Returns
        -------
        (allowed, remaining)
            *allowed*   — True if the request should proceed.
            *remaining* — How many more requests are allowed in this window.
        """
        now    = time.monotonic()
        bucket = self._buckets[key]

        # Evict timestamps that have fallen outside the window
        cutoff = now - self.window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            return False, 0

        bucket.append(now)
        return True, self.limit - len(bucket)


# ---------------------------------------------------------------------------
# Module-level limiter instances (shared across all requests)
# ---------------------------------------------------------------------------

_session_limiter = SlidingWindowCounter(_SESSION_RPM, _WINDOW)
_ip_limiter      = SlidingWindowCounter(_IP_RPM,      _WINDOW)


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Starlette/FastAPI middleware that enforces per-session and per-IP
    rate limits on chat and all other endpoints.

    Usage::

        from phases.phase_10.phase_10_2_rate_limiting.middleware import RateLimitMiddleware
        app.add_middleware(RateLimitMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # /health is exempt — needed by Docker HEALTHCHECK and load balancer probes
        if path == "/health":
            return await call_next(request)

        # Per-session limit on /chat/* (the expensive LLM path)
        if path.startswith("/chat/"):
            session_id = path.split("/chat/", 1)[-1].split("?")[0]
            allowed, remaining = _session_limiter.is_allowed(session_id)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": (
                            "Rate limit exceeded for this session. "
                            "Please wait before sending another query."
                        ),
                        "retry_after_seconds": int(_WINDOW),
                    },
                    headers={"Retry-After": str(int(_WINDOW))},
                )

        # Per-IP limit on all endpoints
        client_ip = (request.client.host if request.client else "unknown")
        allowed_ip, remaining_ip = _ip_limiter.is_allowed(client_ip)
        if not allowed_ip:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many requests from your IP address. Please wait.",
                    "retry_after_seconds": int(_WINDOW),
                },
                headers={"Retry-After": str(int(_WINDOW))},
            )

        response = await call_next(request)

        # Expose remaining quota in response headers (informational)
        if path.startswith("/chat/"):
            response.headers["X-RateLimit-Limit-Session"]     = str(_SESSION_RPM)
            response.headers["X-RateLimit-Remaining-Session"] = str(remaining)
        response.headers["X-RateLimit-Limit-IP"]      = str(_IP_RPM)
        response.headers["X-RateLimit-Remaining-IP"]  = str(remaining_ip)

        return response
