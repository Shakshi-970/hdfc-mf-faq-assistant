"""
phases/phase_7/phase_7_1_unit_tests/test_clarification.py
----------------------------------------------------------
Unit tests for Phase 12 — Known Limitations Mitigations (Section 12,
docs/rag-architecture.md).

Tests:
  - detect_ambiguous_schemes(): returns all 5 when "hdfc" present but no
    scheme-specific term; returns [] when specific term present; returns []
    when "hdfc" absent
  - is_realtime_nav_query(): True for "today's NAV", "current NAV", etc.;
    False for plain NAV or freshness-only queries
  - clarification_message(): lists all candidate schemes, contains example
  - nav_redirect_message(): contains URL when scheme provided; contains all 5
    URLs when no scheme; contains freshness warning

No API keys or network calls required.
Run: pytest phases/phase_7/phase_7_1_unit_tests/test_clarification.py -v
"""

import pytest

from phases.phase_12.phase_12_1_clarification.scheme_resolver import (
    SCHEME_NAMES,
    SCHEME_URLS,
    clarification_message,
    detect_ambiguous_schemes,
    is_realtime_nav_query,
    nav_redirect_message,
)


# ---------------------------------------------------------------------------
# detect_ambiguous_schemes — ambiguous cases (hdfc + no scheme specifier)
# ---------------------------------------------------------------------------

class TestDetectAmbiguousAmbiguousCases:
    def test_hdfc_fund_alone(self):
        result = detect_ambiguous_schemes("What is the expense ratio of HDFC fund?")
        assert len(result) == 5

    def test_hdfc_mutual_fund_generic(self):
        result = detect_ambiguous_schemes("Tell me about HDFC mutual fund")
        assert len(result) == 5

    def test_hdfc_scheme_no_specifier(self):
        result = detect_ambiguous_schemes("What is the exit load of this HDFC scheme?")
        assert len(result) == 5

    def test_returns_all_scheme_names(self):
        result = detect_ambiguous_schemes("What is the NAV of HDFC?")
        for name in SCHEME_NAMES:
            assert name in result

    def test_hdfc_uppercase(self):
        result = detect_ambiguous_schemes("HDFC fund expense ratio?")
        assert len(result) == 5

    def test_hdfc_mixed_case(self):
        result = detect_ambiguous_schemes("Hdfc Fund details")
        assert len(result) == 5


# ---------------------------------------------------------------------------
# detect_ambiguous_schemes — unambiguous cases (specific scheme term present)
# ---------------------------------------------------------------------------

class TestDetectAmbiguousUnambiguousCases:
    def test_large_cap_term(self):
        assert detect_ambiguous_schemes("What is the NAV of HDFC Large Cap fund?") == []

    def test_large_cap_hyphenated(self):
        assert detect_ambiguous_schemes("HDFC large-cap expense ratio") == []

    def test_elss_term(self):
        assert detect_ambiguous_schemes("What is the lock-in period for HDFC ELSS?") == []

    def test_tax_saver_term(self):
        assert detect_ambiguous_schemes("Tell me about HDFC tax saver fund") == []

    def test_mid_cap_term(self):
        assert detect_ambiguous_schemes("HDFC mid cap fund minimum SIP") == []

    def test_mid_cap_hyphenated(self):
        assert detect_ambiguous_schemes("HDFC mid-cap NAV") == []

    def test_focused_fund_term(self):
        assert detect_ambiguous_schemes("HDFC focused fund exit load") == []

    def test_equity_fund_term(self):
        assert detect_ambiguous_schemes("HDFC equity fund benchmark") == []

    def test_80c_term(self):
        assert detect_ambiguous_schemes("Does HDFC fund qualify for 80c?") == []

    def test_flexi_cap_term(self):
        assert detect_ambiguous_schemes("HDFC flexi cap fund manager") == []


# ---------------------------------------------------------------------------
# detect_ambiguous_schemes — no hdfc mention (not ambiguous in scheme sense)
# ---------------------------------------------------------------------------

class TestDetectAmbiguousNoHdfc:
    def test_no_hdfc_plain_question(self):
        assert detect_ambiguous_schemes("What is the expense ratio?") == []

    def test_no_hdfc_general_mf_question(self):
        assert detect_ambiguous_schemes("What is an exit load in mutual funds?") == []

    def test_empty_string(self):
        assert detect_ambiguous_schemes("") == []

    def test_unrelated_query(self):
        assert detect_ambiguous_schemes("What is the weather today?") == []

    def test_other_amc(self):
        assert detect_ambiguous_schemes("What is the Axis Bluechip fund NAV?") == []


# ---------------------------------------------------------------------------
# is_realtime_nav_query — positive cases (NAV + freshness term)
# ---------------------------------------------------------------------------

class TestIsRealtimeNavQueryPositive:
    def test_todays_nav(self):
        assert is_realtime_nav_query("What is today's NAV?") is True

    def test_current_nav(self):
        assert is_realtime_nav_query("What is the current NAV of HDFC Large Cap?") is True

    def test_live_nav(self):
        assert is_realtime_nav_query("Live NAV of HDFC Equity Fund") is True

    def test_latest_nav(self):
        assert is_realtime_nav_query("What is the latest NAV?") is True

    def test_now_nav(self):
        assert is_realtime_nav_query("NAV now for HDFC Mid Cap") is True

    def test_real_time_nav(self):
        assert is_realtime_nav_query("What is the real-time NAV?") is True

    def test_net_asset_value_today(self):
        assert is_realtime_nav_query("What is today's net asset value?") is True

    def test_current_net_asset_value(self):
        assert is_realtime_nav_query("Current net asset value for HDFC ELSS") is True


# ---------------------------------------------------------------------------
# is_realtime_nav_query — negative cases
# ---------------------------------------------------------------------------

class TestIsRealtimeNavQueryNegative:
    def test_nav_without_freshness(self):
        assert is_realtime_nav_query("What is the NAV of HDFC Large Cap?") is False

    def test_freshness_without_nav(self):
        assert is_realtime_nav_query("What is the current expense ratio?") is False

    def test_empty_string(self):
        assert is_realtime_nav_query("") is False

    def test_general_question(self):
        assert is_realtime_nav_query("What is a NAV in mutual funds?") is False

    def test_historical_nav(self):
        assert is_realtime_nav_query("What was the NAV last year?") is False


# ---------------------------------------------------------------------------
# clarification_message — content checks
# ---------------------------------------------------------------------------

class TestClarificationMessage:
    def test_contains_all_five_scheme_names(self):
        msg = clarification_message(list(SCHEME_NAMES))
        for name in SCHEME_NAMES:
            assert name in msg

    def test_contains_example_query(self):
        msg = clarification_message(list(SCHEME_NAMES))
        assert "expense ratio" in msg.lower() or "example" in msg.lower() or "for example" in msg.lower()

    def test_contains_clarification_prompt(self):
        msg = clarification_message(list(SCHEME_NAMES))
        # Must ask the user to specify which scheme
        assert any(word in msg.lower() for word in ("specify", "which", "mean", "scheme"))

    def test_partial_list(self):
        # Two schemes mentioned (comparison) — both should appear
        subset = [
            "HDFC Large Cap Fund (Direct Growth)",
            "HDFC Mid-Cap Fund (Direct Growth)",
        ]
        msg = clarification_message(subset)
        assert "HDFC Large Cap Fund (Direct Growth)" in msg
        assert "HDFC Mid-Cap Fund (Direct Growth)" in msg

    def test_fallback_to_all_when_empty(self):
        msg = clarification_message([])
        for name in SCHEME_NAMES:
            assert name in msg

    def test_numbered_list(self):
        msg = clarification_message(list(SCHEME_NAMES))
        assert "1." in msg
        assert "5." in msg


# ---------------------------------------------------------------------------
# nav_redirect_message — content checks
# ---------------------------------------------------------------------------

class TestNavRedirectMessage:
    def test_contains_url_when_scheme_provided(self):
        scheme = "HDFC Large Cap Fund (Direct Growth)"
        url = SCHEME_URLS[scheme]
        msg = nav_redirect_message(scheme)
        assert url in msg

    def test_contains_scheme_name_when_provided(self):
        scheme = "HDFC ELSS Tax Saver Fund (Direct Plan Growth)"
        msg = nav_redirect_message(scheme)
        assert scheme in msg

    def test_contains_freshness_warning(self):
        msg = nav_redirect_message("HDFC Large Cap Fund (Direct Growth)")
        assert any(
            w in msg.lower()
            for w in ("once per day", "daily", "stale", "not reflect")
        )

    def test_generic_message_when_no_scheme(self):
        msg = nav_redirect_message(None)
        for url in SCHEME_URLS.values():
            assert url in msg

    def test_generic_message_contains_all_scheme_names(self):
        msg = nav_redirect_message(None)
        for name in SCHEME_NAMES:
            assert name in msg

    def test_unknown_scheme_falls_back_to_generic(self):
        msg = nav_redirect_message("Some Unknown Fund")
        # Unknown scheme → generic message listing all 5
        for url in SCHEME_URLS.values():
            assert url in msg

    def test_generic_message_contains_freshness_warning(self):
        msg = nav_redirect_message(None)
        assert any(
            w in msg.lower()
            for w in ("once per day", "daily", "not reflect")
        )


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------

class TestConstants:
    def test_scheme_names_count(self):
        assert len(SCHEME_NAMES) == 5

    def test_scheme_urls_count(self):
        assert len(SCHEME_URLS) == 5

    def test_all_urls_https(self):
        for url in SCHEME_URLS.values():
            assert url.startswith("https://")

    def test_all_urls_groww_domain(self):
        for url in SCHEME_URLS.values():
            assert "groww.in" in url

    def test_scheme_names_match_urls_keys(self):
        assert set(SCHEME_NAMES) == set(SCHEME_URLS.keys())
