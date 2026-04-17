"""
phases/phase_3_4_query_pipeline/rewriter.py
--------------------------------------------
Step 3 — Query Rewriter

Normalises a factual query before embedding to improve retrieval recall:

  1. Expands common abbreviations (ELSS, NAV, TER, SIP, AUM, ...)
  2. Normalises HDFC scheme name variants to their canonical full names
     (as stored in chunk metadata)

This is intentionally rule-based — no LLM call — to keep query latency
below 100 ms.  The rewritten query is only used for vector retrieval;
the original query is passed to the LLM prompt unchanged so the answer
sounds natural.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Abbreviation expansions
# ---------------------------------------------------------------------------
# Each entry: (compiled regex, replacement string)
# Applied in order; case-insensitive matching.

_ABBREVIATIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bELSS\b', re.IGNORECASE),
     'Equity Linked Savings Scheme ELSS'),
    (re.compile(r'\bNAV\b', re.IGNORECASE),
     'Net Asset Value NAV'),
    (re.compile(r'\bTER\b', re.IGNORECASE),
     'Total Expense Ratio TER'),
    (re.compile(r'\bSIP\b', re.IGNORECASE),
     'Systematic Investment Plan SIP'),
    (re.compile(r'\bAUM\b', re.IGNORECASE),
     'Assets Under Management AUM'),
    (re.compile(r'\bAMC\b', re.IGNORECASE),
     'Asset Management Company AMC'),
    (re.compile(r'\bSEBI\b', re.IGNORECASE),
     'Securities and Exchange Board of India SEBI'),
    (re.compile(r'\bAMFI\b', re.IGNORECASE),
     'Association of Mutual Funds in India AMFI'),
    (re.compile(r'\bKIM\b', re.IGNORECASE),
     'Key Information Memorandum KIM'),
    (re.compile(r'\bSID\b', re.IGNORECASE),
     'Scheme Information Document SID'),
    (re.compile(r'\b80C\b', re.IGNORECASE),
     'Section 80C tax deduction'),
]

# ---------------------------------------------------------------------------
# Scheme name normalisation
# ---------------------------------------------------------------------------
# Maps user shorthand → canonical scheme_name stored in chunk metadata.
# Applied after abbreviation expansion.

_SCHEME_ALIASES: list[tuple[re.Pattern, str]] = [
    # HDFC Large Cap Fund  (full name + LC shorthand)
    (re.compile(r'\bhdfc\s+large\s+cap\b', re.IGNORECASE),
     'HDFC Large Cap Fund Direct Growth'),
    (re.compile(r'\bhdfc\s+lc\b', re.IGNORECASE),
     'HDFC Large Cap Fund Direct Growth'),
    # HDFC Equity Fund (also known as Flexi Cap)  + EQ shorthand
    (re.compile(r'\bhdfc\s+flexi[\s\-]?cap\b', re.IGNORECASE),
     'HDFC Equity Fund Direct Growth'),
    (re.compile(r'\bhdfc\s+equity\b', re.IGNORECASE),
     'HDFC Equity Fund Direct Growth'),
    (re.compile(r'\bhdfc\s+eq\b', re.IGNORECASE),
     'HDFC Equity Fund Direct Growth'),
    # HDFC ELSS Tax Saver Fund
    (re.compile(r'\bhdfc\s+(elss|tax\s+saver)\b', re.IGNORECASE),
     'HDFC ELSS Tax Saver Fund Direct Plan Growth'),
    # HDFC Mid-Cap Fund  + MC shorthand
    (re.compile(r'\bhdfc\s+mid[\s\-]?cap\b', re.IGNORECASE),
     'HDFC Mid-Cap Fund Direct Growth'),
    (re.compile(r'\bhdfc\s+mc\b', re.IGNORECASE),
     'HDFC Mid-Cap Fund Direct Growth'),
    # HDFC Focused Fund
    (re.compile(r'\bhdfc\s+focused\b', re.IGNORECASE),
     'HDFC Focused Fund Direct Growth'),
]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def rewrite_query(query: str) -> str:
    """
    Expand abbreviations and normalise scheme names in the query.

    Parameters
    ----------
    query : Original user query (already classified as factual).

    Returns
    -------
    Rewritten query string for use in vector retrieval.
    The original query is preserved separately for the LLM prompt.
    """
    result = query

    # Scheme normalisation FIRST — before abbreviations can expand ELSS/NAV/etc.
    # into multi-word strings that would break scheme-name regex matching.
    for pattern, replacement in _SCHEME_ALIASES:
        result = pattern.sub(replacement, result)

    for pattern, replacement in _ABBREVIATIONS:
        result = pattern.sub(replacement, result)

    return result
