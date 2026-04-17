"""
phases/phase_7/phase_7_1_unit_tests/test_pipeline.py
-----------------------------------------------------
Unit tests for the Phase 6 query pipeline.

The retriever (Chroma Cloud) and LLM (Groq/Claude) are mocked so that
all tests run without any API keys or network access.

Tests cover:
  - Refusal paths: advisory, pii_risk, out_of_scope (no LLM call made)
  - Factual path: LLM is called with correct system prompt + messages
  - Empty retrieval: graceful no-info response
  - Session not found: error dict returned
  - Response structure: all required keys present

Run: pytest phases/phase_7/phase_7_1_unit_tests/test_pipeline.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from phases.phase_3.phase_3_5_session_manager import create_session
from phases.phase_6.phase_6_1_groq_pipeline.pipeline import run_query

# ---------------------------------------------------------------------------
# Shared fixtures / constants
# ---------------------------------------------------------------------------

_MOCK_CHUNK = {
    "text": (
        "The expense ratio of HDFC Large Cap Fund Direct Growth is 0.77% per annum."
    ),
    "metadata": {
        "source_url": "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
        "scheme_name": "HDFC Large Cap Fund Direct Growth",
        "field_type": "expense_ratio",
        "ingestion_date": "2026-04-16",
    },
    "score": 0.95,
}

_MOCK_ANSWER = (
    "The expense ratio of HDFC Large Cap Fund Direct Growth is 0.77% per annum.\n\n"
    "Source: https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth\n\n"
    "Last updated from sources: 2026-04-16"
)


def _mock_llm(answer: str = _MOCK_ANSWER) -> MagicMock:
    """Return a mock LLMClient whose generate() returns `answer`."""
    m = MagicMock()
    m.provider_name = "test/mock-model"
    m.generate.return_value = answer
    return m


# ---------------------------------------------------------------------------
# Refusal paths — no LLM or retriever should be called
# ---------------------------------------------------------------------------

class TestRefusalPaths:
    def test_advisory_query_refused(self):
        sid = create_session()
        result = run_query(sid, "Should I invest in HDFC ELSS?")
        assert result["query_class"] == "advisory"
        assert "error" not in result
        answer = result["answer"].lower()
        assert "investment advice" in answer or "facts only" in answer

    def test_pii_query_refused(self):
        sid = create_session()
        result = run_query(sid, "My PAN is ABCDE1234F what is NAV?")
        assert result["query_class"] == "pii_risk"
        assert "error" not in result
        answer = result["answer"].lower()
        assert "personal information" in answer or "security" in answer

    def test_out_of_scope_refused(self):
        sid = create_session()
        result = run_query(sid, "What is the price of Bitcoin?")
        assert result["query_class"] == "out_of_scope"
        assert "error" not in result

    def test_advisory_does_not_call_llm(self):
        sid = create_session()
        llm = _mock_llm()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline._llm", llm):
            run_query(sid, "Which fund should I buy?")
        llm.generate.assert_not_called()

    def test_pii_does_not_call_llm(self):
        sid = create_session()
        llm = _mock_llm()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline._llm", llm):
            run_query(sid, "My Aadhaar is 123456789012")
        llm.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Session handling
# ---------------------------------------------------------------------------

class TestSessionHandling:
    def test_missing_session_returns_error(self):
        result = run_query("non-existent-uuid-session", "What is the NAV?")
        assert "error" in result
        assert "session" in result["error"].lower()

    def test_valid_session_is_accepted(self):
        sid = create_session()
        llm = _mock_llm()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline.retrieve",
                   return_value=[_MOCK_CHUNK]), \
             patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline._llm", llm):
            result = run_query(sid, "What is the expense ratio of HDFC Large Cap Fund?")
        assert "error" not in result


# ---------------------------------------------------------------------------
# Factual pipeline — mocked retriever + LLM
# ---------------------------------------------------------------------------

class TestFactualPipeline:
    def test_answer_returned_for_factual_query(self):
        sid = create_session()
        llm = _mock_llm()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline.retrieve",
                   return_value=[_MOCK_CHUNK]), \
             patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline._llm", llm):
            result = run_query(sid, "What is the expense ratio of HDFC Large Cap Fund?")

        assert result["answer"] == _MOCK_ANSWER
        assert result["query_class"] == "factual"
        assert result["source_url"] == _MOCK_CHUNK["metadata"]["source_url"]
        assert result["last_updated"] == "2026-04-16"

    def test_llm_called_once_per_factual_query(self):
        sid = create_session()
        llm = _mock_llm()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline.retrieve",
                   return_value=[_MOCK_CHUNK]), \
             patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline._llm", llm):
            run_query(sid, "What is the expense ratio of HDFC Large Cap Fund?")

        llm.generate.assert_called_once()

    def test_llm_receives_system_prompt_and_messages(self):
        sid = create_session()
        llm = _mock_llm()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline.retrieve",
                   return_value=[_MOCK_CHUNK]), \
             patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline._llm", llm):
            run_query(sid, "What is the expense ratio of HDFC Large Cap Fund?")

        args, _ = llm.generate.call_args
        system_prompt, messages = args
        # System prompt must contain facts-only instructions
        assert "facts" in system_prompt.lower() or "mutual fund" in system_prompt.lower()
        # Messages must be a list with at least one user turn
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"
        # Context block must include chunk text
        assert _MOCK_CHUNK["text"] in messages[0]["content"]

    def test_empty_retrieval_returns_no_info_message(self):
        sid = create_session()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline.retrieve",
                   return_value=[]):
            result = run_query(sid, "What is the expense ratio of HDFC Large Cap Fund?")

        assert "error" not in result
        assert result["answer"]   # some message returned
        # LLM should NOT be called when no chunks retrieved
        answer_lower = result["answer"].lower()
        assert "could not find" in answer_lower or "no relevant" in answer_lower \
            or "check the groww" in answer_lower

    def test_response_contains_llm_provider(self):
        sid = create_session()
        llm = _mock_llm()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline.retrieve",
                   return_value=[_MOCK_CHUNK]), \
             patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline._llm", llm):
            result = run_query(sid, "What is the expense ratio of HDFC Large Cap Fund?")

        assert result.get("llm_provider") == "test/mock-model"

    def test_retriever_error_returns_service_unavailable(self):
        sid = create_session()
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline.retrieve",
                   side_effect=Exception("Chroma Cloud unreachable")):
            result = run_query(sid, "What is the expense ratio of HDFC Large Cap Fund?")

        assert "error" in result
        assert "unavailable" in result["error"].lower() or "retrieval" in result["error"].lower()

    def test_llm_error_returns_service_unavailable(self):
        sid = create_session()
        llm = _mock_llm()
        llm.generate.side_effect = Exception("Groq API timeout")
        with patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline.retrieve",
                   return_value=[_MOCK_CHUNK]), \
             patch("phases.phase_6.phase_6_1_groq_pipeline.pipeline._llm", llm):
            result = run_query(sid, "What is the expense ratio of HDFC Large Cap Fund?")

        assert "error" in result
        assert "unavailable" in result["error"].lower()
