"""
phases/phase_8/phase_8_1_response_formatter/guardrail.py
---------------------------------------------------------
Post-Generation Guardrail

Scans the body of an LLM response for advisory language that must not
appear in a facts-only assistant.  If detected, the body is replaced
with a safe fallback while any Source / footer lines are preserved.

Public API
----------
sanitize_output(text) -> tuple[str, bool]
    Returns (sanitized_text, was_modified).
    was_modified=True  → advisory language found; body replaced.
    was_modified=False → text is clean; returned unchanged.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Advisory phrases that must not appear in factual answers
# ---------------------------------------------------------------------------

_ADVISORY_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r'\bI recommend\b',
        r'\byou should invest\b',
        r'\byou should consider\b',
        r'\bI suggest\b',
        r'\bconsider investing\b',
        r'\bgood (?:choice|option|investment)\b',
        r'\bbest (?:fund|option|choice)\b',
        r'\bwould recommend\b',
        r'\bideally\b',
        r'\bsuitable for\b',
        r'\bfor your (?:financial )?goal\b',
    ]
]

# Fallback body when advisory language is detected
_FALLBACK_BODY = (
    "This assistant provides verified facts only and cannot offer investment "
    "advice or recommendations. Please refer to the source page for full details."
)

# ---------------------------------------------------------------------------
# Compiled patterns to locate Source / footer lines
# ---------------------------------------------------------------------------

_SOURCE_LINE = re.compile(r'(^\s*Source\s*:.*$)', re.IGNORECASE | re.MULTILINE)
_FOOTER_LINE = re.compile(
    r'(^\s*Last updated from sources\s*:.*$)', re.IGNORECASE | re.MULTILINE
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_body_and_footer(text: str) -> tuple[str, list[str]]:
    """
    Separate the answer body from any Source / footer lines.

    Returns
    -------
    (body_text, footer_lines)
        *body_text*    — text with Source / footer lines removed.
        *footer_lines* — list of the extracted footer line strings (in order
                         found: Source first, then Last-updated).
    """
    footer_lines: list[str] = []

    source_m = _SOURCE_LINE.search(text)
    footer_m = _FOOTER_LINE.search(text)

    body = text
    if source_m:
        footer_lines.append(source_m.group(1).strip())
        body = _SOURCE_LINE.sub('', body)
    if footer_m:
        footer_lines.append(footer_m.group(1).strip())
        body = _FOOTER_LINE.sub('', body)

    return body.strip(), footer_lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sanitize_output(text: str) -> tuple[str, bool]:
    """
    Check an LLM response for advisory language and sanitise if found.

    The check is applied only to the *body* (Source / footer lines are
    excluded) so metadata lines never trigger a false positive.

    Parameters
    ----------
    text : Raw LLM output string (may include Source / footer lines).

    Returns
    -------
    tuple[str, bool]
        ``(sanitized_text, was_modified)``

        * ``was_modified=False`` — no advisory language detected; *text*
          returned unchanged.
        * ``was_modified=True``  — advisory language found; body replaced
          with :data:`_FALLBACK_BODY`; Source / footer lines preserved.
    """
    body, footer_lines = _split_body_and_footer(text)

    if not any(pattern.search(body) for pattern in _ADVISORY_PATTERNS):
        return text, False

    # Rebuild with fallback body + preserved footer
    parts = [_FALLBACK_BODY] + footer_lines
    return '\n\n'.join(parts), True
