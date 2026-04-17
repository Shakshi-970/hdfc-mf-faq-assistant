"""
phases/phase_3_2_chunking_embedding/atomic_chunker.py
-------------------------------------------------------
Step 3a — Atomic Fact Chunker

Converts each structured key-value field into exactly ONE complete sentence
using field-specific templates. This ensures precise retrieval: a query like
"What is the expense ratio of HDFC ELSS?" matches a single, unambiguous chunk.

Templates are defined per field key as per docs/chunking-and-embedding.md §5.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .field_splitter import SplitResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sentence templates — one per field key
# {scheme_name}, {value}, {date} are the only substitution variables.
# ---------------------------------------------------------------------------

ATOMIC_TEMPLATES: dict[str, str] = {
    "nav": (
        "The NAV of {scheme_name} is {value} as of {date}."
    ),
    "expense_ratio": (
        "The total expense ratio (TER) of {scheme_name} is {value}."
    ),
    "exit_load": (
        "The exit load of {scheme_name} is: {value}."
    ),
    "min_sip": (
        "The minimum SIP investment amount for {scheme_name} is {value}."
    ),
    "min_lumpsum": (
        "The minimum lump sum investment for {scheme_name} is {value}."
    ),
    "riskometer": (
        "The riskometer classification of {scheme_name} is {value}."
    ),
    "benchmark": (
        "The benchmark index for {scheme_name} is {value}."
    ),
    "fund_manager": (
        "The fund manager(s) of {scheme_name} are {value}."
    ),
    "aum": (
        "The Assets Under Management (AUM) of {scheme_name} is {value}."
    ),
    "lock_in": (
        "The lock-in period for {scheme_name} is {value}."
    ),
    "tax_benefit": (
        "The tax benefit for {scheme_name}: {value}."
    ),
    "category": (
        "The fund category of {scheme_name} is {value}."
    ),
    "fund_house": (
        "The fund house (AMC) for {scheme_name} is {value}."
    ),
    "rating": (
        "The Groww rating of {scheme_name} is {value} out of 5."
    ),
}


@dataclass
class RawChunk:
    """
    A single chunk before metadata is attached.

    Attributes
    ----------
    text       : The sentence/paragraph text to be embedded.
    chunk_type : "atomic_fact" or "free_text".
    field      : Field key (e.g. "expense_ratio") or "general" for free-text.
    """
    text: str
    chunk_type: str
    field: str


def build_atomic_chunks(split: SplitResult) -> list[RawChunk]:
    """
    Generate one RawChunk per structured field in the SplitResult.

    Fields with no template are emitted as a generic fallback sentence
    so no data is silently dropped.

    Parameters
    ----------
    split : Output from field_splitter.split().

    Returns
    -------
    list[RawChunk] — one chunk per non-null structured field.
    """
    chunks: list[RawChunk] = []

    for field_key, value in split.structured_fields.items():
        template = ATOMIC_TEMPLATES.get(field_key)

        if template:
            text = template.format(
                scheme_name=split.scheme_name,
                value=value,
                date=split.ingestion_date,
            )
        else:
            # Fallback for any field not in the template map
            label = field_key.replace("_", " ").title()
            text = f"The {label} of {split.scheme_name} is {value}."
            logger.debug(
                "No template for field '%s' — using fallback sentence.", field_key
            )

        chunks.append(RawChunk(text=text, chunk_type="atomic_fact", field=field_key))

    logger.info(
        "Atomic chunker — '%s': produced %d atomic-fact chunks.",
        split.scheme_name,
        len(chunks),
    )
    return chunks
