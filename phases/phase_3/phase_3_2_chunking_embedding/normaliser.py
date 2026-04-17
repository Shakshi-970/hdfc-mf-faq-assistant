"""
phases/phase_3_2_chunking_embedding/normaliser.py
---------------------------------------------------
Step 1 — Text Normaliser

Cleans and standardises all raw text before chunking.
Applied to both structured field values and free-text paragraphs.

Operations (in order as per docs/chunking-and-embedding.md §3):
  1. Decode HTML entities    (&amp; → &, &#8377; → ₹)
  2. Collapse whitespace     (\t, \n\n+ → single space/newline)
  3. Strip zero-width chars  (\u200b, \u200c, \u200d, \u00a0 → space)
  4. Normalise Unicode       (NFC)
  5. Remove boilerplate      (cookie banners, "Accept all", etc.)
  6. Standardise currency    ("Rs." / "INR " / "Rs " → "₹")
  7. Standardise percent     (" percent" / " per cent" → "%")
"""

from __future__ import annotations

import html
import re
import unicodedata

# ---------------------------------------------------------------------------
# Boilerplate keyword patterns — lines containing these are stripped
# ---------------------------------------------------------------------------
_BOILERPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"accept\s+(all\s+)?cookies?", re.IGNORECASE),
    re.compile(r"cookie\s+policy", re.IGNORECASE),
    re.compile(r"privacy\s+policy", re.IGNORECASE),
    re.compile(r"terms\s+(and\s+conditions|of\s+(use|service))", re.IGNORECASE),
    re.compile(r"all\s+rights\s+reserved", re.IGNORECASE),
    re.compile(r"subscribe\s+to\s+(our\s+)?newsletter", re.IGNORECASE),
    re.compile(r"javascript\s+(is\s+)?required", re.IGNORECASE),
    re.compile(r"enable\s+javascript", re.IGNORECASE),
    re.compile(r"loading\.\.\.", re.IGNORECASE),
]

# Zero-width and non-breaking characters to strip
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
_NBSP_RE = re.compile(r"\u00a0")

# Currency normalisation
_CURRENCY_RE = re.compile(
    r"\b(?:Rs\.?|INR)\s*",
    re.IGNORECASE,
)

# Percent normalisation
_PERCENT_RE = re.compile(
    r"\s+per\s*cent\b|\s+percent\b",
    re.IGNORECASE,
)

# Collapse runs of spaces (but not newlines)
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
# Collapse 3+ newlines to 2
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _remove_boilerplate(text: str) -> str:
    """Drop lines that match known boilerplate patterns."""
    lines = text.splitlines()
    clean = [
        line for line in lines
        if not any(pat.search(line) for pat in _BOILERPLATE_PATTERNS)
    ]
    return "\n".join(clean)


def normalise(text: str) -> str:
    """
    Apply all 7 normalisation steps to a text string.

    Parameters
    ----------
    text : Raw text from the scraper (field value or free-text paragraph).

    Returns
    -------
    str : Cleaned, normalised text ready for chunking.
    """
    if not text or not text.strip():
        return ""

    # Step 1 — Decode HTML entities
    text = html.unescape(text)

    # Step 2 — Collapse tabs to spaces first, then handle newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    # Step 3 — Strip zero-width and non-breaking characters
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _NBSP_RE.sub(" ", text)

    # Step 4 — Unicode NFC normalisation
    text = unicodedata.normalize("NFC", text)

    # Step 5 — Remove boilerplate lines
    text = _remove_boilerplate(text)

    # Step 6 — Standardise currency symbols
    text = _CURRENCY_RE.sub("₹", text)

    # Step 7 — Standardise percent notation
    text = _PERCENT_RE.sub("%", text)

    return text.strip()


def normalise_record(record: dict) -> dict:
    """
    Normalise all text in a scraper output record in-place (returns new dict).

    Applies normalise() to every field value and every free-text paragraph.
    Fields with None values are left as-is.
    """
    normalised = dict(record)

    # Normalise structured fields
    normalised_fields = {}
    for key, val in record.get("fields", {}).items():
        normalised_fields[key] = normalise(val) if val else val
    normalised["fields"] = normalised_fields

    # Normalise free-text paragraphs and drop any that become empty
    normalised["free_text"] = [
        clean
        for raw in record.get("free_text", [])
        if (clean := normalise(raw))
    ]

    # Normalise top-level scheme_name
    if record.get("scheme_name"):
        normalised["scheme_name"] = normalise(record["scheme_name"])

    return normalised
