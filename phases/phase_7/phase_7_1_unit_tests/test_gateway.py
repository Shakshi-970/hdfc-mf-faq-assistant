"""
phases/phase_7/phase_7_1_unit_tests/test_gateway.py
-----------------------------------------------------
Unit tests for the Phase 10 API Gateway components:
  - SlidingWindowCounter  (rate limiting)
  - Response cache        (get/set/miss/hit/no-cache rules)

No API keys, network calls, or running servers required.
Run: pytest phases/phase_7/phase_7_1_unit_tests/test_gateway.py -v
"""

import pytest

from phases.phase_10.phase_10_2_rate_limiting.middleware import SlidingWindowCounter
from phases.phase_10.phase_10_3_request_cache.cache import (
    _local_cache,
    get_cached_response,
    set_cached_response,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _factual(answer: str = "The expense ratio is 1.09%.") -> dict:
    """Minimal factual result dict that should be cached."""
    return {
        "answer": answer,
        "query_class": "factual",
        "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
        "last_updated": "2026-04-16",
        "llm_provider": "groq/llama-3.3-70b-versatile",
    }


# Clear the in-memory cache before each test so tests are fully isolated.
@pytest.fixture(autouse=True)
def clear_cache():
    _local_cache.clear()
    yield
    _local_cache.clear()


# ---------------------------------------------------------------------------
# SlidingWindowCounter — rate limiter
# ---------------------------------------------------------------------------

class TestSlidingWindowCounter:
    def test_first_request_allowed(self):
        c = SlidingWindowCounter(5, 60.0)
        allowed, _ = c.is_allowed("sess-1")
        assert allowed is True

    def test_allows_up_to_limit(self):
        c = SlidingWindowCounter(3, 60.0)
        for _ in range(3):
            allowed, _ = c.is_allowed("key")
            assert allowed is True

    def test_blocks_when_limit_exceeded(self):
        c = SlidingWindowCounter(3, 60.0)
        for _ in range(3):
            c.is_allowed("key")
        allowed, remaining = c.is_allowed("key")
        assert allowed is False
        assert remaining == 0

    def test_remaining_decrements_with_each_request(self):
        c = SlidingWindowCounter(5, 60.0)
        _, r1 = c.is_allowed("key")
        _, r2 = c.is_allowed("key")
        _, r3 = c.is_allowed("key")
        assert r1 > r2 > r3

    def test_different_keys_are_independent(self):
        c = SlidingWindowCounter(1, 60.0)
        allowed_a, _ = c.is_allowed("session-A")
        allowed_b, _ = c.is_allowed("session-B")
        assert allowed_a is True
        assert allowed_b is True

    def test_limit_of_one(self):
        c = SlidingWindowCounter(1, 60.0)
        allowed, _ = c.is_allowed("k")
        assert allowed is True
        allowed, _ = c.is_allowed("k")
        assert allowed is False

    def test_returns_tuple_of_two(self):
        c = SlidingWindowCounter(5, 60.0)
        result = c.is_allowed("key")
        assert isinstance(result, tuple)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Response cache — cache miss
# ---------------------------------------------------------------------------

class TestCacheMiss:
    def test_miss_on_unknown_query(self):
        assert get_cached_response("__totally_unique_query_xyz_987__") is None

    def test_miss_before_any_set(self):
        assert get_cached_response("What is the NAV of HDFC Equity?") is None


# ---------------------------------------------------------------------------
# Response cache — cache hit
# ---------------------------------------------------------------------------

class TestCacheHit:
    def test_hit_after_set(self):
        result = _factual()
        set_cached_response("expense ratio hdfc large cap unique_001", result)
        assert get_cached_response("expense ratio hdfc large cap unique_001") == result

    def test_case_insensitive_key(self):
        result = _factual("The TER is 0.77%.")
        set_cached_response("HDFC Large Cap TER unique_002", result)
        assert get_cached_response("hdfc large cap ter unique_002") == result

    def test_whitespace_normalised(self):
        result = _factual("The minimum SIP is ₹100.")
        set_cached_response("  min sip hdfc unique_003  ", result)
        assert get_cached_response("min sip hdfc unique_003") == result

    def test_different_queries_do_not_collide(self):
        r1 = _factual("Answer one.")
        r2 = _factual("Answer two.")
        set_cached_response("query alpha unique_004", r1)
        set_cached_response("query beta unique_005", r2)
        assert get_cached_response("query alpha unique_004") == r1
        assert get_cached_response("query beta unique_005") == r2


# ---------------------------------------------------------------------------
# Response cache — no-cache rules
# ---------------------------------------------------------------------------

class TestNoCacheRules:
    def test_advisory_not_cached(self):
        result = {"answer": "refusal text", "query_class": "advisory"}
        set_cached_response("should i invest unique_006", result)
        assert get_cached_response("should i invest unique_006") is None

    def test_out_of_scope_not_cached(self):
        result = {"answer": "out of scope text", "query_class": "out_of_scope"}
        set_cached_response("what is bitcoin unique_007", result)
        assert get_cached_response("what is bitcoin unique_007") is None

    def test_pii_risk_not_cached(self):
        result = {"answer": "pii refusal", "query_class": "pii_risk"}
        set_cached_response("my pan is ABCDE1234F unique_008", result)
        assert get_cached_response("my pan is ABCDE1234F unique_008") is None

    def test_error_result_not_cached(self):
        result = {"error": "service unavailable"}
        set_cached_response("expense ratio unique_009", result)
        assert get_cached_response("expense ratio unique_009") is None

    def test_empty_answer_not_cached(self):
        result = {"answer": "", "query_class": "factual"}
        set_cached_response("empty answer unique_010", result)
        assert get_cached_response("empty answer unique_010") is None
