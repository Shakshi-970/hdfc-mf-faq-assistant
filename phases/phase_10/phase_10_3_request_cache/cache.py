"""
phases/phase_10/phase_10_3_request_cache/cache.py
--------------------------------------------------
Query response cache for the Mutual Fund FAQ Assistant.

Caches factual pipeline results by a normalised query key, avoiding
redundant Chroma Cloud lookups and LLM calls for identical questions
asked within the same daily ingestion cycle.

Cache key  : SHA-256( query.strip().lower() )
TTL        : CACHE_TTL_SECONDS (default 3 600 s / 1 hour)
             Safe because the corpus is refreshed once per day at 09:15 IST.
Max size   : CACHE_MAX_ENTRIES (default 256) in-memory entries (LRU eviction)
Storage    : In-memory LRU dict (dev / single-instance)
             Redis (prod — activated automatically when REDIS_URL is set)

Refusals (advisory, out_of_scope, pii_risk) and error results are
never cached — they are fast to compute and session-dependent.

Public API
----------
get_cached_response(query)           -> dict | None
set_cached_response(query, result)   -> None
invalidate_cache()                   -> None   (call after fresh ingestion)
cache_stats()                        -> dict
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_REDIS_URL:      str | None = os.environ.get("REDIS_URL")
_TTL:            int        = int(os.environ.get("CACHE_TTL_SECONDS",  "3600"))
_MAX_IN_MEMORY:  int        = int(os.environ.get("CACHE_MAX_ENTRIES",  "256"))

# Query classes that must NOT be cached
_NO_CACHE_CLASSES = frozenset({"advisory", "out_of_scope", "pii_risk"})


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def _make_key(query: str) -> str:
    """Return the SHA-256 hex digest of the normalised query."""
    return hashlib.sha256(query.strip().lower().encode()).hexdigest()


# ---------------------------------------------------------------------------
# In-memory LRU cache with TTL
# ---------------------------------------------------------------------------

class _LRUCache:
    """
    Thread-safe-ish (CPython GIL protects dict ops) LRU cache with per-entry TTL.

    Stores (value, expires_at_monotonic) tuples in an OrderedDict.
    Least-recently-used entries are evicted when *maxsize* is reached.
    Expired entries are lazily pruned on access.
    """

    def __init__(self, maxsize: int, ttl: int) -> None:
        self._maxsize = maxsize
        self._ttl     = ttl
        self._store: OrderedDict[str, tuple[dict, float]] = OrderedDict()

    def get(self, key: str) -> dict | None:
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        self._store.move_to_end(key)   # mark as recently used
        return value

    def set(self, key: str, value: dict) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, time.monotonic() + self._ttl)
        # Evict LRU entries when over capacity
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


_local_cache = _LRUCache(maxsize=_MAX_IN_MEMORY, ttl=_TTL)


# ---------------------------------------------------------------------------
# Optional Redis backend
# ---------------------------------------------------------------------------

_redis_client = None
_redis_checked = False


def _redis():
    """
    Lazy-initialise and return a Redis client, or None if unavailable.

    Uses a module-level flag so the connection attempt is made only once.
    Falls back to the in-memory cache silently on any Redis error.
    """
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    if not _REDIS_URL:
        return None
    try:
        import redis as _redis_lib
        client = _redis_lib.from_url(
            _REDIS_URL, decode_responses=True, socket_timeout=2
        )
        client.ping()
        _redis_client = client
    except Exception:
        _redis_client = None
    return _redis_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_cached_response(query: str) -> dict | None:
    """
    Return the cached pipeline result for *query*, or None on cache miss.

    Parameters
    ----------
    query : Raw user query string.  Case and leading/trailing whitespace
            are normalised before key derivation.
    """
    key = _make_key(query)
    r   = _redis()
    if r is not None:
        try:
            raw = r.get(f"mf_faq:{key}")
            return json.loads(raw) if raw else None
        except Exception:
            pass   # Fall through to local cache on Redis error
    return _local_cache.get(key)


def set_cached_response(query: str, result: dict) -> None:
    """
    Cache the pipeline *result* for *query*.

    Refusals (advisory / out_of_scope / pii_risk) and error results are
    deliberately not cached — they are fast to produce and should always
    reflect live classifier output.

    Parameters
    ----------
    query  : Raw user query string.
    result : Dict returned by ``run_query``.
    """
    # Guard: only cache successful factual answers
    if "error" in result:
        return
    if not result.get("answer"):
        return
    if result.get("query_class") in _NO_CACHE_CLASSES:
        return

    key = _make_key(query)
    r   = _redis()
    if r is not None:
        try:
            r.setex(f"mf_faq:{key}", _TTL, json.dumps(result))
            return
        except Exception:
            pass   # Fall through to local cache on Redis error
    _local_cache.set(key, result)


def invalidate_cache() -> None:
    """
    Flush the entire query cache.

    Call this at the end of a successful ingestion run to ensure the
    first query after fresh data is always answered from the vector store.
    """
    _local_cache.clear()
    r = _redis()
    if r is not None:
        try:
            keys = list(r.scan_iter("mf_faq:*"))
            if keys:
                r.delete(*keys)
        except Exception:
            pass


def cache_stats() -> dict:
    """
    Return cache metadata for the /health endpoint and diagnostics.

    Returns
    -------
    dict with keys: backend, entries, ttl_seconds, max_entries
    """
    r       = _redis()
    backend = "redis" if r is not None else "memory"
    if backend == "redis":
        try:
            entries = sum(1 for _ in r.scan_iter("mf_faq:*"))
        except Exception:
            entries = -1
    else:
        entries = _local_cache.size
    return {
        "backend":     backend,
        "entries":     entries,
        "ttl_seconds": _TTL,
        "max_entries": _MAX_IN_MEMORY,
    }
