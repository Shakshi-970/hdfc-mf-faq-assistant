"""
phases/phase_7/phase_7_1_unit_tests/test_security.py
-----------------------------------------------------
Unit tests for Phase 11 — Security and Privacy Controls (Section 11,
docs/rag-architecture.md).

Tests:
  - Domain whitelist: validate_url() rejects non-HTTPS, wrong domain, non-corpus URLs
  - Domain whitelist: validate_url() accepts all 5 corpus URLs
  - is_corpus_url(): True for corpus URLs, False otherwise
  - Audit log: log_query_event() emits session_id + class, NEVER query text
  - Audit log: log_session_event() emits event + session_id
  - Audit log: log_rewrite_event() emits boolean flag, not rewritten text

No API keys or network calls required.
Run: pytest phases/phase_7/phase_7_1_unit_tests/test_security.py -v
"""

import io
import logging

import pytest

from phases.phase_11.phase_11_1_security.domain_whitelist import (
    ALLOWED_DOMAIN,
    CORPUS_URLS,
    is_corpus_url,
    validate_url,
)
from phases.phase_11.phase_11_1_security.audit_log import (
    log_query_event,
    log_rewrite_event,
    log_session_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_log(func, *args, **kwargs) -> str:
    """Call func and return everything it writes to the given logger as a string."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    # Use the root logger so we catch everything regardless of module name
    root = logging.getLogger()
    root.addHandler(handler)
    old_level = root.level
    root.setLevel(logging.DEBUG)
    try:
        func(*args, **kwargs)
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
    return stream.getvalue()


_TEST_LOGGER = logging.getLogger("test.security")

# ---------------------------------------------------------------------------
# validate_url — blocked cases
# ---------------------------------------------------------------------------

class TestValidateUrlBlocked:
    def test_rejects_http_scheme(self):
        with pytest.raises(ValueError, match="non-HTTPS"):
            validate_url("http://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth")

    def test_rejects_ftp_scheme(self):
        with pytest.raises(ValueError):
            validate_url("ftp://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth")

    def test_rejects_wrong_domain(self):
        with pytest.raises(ValueError, match="not whitelisted"):
            validate_url("https://example.com/mutual-funds/hdfc-large-cap")

    def test_rejects_amfiindia(self):
        with pytest.raises(ValueError, match="not whitelisted"):
            validate_url("https://www.amfiindia.com/some-page")

    def test_rejects_groww_url_not_in_corpus(self):
        # A valid groww.in URL but NOT one of the 5 authorised scheme pages
        with pytest.raises(ValueError, match="corpus whitelist"):
            validate_url("https://groww.in/mutual-funds/some-other-scheme")

    def test_rejects_groww_homepage(self):
        with pytest.raises(ValueError, match="corpus whitelist"):
            validate_url("https://groww.in/")

    def test_error_message_contains_rejected_url(self):
        bad = "https://groww.in/mutual-funds/unknown-scheme"
        with pytest.raises(ValueError) as exc_info:
            validate_url(bad)
        assert bad in str(exc_info.value)


# ---------------------------------------------------------------------------
# validate_url — allowed cases (all 5 corpus URLs)
# ---------------------------------------------------------------------------

class TestValidateUrlAllowed:
    @pytest.mark.parametrize("url", sorted(CORPUS_URLS))
    def test_accepts_all_corpus_urls(self, url: str):
        # Must not raise
        validate_url(url)

    def test_accepts_url_with_trailing_slash(self):
        url = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth/"
        validate_url(url)   # trailing slash normalised away


# ---------------------------------------------------------------------------
# is_corpus_url
# ---------------------------------------------------------------------------

class TestIsCorpusUrl:
    @pytest.mark.parametrize("url", sorted(CORPUS_URLS))
    def test_true_for_all_corpus_urls(self, url: str):
        assert is_corpus_url(url) is True

    def test_false_for_unknown_scheme(self):
        assert is_corpus_url("https://groww.in/mutual-funds/unknown") is False

    def test_false_for_wrong_domain(self):
        assert is_corpus_url("https://example.com/anything") is False

    def test_true_with_trailing_slash(self):
        url = list(CORPUS_URLS)[0] + "/"
        assert is_corpus_url(url) is True

    def test_false_for_empty_string(self):
        assert is_corpus_url("") is False

    def test_allowed_domain_constant(self):
        assert ALLOWED_DOMAIN == "groww.in"


# ---------------------------------------------------------------------------
# audit_log — log_query_event (no query text in output)
# ---------------------------------------------------------------------------

class TestLogQueryEvent:
    def test_contains_session_id(self):
        output = _capture_log(
            log_query_event, _TEST_LOGGER, "sess-abc123", "factual"
        )
        assert "sess-abc123" in output

    def test_contains_query_class(self):
        output = _capture_log(
            log_query_event, _TEST_LOGGER, "sess-xyz", "advisory"
        )
        assert "advisory" in output

    def test_contains_provider_when_given(self):
        output = _capture_log(
            log_query_event, _TEST_LOGGER, "sess-1", "factual",
            provider="groq/llama-3.3-70b-versatile",
        )
        assert "groq/llama-3.3-70b-versatile" in output

    def test_contains_latency_when_given(self):
        output = _capture_log(
            log_query_event, _TEST_LOGGER, "sess-2", "factual", latency_ms=312
        )
        assert "312" in output

    def test_never_accepts_query_parameter(self):
        """log_query_event must not have a query parameter — by design."""
        import inspect
        sig = inspect.signature(log_query_event)
        assert "query" not in sig.parameters

    def test_cache_hit_flag_present(self):
        output = _capture_log(
            log_query_event, _TEST_LOGGER, "sess-3", "factual", cache_hit=True
        )
        assert "cache_hit=True" in output

    def test_cache_miss_flag_present(self):
        output = _capture_log(
            log_query_event, _TEST_LOGGER, "sess-4", "factual", cache_hit=False
        )
        assert "cache_hit=False" in output


# ---------------------------------------------------------------------------
# audit_log — log_session_event
# ---------------------------------------------------------------------------

class TestLogSessionEvent:
    def test_contains_event_type(self):
        output = _capture_log(
            log_session_event, _TEST_LOGGER, "created", "sess-111"
        )
        assert "created" in output

    def test_contains_session_id(self):
        output = _capture_log(
            log_session_event, _TEST_LOGGER, "deleted", "sess-222"
        )
        assert "sess-222" in output


# ---------------------------------------------------------------------------
# audit_log — log_rewrite_event (boolean only, no text)
# ---------------------------------------------------------------------------

class TestLogRewriteEvent:
    def test_logs_when_rewritten_true(self):
        output = _capture_log(
            log_rewrite_event, _TEST_LOGGER, "sess-rw1", True
        )
        assert "query_rewritten=true" in output

    def test_no_output_when_rewritten_false(self):
        output = _capture_log(
            log_rewrite_event, _TEST_LOGGER, "sess-rw2", False
        )
        # Nothing should be logged when no rewrite occurred
        assert output == ""

    def test_never_accepts_rewritten_text_parameter(self):
        import inspect
        sig = inspect.signature(log_rewrite_event)
        # Only session_id and rewritten (bool) — no text parameter
        assert "text" not in sig.parameters
        assert "query" not in sig.parameters
