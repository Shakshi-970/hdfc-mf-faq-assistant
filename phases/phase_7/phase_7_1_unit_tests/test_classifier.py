"""
phases/phase_7/phase_7_1_unit_tests/test_classifier.py
-------------------------------------------------------
Unit tests for the rule-based query classifier.

Tests all four classification outcomes:
  pii_risk     — PAN, Aadhaar, OTP, account/card numbers
  advisory     — recommendation / opinion requests
  out_of_scope — clearly non-mutual-fund topics
  factual      — in-scope, verifiable fund facts

No API keys or network calls required.
Run: pytest phases/phase_7/phase_7_1_unit_tests/test_classifier.py -v
"""

import pytest

from phases.phase_3.phase_3_4_query_pipeline.classifier import classify_query


# ---------------------------------------------------------------------------
# PII detection (highest priority — must fire even if fund terms present)
# ---------------------------------------------------------------------------

class TestPIIDetection:
    def test_pan_card_format(self):
        assert classify_query("My PAN is ABCDE1234F") == "pii_risk"

    def test_pan_card_with_fund_context(self):
        # PAN in otherwise factual query → still pii_risk
        assert classify_query("ABCDE1234F what is the NAV of HDFC fund?") == "pii_risk"

    def test_aadhaar_twelve_digits(self):
        assert classify_query("My Aadhaar is 123456789012") == "pii_risk"

    def test_otp_mention(self):
        assert classify_query("What is my OTP for the transaction?") == "pii_risk"

    def test_account_number_phrase(self):
        assert classify_query("Check my account number for SIP status") == "pii_risk"

    def test_sixteen_digit_card_number(self):
        assert classify_query("My card 4111111111111111 is linked to SIP") == "pii_risk"


# ---------------------------------------------------------------------------
# Advisory queries
# ---------------------------------------------------------------------------

class TestAdvisoryDetection:
    def test_should_i_invest(self):
        assert classify_query("Should I invest in HDFC ELSS?") == "advisory"

    def test_should_i_buy(self):
        assert classify_query("Should I buy HDFC Large Cap Fund?") == "advisory"

    def test_recommend(self):
        assert classify_query("Which fund do you recommend for me?") == "advisory"

    def test_best_fund(self):
        # "best fund" must be a substring — "best mutual fund" does not match
        assert classify_query("Which is the best fund to invest in?") == "advisory"

    def test_which_is_better(self):
        assert classify_query("Which is better — ELSS or Large Cap?") == "advisory"

    def test_good_investment(self):
        assert classify_query("Is HDFC Mid-Cap a good investment?") == "advisory"

    def test_future_returns(self):
        assert classify_query("What will be the future returns of this fund?") == "advisory"

    def test_how_much_should_i(self):
        assert classify_query("How much should I invest in SIP per month?") == "advisory"


# ---------------------------------------------------------------------------
# Out-of-scope queries
# ---------------------------------------------------------------------------

class TestOutOfScope:
    def test_weather(self):
        assert classify_query("What is the weather in Mumbai today?") == "out_of_scope"

    def test_cricket(self):
        assert classify_query("Who won the cricket match yesterday?") == "out_of_scope"

    def test_bitcoin(self):
        assert classify_query("What is the price of Bitcoin?") == "out_of_scope"

    def test_sensex_today(self):
        assert classify_query("What is sensex today?") == "out_of_scope"

    def test_fixed_deposit(self):
        assert classify_query("What is the FD rate at SBI?") == "out_of_scope"

    def test_insurance(self):
        assert classify_query("Tell me about term insurance policies") == "out_of_scope"


# ---------------------------------------------------------------------------
# Factual queries (in-scope)
# ---------------------------------------------------------------------------

class TestFactualClassification:
    def test_expense_ratio(self):
        assert classify_query("What is the expense ratio of HDFC Large Cap Fund?") == "factual"

    def test_nav(self):
        assert classify_query("What is the NAV of HDFC Equity Fund?") == "factual"

    def test_elss_lockin(self):
        assert classify_query("What is the lock-in period for HDFC ELSS?") == "factual"

    def test_exit_load(self):
        assert classify_query("What is the exit load of HDFC Mid-Cap Fund?") == "factual"

    def test_min_sip(self):
        assert classify_query("What is the minimum SIP amount for HDFC Focused Fund?") == "factual"

    def test_benchmark(self):
        assert classify_query("What is the benchmark index of HDFC Large Cap Fund?") == "factual"

    def test_fund_manager(self):
        assert classify_query("Who is the fund manager of HDFC Equity Fund?") == "factual"

    def test_aum(self):
        assert classify_query("What is the AUM of HDFC Mid-Cap Fund?") == "factual"

    def test_section_80c(self):
        assert classify_query("Does HDFC ELSS qualify for 80C tax deduction?") == "factual"

    def test_riskometer(self):
        assert classify_query("What is the risk level of HDFC Focused Fund?") == "factual"


# ---------------------------------------------------------------------------
# Fallback behaviour — question-word queries without explicit scheme names
# ---------------------------------------------------------------------------

class TestFallbackBehaviour:
    def test_what_question_defaults_factual(self):
        assert classify_query("What is the minimum investment amount?") == "factual"

    def test_how_question_defaults_factual(self):
        assert classify_query("How many schemes does HDFC offer?") == "factual"

    def test_tell_me_defaults_factual(self):
        assert classify_query("Tell me about the expense ratio") == "factual"
