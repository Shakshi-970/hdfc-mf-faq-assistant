"""
phases/phase_11/phase_11_1_security/domain_whitelist.py
--------------------------------------------------------
Source domain whitelist — Section 11, Security and Privacy Controls.

Architecture requirement:
  "Source domain whitelist — Scraper rejects any URL outside approved domains"
  "Source domain locked to groww.in — Scraper rejects any URL not in the
   5-URL corpus whitelist"
  "HTTPS only — All external fetches enforce TLS"

Three levels of validation (most → least restrictive):
  1. is_corpus_url(url)  — True only for the exact 5 authorised scheme pages
  2. validate_url(url)   — raises ValueError for any URL that is:
                             • not HTTPS
                             • not on groww.in
                             • not in the 5-URL corpus
  3. ALLOWED_DOMAIN      — string constant for domain-only checks

Public API
----------
validate_url(url)              — call before any external HTTP fetch
is_corpus_url(url) -> bool     — call when accepting source_url from chunk metadata
CORPUS_URLS                    — frozenset of the 5 authorised URLs
ALLOWED_DOMAIN                 — "groww.in"
"""

from __future__ import annotations

from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Authorised corpus — the 5 Groww HDFC scheme pages (Section 5 of arch doc)
# ---------------------------------------------------------------------------

ALLOWED_DOMAIN: str = "groww.in"

CORPUS_URLS: frozenset[str] = frozenset({
    "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth",
})


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _normalise(url: str) -> str:
    """Strip trailing slashes for consistent comparison."""
    return url.rstrip("/")


def validate_url(url: str) -> None:
    """
    Enforce the three-layer URL security policy.

    Raises
    ------
    ValueError
        With a descriptive message identifying which rule the URL violates.

    Checks (in order):
      1. Scheme must be ``https`` — no plaintext HTTP fetches.
      2. Hostname must be ``groww.in`` or ``www.groww.in``.
      3. URL must be one of the 5 authorised corpus URLs.
    """
    parsed = urlparse(url)

    # Control: HTTPS only
    if parsed.scheme != "https":
        raise ValueError(
            f"Security violation — non-HTTPS URL rejected: '{url}'. "
            "Only HTTPS fetches are permitted (Section 11: HTTPS only)."
        )

    # Control: source domain whitelist
    host = parsed.netloc.lower().lstrip("www.")
    if host != ALLOWED_DOMAIN:
        raise ValueError(
            f"Security violation — domain '{host}' is not whitelisted. "
            f"Only '{ALLOWED_DOMAIN}' is an approved source domain "
            "(Section 11: Source domain whitelist)."
        )

    # Control: source domain locked to corpus URLs
    if _normalise(url) not in {_normalise(u) for u in CORPUS_URLS}:
        raise ValueError(
            f"Security violation — URL '{url}' is not in the 5-URL corpus whitelist. "
            "Only the authorised HDFC scheme pages on Groww may be scraped "
            "(Section 11: Source domain locked to groww.in)."
        )


def is_corpus_url(url: str) -> bool:
    """
    Return True if *url* is one of the 5 authorised corpus URLs.

    Does not raise — safe to use in conditional checks anywhere a URL
    appears (e.g., validating ``source_url`` in chunk metadata).
    """
    return _normalise(url) in {_normalise(u) for u in CORPUS_URLS}
