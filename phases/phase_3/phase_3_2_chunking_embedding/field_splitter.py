"""
phases/phase_3_2_chunking_embedding/field_splitter.py
-------------------------------------------------------
Step 2 — Field Splitter

Routes normalised scraper output to the correct chunker:
  - Structured fields (key-value pairs)  → Atomic Fact Chunker
  - Free-text paragraphs (list of strs)  → Recursive Text Chunker

Returns two separate lists that are passed independently downstream.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SplitResult:
    """
    Container produced by the field splitter for a single scheme record.

    Attributes
    ----------
    scheme_name     : Display name of the scheme.
    source_url      : Groww URL (used for metadata + citations).
    amc             : Asset Management Company name.
    category        : Fund category (Large Cap, ELSS, etc.).
    ingestion_date  : YYYY-MM-DD string from the scraper run.
    ingestion_time  : HH:MM IST string from the scraper run.

    structured_fields : Dict of field_name → value for atomic-fact chunking.
                        Only fields with non-None, non-empty values are included.
    free_text_paras   : List of paragraph strings for recursive text chunking.
                        Empty paragraphs are excluded.
    """
    scheme_name: str
    source_url: str
    amc: str
    category: str
    ingestion_date: str
    ingestion_time: str
    structured_fields: dict[str, str] = field(default_factory=dict)
    free_text_paras: list[str] = field(default_factory=list)


def split(record: dict) -> SplitResult:
    """
    Split a normalised scraper record into structured fields and free-text.

    Parameters
    ----------
    record : A normalised scraper output record (dict).

    Returns
    -------
    SplitResult with structured_fields and free_text_paras populated.
    """
    # Only include fields that have actual values
    structured = {
        k: v
        for k, v in record.get("fields", {}).items()
        if v and str(v).strip()
    }

    # Only include non-empty free-text paragraphs
    free_text = [p for p in record.get("free_text", []) if p and p.strip()]

    result = SplitResult(
        scheme_name=record.get("scheme_name", ""),
        source_url=record.get("source_url", ""),
        amc=record.get("amc", "HDFC Mutual Fund"),
        category=record.get("category", ""),
        ingestion_date=record.get("ingestion_date", ""),
        ingestion_time=record.get("ingestion_time", ""),
        structured_fields=structured,
        free_text_paras=free_text,
    )

    logger.info(
        "Field splitter — '%s': %d structured fields, %d free-text paragraphs.",
        result.scheme_name,
        len(result.structured_fields),
        len(result.free_text_paras),
    )
    return result


def split_all(records: list[dict]) -> list[SplitResult]:
    """Split every record in the scraper output list."""
    return [split(r) for r in records]
