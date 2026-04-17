"""
phases/phase_12/phase_12_1_clarification/scheme_resolver.py
------------------------------------------------------------
Ambiguous query resolution — Section 12, Known Limitations Mitigations.

Architecture requirement (Section 12):
  "Ambiguous scheme names — 'HDFC Fund' may match multiple schemes
   → Ask clarifying question or list the 5 in-scope schemes."

  "No real-time NAV — Cannot answer 'what is today's NAV?'
   → Redirect to the Groww scheme page for live NAV."

Two separate concerns are handled here:

1. Ambiguous scheme detection
   A query that mentions "hdfc" but no scheme-specific term (e.g.,
   "What is the expense ratio of HDFC fund?") is ambiguous — it could
   refer to any of the 5 in-scope schemes.  detect_ambiguous_schemes()
   returns the list of candidate scheme names; the pipeline returns a
   clarifying question instead of guessing.

2. Real-time NAV redirect
   Queries that combine a NAV term with a freshness term (e.g.,
   "today's NAV", "current NAV", "live NAV") cannot be answered
   from the scraped corpus, which is only updated once daily.
   is_realtime_nav_query() flags these; nav_redirect_message() tells
   the user where to find the live value.

Public API
----------
detect_ambiguous_schemes(query)  -> list[str]
is_realtime_nav_query(query)     -> bool
clarification_message(matches)   -> str
nav_redirect_message(scheme_name) -> str
SCHEME_NAMES                     -> tuple[str, ...]
SCHEME_URLS                      -> dict[str, str]
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Canonical scheme data (mirrors CORPUS_URLS in domain_whitelist.py)
# ---------------------------------------------------------------------------

SCHEME_NAMES: tuple[str, ...] = (
    "HDFC Large Cap Fund (Direct Growth)",
    "HDFC Equity Fund (Direct Growth)",
    "HDFC ELSS Tax Saver Fund (Direct Plan Growth)",
    "HDFC Mid-Cap Fund (Direct Growth)",
    "HDFC Focused Fund (Direct Growth)",
)

SCHEME_URLS: dict[str, str] = {
    "HDFC Large Cap Fund (Direct Growth)":
        "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    "HDFC Equity Fund (Direct Growth)":
        "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "HDFC ELSS Tax Saver Fund (Direct Plan Growth)":
        "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "HDFC Mid-Cap Fund (Direct Growth)":
        "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "HDFC Focused Fund (Direct Growth)":
        "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth",
}

# ---------------------------------------------------------------------------
# Scheme-specific identifying terms
# A term uniquely identifies one scheme — presence of any term means the
# user is asking about that specific scheme (not ambiguous).
# ---------------------------------------------------------------------------

_SCHEME_IDENTIFIERS: dict[str, list[str]] = {
    "HDFC Large Cap Fund (Direct Growth)": [
        "large cap", "large-cap", "largecap",
    ],
    "HDFC Equity Fund (Direct Growth)": [
        "equity fund", "flexi cap", "flexi-cap", "flexicap",
    ],
    "HDFC ELSS Tax Saver Fund (Direct Plan Growth)": [
        "elss", "tax saver", "tax-saver", "80c", "lock-in", "lock in",
        "tax saving", "section 80c",
    ],
    "HDFC Mid-Cap Fund (Direct Growth)": [
        "mid cap", "mid-cap", "midcap",
    ],
    "HDFC Focused Fund (Direct Growth)": [
        "focused fund", "focused",
    ],
}

# ---------------------------------------------------------------------------
# Real-time NAV detection patterns
# ---------------------------------------------------------------------------

_NAV_RE = re.compile(
    r'\bnav\b|\bnet\s+asset\s+value\b',
    re.IGNORECASE,
)

_FRESHNESS_RE = re.compile(
    r'\btoday\b|\bcurrent\b|\blive\b|\bnow\b|\blatest\b|\breal.?time\b|\btoday\'?s\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def detect_ambiguous_schemes(query: str) -> list[str]:
    """
    Return a list of candidate scheme names when the query is ambiguous.

    A query is considered ambiguous when it explicitly mentions "hdfc"
    but contains none of the scheme-specific identifying terms defined in
    _SCHEME_IDENTIFIERS.  In that case every in-scope scheme is a valid
    candidate and the user should be asked to clarify.

    Returns an empty list when:
    - "hdfc" is not present (query is about general MF concepts — not
      ambiguous in the scheme-name sense)
    - Exactly one scheme-specific term is present (query is unambiguous)

    Parameters
    ----------
    query : str — raw user query text.

    Returns
    -------
    list[str] — canonical scheme names that are candidates, or [] if clear.
    """
    q = query.lower()

    if "hdfc" not in q:
        return []

    matched = [
        name
        for name, terms in _SCHEME_IDENTIFIERS.items()
        if any(t in q for t in terms)
    ]

    # Exactly one scheme identified → unambiguous
    if len(matched) == 1:
        return []

    # No scheme-specific term found → all 5 are candidates
    if len(matched) == 0:
        return list(SCHEME_NAMES)

    # Multiple scheme terms found (e.g., a comparison query) → return matches
    # so the caller can present a clarification if needed
    return matched


def is_realtime_nav_query(query: str) -> bool:
    """
    Return True when the query asks for the current/live/today's NAV.

    The scraper runs once daily so the stored NAV may be up to 24 hours
    stale.  Queries that combine a NAV term with a freshness indicator
    should be redirected to the Groww scheme page.

    Parameters
    ----------
    query : str — raw user query text.

    Returns
    -------
    bool
    """
    return bool(_NAV_RE.search(query) and _FRESHNESS_RE.search(query))


def clarification_message(matches: list[str]) -> str:
    """
    Build a polite clarifying question that lists the candidate schemes.

    Parameters
    ----------
    matches : list[str] — canonical scheme names from detect_ambiguous_schemes().

    Returns
    -------
    str — the clarification response to return to the user.
    """
    if not matches:
        matches = list(SCHEME_NAMES)

    numbered = "\n".join(
        f"  {i + 1}. {name}" for i, name in enumerate(matches)
    )
    return (
        "I can answer questions about the following HDFC Mutual Fund schemes. "
        "Could you specify which one you mean?\n\n"
        + numbered
        + "\n\nFor example: \"What is the expense ratio of HDFC Large Cap Fund?\""
    )


def nav_redirect_message(scheme_name: str | None = None) -> str:
    """
    Build a redirect response for real-time NAV queries.

    The corpus is updated once per day so the stored NAV may be stale.
    This message directs the user to the authoritative Groww page.

    Parameters
    ----------
    scheme_name : str | None — active scheme context from the session,
                  used to include a direct URL when known.

    Returns
    -------
    str — the redirect response to return to the user.
    """
    if scheme_name and scheme_name in SCHEME_URLS:
        url = SCHEME_URLS[scheme_name]
        return (
            f"The current NAV for {scheme_name} is updated daily by AMFI and "
            f"displayed in real time on the Groww scheme page: {url}\n\n"
            "Note: This assistant's data is refreshed once per day and may not "
            "reflect today's latest NAV. Please visit the Groww page above for "
            "the live value."
        )
    return (
        "NAV data is updated daily by AMFI. For the most current NAV, please "
        "visit the relevant Groww scheme page directly.\n\n"
        "The 5 HDFC schemes covered by this assistant are:\n"
        + "\n".join(
            f"  {i + 1}. {name} — {url}"
            for i, (name, url) in enumerate(SCHEME_URLS.items())
        )
        + "\n\nNote: This assistant's data is refreshed once per day and may "
        "not reflect today's latest NAV."
    )
