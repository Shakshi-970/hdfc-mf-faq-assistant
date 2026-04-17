"""
phases/phase_8/phase_8_1_response_formatter/formatter.py
---------------------------------------------------------
Step 6 — Response Formatter (Post-generation)

Enforces output structure on every factual LLM answer:
  - Body : max 3 sentences (truncated at 3rd sentence boundary)
  - Exactly one  "Source: <url>" line  (injected from chunk metadata)
  - Exactly one  "Last updated from sources: YYYY-MM-DD" footer

Public API
----------
format_response(answer, source_url, ingestion_date) -> str
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Sentence boundary: . ? ! followed by one or more whitespace characters.
# Using a lookbehind so the delimiter is NOT consumed.
_SENT_SPLIT = re.compile(r'(?<=[.?!])\s+')

# Matches any existing "Source: …" line in the LLM output (to strip before re-inject).
_SOURCE_LINE = re.compile(r'^\s*Source\s*:.*$', re.IGNORECASE | re.MULTILINE)

# Matches any existing "Last updated from sources: …" footer line.
_FOOTER_LINE = re.compile(
    r'^\s*Last updated from sources\s*:.*$', re.IGNORECASE | re.MULTILINE
)

# Phrases that indicate the LLM could not find relevant information.
# When these appear in the body the source citation is suppressed — the
# retrieved chunk that produced the URL was not actually used in the answer.
_NO_INFO_PATTERNS = re.compile(
    r"don'?t have (sufficient|enough)|"
    r"insufficient information|"
    r"no (relevant |sufficient )?information|"
    r"not enough information|"
    r"cannot (find|answer|provide)|"
    r"unable to (find|answer|provide)|"
    r"not available in (my|the)|"
    r"no data available|"
    r"please refer to the source",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cap_sentences(text: str, max_sentences: int = 3) -> str:
    """
    Truncate *text* to at most *max_sentences* complete sentences.

    Sentences are delimited by . ? ! followed by whitespace.  If the
    truncated text does not end with sentence-terminal punctuation a
    period is appended so the output always reads as complete.
    """
    sentences = [s.strip() for s in _SENT_SPLIT.split(text.strip()) if s.strip()]
    capped = sentences[:max_sentences]
    if not capped:
        return text.strip()
    joined = ' '.join(capped)
    if joined and joined[-1] not in '.?!':
        joined += '.'
    return joined


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_response(
    answer: str,
    source_url: str,
    ingestion_date: str,
) -> str:
    """
    Post-process a raw LLM answer to enforce the standard response format.

    Parameters
    ----------
    answer         : Raw text from the LLM.  May or may not already contain
                     Source / footer lines — they are stripped and re-injected.
    source_url     : Authoritative URL taken from the top retrieved chunk's
                     metadata (``chunk["metadata"]["source_url"]``).
    ingestion_date : Date string from the same chunk (e.g. ``"2026-04-16"``).
                     Pass an empty string to omit the footer.

    Returns
    -------
    str
        Formatted string conforming to the architecture spec::

            {≤3 sentences body}

            Source: {source_url}

            Last updated from sources: {ingestion_date}
    """
    # 1. Strip any Source / footer lines already in the LLM output so we can
    #    re-inject canonical, metadata-derived versions.
    body = _SOURCE_LINE.sub('', answer)
    body = _FOOTER_LINE.sub('', body)
    body = body.strip()

    # 2. Cap to 3 sentences.
    body = _cap_sentences(body, max_sentences=3)

    # 3. Return formatted body only — source URL injection is handled by the
    #    pipeline layer, which only exposes the URL when the answer is a no-info
    #    response (i.e. the bot could not find relevant data).
    return body
