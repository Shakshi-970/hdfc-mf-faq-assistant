"""
phases/phase_7/phase_7_1_unit_tests/test_formatter.py
------------------------------------------------------
Unit tests for the response formatter and post-generation guardrail.

Tests:
  - Sentence capping (1, 2, 3, 4+ sentences → body kept to max 3)
  - Source injection (missing / already present / duplicate removed)
  - Footer injection (missing / already present / replaced / omitted)
  - Full format_response output structure
  - Advisory phrase detection (sanitize_output)
  - Clean text passes through unchanged
  - Source / footer preserved when guardrail fires

No API keys or network calls required.
Run: pytest phases/phase_7/phase_7_1_unit_tests/test_formatter.py -v
"""

import pytest

from phases.phase_8.phase_8_1_response_formatter.formatter import format_response
from phases.phase_8.phase_8_1_response_formatter.guardrail import sanitize_output

_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
_DATE = "2026-04-16"


# ---------------------------------------------------------------------------
# format_response — sentence capping
# ---------------------------------------------------------------------------

class TestSentenceCap:
    def test_three_sentences_kept(self):
        body = "Sentence one. Sentence two. Sentence three."
        result = format_response(body, _URL, _DATE)
        assert result.startswith("Sentence one. Sentence two. Sentence three.")

    def test_four_sentences_truncated_to_three(self):
        body = "One. Two. Three. Four."
        result = format_response(body, _URL, _DATE)
        # "Four" must be absent from the body section (before Source:)
        body_part = result.split("Source:")[0]
        assert "Four" not in body_part

    def test_four_sentences_first_three_present(self):
        body = "One. Two. Three. Four."
        result = format_response(body, _URL, _DATE)
        body_part = result.split("Source:")[0]
        assert "One." in body_part
        assert "Three." in body_part

    def test_one_sentence_kept(self):
        body = "Only one sentence here."
        result = format_response(body, _URL, _DATE)
        assert result.startswith("Only one sentence here.")

    def test_two_sentences_both_kept(self):
        body = "First sentence. Second sentence."
        result = format_response(body, _URL, _DATE)
        assert "First sentence" in result
        assert "Second sentence" in result


# ---------------------------------------------------------------------------
# format_response — Source injection
# ---------------------------------------------------------------------------

class TestSourceInjection:
    def test_source_line_injected(self):
        result = format_response("Answer text.", _URL, _DATE)
        assert f"Source: {_URL}" in result

    def test_existing_source_replaced(self):
        text = "Answer text.\n\nSource: https://old-url.example.com"
        result = format_response(text, _URL, _DATE)
        assert f"Source: {_URL}" in result
        assert "old-url.example.com" not in result

    def test_exactly_one_source_line(self):
        result = format_response("Answer text.", _URL, _DATE)
        assert result.count("Source:") == 1


# ---------------------------------------------------------------------------
# format_response — footer injection
# ---------------------------------------------------------------------------

class TestFooterInjection:
    def test_footer_injected(self):
        result = format_response("Answer.", _URL, _DATE)
        assert f"Last updated from sources: {_DATE}" in result

    def test_existing_footer_replaced(self):
        text = "Answer.\n\nLast updated from sources: 2020-01-01"
        result = format_response(text, _URL, _DATE)
        assert f"Last updated from sources: {_DATE}" in result
        assert "2020-01-01" not in result

    def test_exactly_one_footer_line(self):
        result = format_response("Answer.", _URL, _DATE)
        assert result.count("Last updated from sources:") == 1

    def test_empty_date_omits_footer(self):
        result = format_response("Answer.", _URL, "")
        assert "Last updated from sources:" not in result


# ---------------------------------------------------------------------------
# format_response — full output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:
    def test_returns_string(self):
        assert isinstance(format_response("Answer.", _URL, _DATE), str)

    def test_non_empty(self):
        assert len(format_response("Answer.", _URL, _DATE)) > 0

    def test_source_appears_after_body(self):
        result = format_response("Answer text.", _URL, _DATE)
        body_pos = result.index("Answer text.")
        source_pos = result.index("Source:")
        assert source_pos > body_pos

    def test_footer_appears_after_source(self):
        result = format_response("Answer text.", _URL, _DATE)
        source_pos = result.index("Source:")
        footer_pos = result.index("Last updated from sources:")
        assert footer_pos > source_pos


# ---------------------------------------------------------------------------
# sanitize_output — advisory detection
# ---------------------------------------------------------------------------

class TestAdvisoryDetection:
    def test_i_recommend_detected(self):
        _, modified = sanitize_output("I recommend investing in this fund.")
        assert modified is True

    def test_you_should_invest_detected(self):
        _, modified = sanitize_output("You should invest in HDFC ELSS for tax savings.")
        assert modified is True

    def test_i_suggest_detected(self):
        _, modified = sanitize_output("I suggest considering this fund.")
        assert modified is True

    def test_consider_investing_detected(self):
        _, modified = sanitize_output("Consider investing a small amount initially.")
        assert modified is True

    def test_body_replaced_with_fallback(self):
        result, _ = sanitize_output("I recommend this fund for growth.")
        assert "verified facts only" in result

    def test_source_preserved_on_sanitize(self):
        text = f"I recommend this fund.\n\nSource: {_URL}"
        result, modified = sanitize_output(text)
        assert modified is True
        assert f"Source: {_URL}" in result

    def test_footer_preserved_on_sanitize(self):
        text = (
            f"I recommend this fund.\n\n"
            f"Source: {_URL}\n\n"
            f"Last updated from sources: {_DATE}"
        )
        result, modified = sanitize_output(text)
        assert modified is True
        assert f"Source: {_URL}" in result
        assert f"Last updated from sources: {_DATE}" in result


# ---------------------------------------------------------------------------
# sanitize_output — clean text passthrough
# ---------------------------------------------------------------------------

class TestCleanPassthrough:
    def test_factual_text_unchanged(self):
        text = "The expense ratio is 1.09%. The fund was launched in 2013."
        result, modified = sanitize_output(text)
        assert modified is False
        assert result == text

    def test_nav_text_unchanged(self):
        text = "The NAV of HDFC Equity Fund is ₹123.45 as of April 2026."
        result, modified = sanitize_output(text)
        assert modified is False

    def test_returns_tuple_of_two(self):
        out = sanitize_output("Some factual text.")
        assert isinstance(out, tuple)
        assert len(out) == 2

    def test_second_element_is_bool(self):
        _, modified = sanitize_output("Some factual text.")
        assert isinstance(modified, bool)
