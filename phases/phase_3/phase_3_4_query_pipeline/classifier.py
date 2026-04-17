"""
phases/phase_3_4_query_pipeline/classifier.py
----------------------------------------------
Step 1 — Query Classifier

Classifies incoming queries into one of four classes:

  factual       — asks for a verifiable fund fact → proceed to retrieval
  advisory      — asks for recommendation/opinion → polite refusal
  out_of_scope  — unrelated to mutual funds       → out-of-scope message
  pii_risk      — contains PAN/Aadhaar/OTP/phone  → security refusal

Classification is rule-based (no LLM call) for low latency and cost.
Precision is favoured over recall for advisory detection — ambiguous
queries are treated as factual to avoid over-refusing.
"""

from __future__ import annotations

import re
from typing import Literal

QueryClass = Literal["factual", "advisory", "out_of_scope", "pii_risk"]

# ---------------------------------------------------------------------------
# PII patterns — checked first, highest priority
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[re.Pattern] = [
    re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),           # PAN card
    re.compile(r'\b\d{12}\b'),                         # Aadhaar (12-digit)
    re.compile(r'\bOTP\b', re.IGNORECASE),             # OTP mention
    re.compile(r'\baccount\s*number\b', re.IGNORECASE),
    re.compile(r'\b\d{16}\b'),                         # card number
]

# ---------------------------------------------------------------------------
# Advisory keywords — explicit recommendation / opinion requests
# ---------------------------------------------------------------------------

_ADVISORY_PHRASES: list[str] = [
    "should i invest",
    "should i buy",
    "should i put",
    "is it worth",
    "is it a good",
    "recommend",
    "which fund",
    "which is better",
    "which is best",
    "best fund",
    "better than",
    "advice",
    "advise",
    "suggest",
    "will it grow",
    "future returns",
    "return prediction",
    "portfolio allocation",
    "how much should i",
    "good investment",
]

# ---------------------------------------------------------------------------
# In-scope signals — any of these present → likely factual
# ---------------------------------------------------------------------------

_FACTUAL_SIGNALS: list[str] = [
    # Scheme names
    "large cap", "equity fund", "elss", "tax saver",
    "mid cap", "mid-cap", "focused fund",
    "hdfc",
    # Field names
    "nav", "net asset value",
    "expense ratio", "ter",
    "exit load",
    "sip", "systematic investment",
    "lumpsum", "lump sum",
    "riskometer", "risk",
    "benchmark",
    "fund manager",
    "aum", "assets under management",
    "lock-in", "lock in", "lockin",
    "tax benefit", "section 80c", "80c",
    "minimum investment", "min investment",
    "category",
    "direct growth",
    # General MF terms
    "mutual fund", "scheme", "fund", "groww",
]

# ---------------------------------------------------------------------------
# Out-of-scope hard exclusions — clearly non-MF topics
# ---------------------------------------------------------------------------

_OFFTOPIC_SIGNALS: list[str] = [
    "cricket", "weather", "recipe", "movie", "restaurant",
    "stock price", "share price", "nifty 50 today", "sensex today",
    "forex", "bitcoin", "crypto",
    "insurance", "fixed deposit", "fd rate",
]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify_query(query: str) -> QueryClass:
    """
    Classify a user query into one of: factual, advisory, out_of_scope, pii_risk.

    Parameters
    ----------
    query : Raw user query string.

    Returns
    -------
    QueryClass literal.
    """
    # --- PII check (highest priority) ---
    for pattern in _PII_PATTERNS:
        if pattern.search(query):
            return "pii_risk"

    q_lower = query.lower()

    # --- Advisory check ---
    if any(phrase in q_lower for phrase in _ADVISORY_PHRASES):
        return "advisory"

    # --- Off-topic hard exclusions ---
    if any(signal in q_lower for signal in _OFFTOPIC_SIGNALS):
        return "out_of_scope"

    # --- In-scope signals → factual ---
    if any(signal in q_lower for signal in _FACTUAL_SIGNALS):
        return "factual"

    # --- Fallback: short queries with question words → treat as factual ---
    # e.g. "what is the expense ratio?" without spelling out a scheme name
    question_words = ("what", "how", "when", "which", "who", "where", "tell me")
    if any(q_lower.strip().startswith(w) for w in question_words):
        return "factual"

    # --- Default: out of scope ---
    return "out_of_scope"
