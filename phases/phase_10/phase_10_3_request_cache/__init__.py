"""
phases/phase_10/phase_10_3_request_cache
-----------------------------------------
Query response cache — avoids redundant LLM + Chroma round-trips for
identical repeated questions within the same ingestion cycle.

Public API
----------
from phases.phase_10.phase_10_3_request_cache.cache import (
    get_cached_response,
    set_cached_response,
    invalidate_cache,
    cache_stats,
)
"""
