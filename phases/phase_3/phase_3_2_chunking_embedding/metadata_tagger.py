"""
phases/phase_3_2_chunking_embedding/metadata_tagger.py
--------------------------------------------------------
Step 4 — Metadata Tagger

Attaches a standard metadata envelope to every RawChunk, producing a
TaggedChunk ready for embedding and vector store upsert.

Metadata envelope (from docs/chunking-and-embedding.md §7):
  chunk_id       : sha256(source_url + field_type + str(chunk_index))
                   Stable, deterministic ID — enables clean upserts.
  source_url     : Groww scheme page URL (used as the citation link).
  scheme_name    : Display name of the scheme.
  amc_name       : Asset Management Company ("HDFC Mutual Fund").
  category       : Fund category (Large Cap, ELSS, Mid Cap, etc.).
  field_type     : Structured field key OR "general" for free-text.
  chunk_type     : "atomic_fact" | "free_text".
  chunk_index    : 0-based position of this chunk within the scheme's
                   full chunk list (atomic facts come before free-text).
  ingestion_date : YYYY-MM-DD (when the scraper ran).
  ingestion_time : HH:MM IST  (when the scraper ran).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

from .atomic_chunker import RawChunk
from .field_splitter import SplitResult

logger = logging.getLogger(__name__)


@dataclass
class TaggedChunk:
    """
    A chunk with its full metadata envelope, ready for embedding.

    Attributes
    ----------
    text     : The text to embed.
    metadata : Dict matching the metadata envelope specification.
    """
    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        return self.metadata["chunk_id"]


def _make_chunk_id(source_url: str, field_type: str, chunk_index: int) -> str:
    """
    Generate a stable SHA-256 chunk ID from (source_url, field_type, chunk_index).

    The ID is deterministic: running the pipeline twice on the same input
    produces the same chunk_id, enabling upsert deduplication.
    """
    raw = f"{source_url}::{field_type}::{chunk_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def tag_chunks(
    raw_chunks: list[RawChunk],
    split: SplitResult,
) -> list[TaggedChunk]:
    """
    Attach metadata to a list of RawChunks for a single scheme.

    Parameters
    ----------
    raw_chunks : Combined list of atomic-fact + free-text RawChunks
                 (atomic facts should come first for consistent chunk_index values).
    split      : The SplitResult that produced these chunks (provides scheme context).

    Returns
    -------
    list[TaggedChunk] — one TaggedChunk per input RawChunk.
    """
    tagged: list[TaggedChunk] = []

    for index, raw in enumerate(raw_chunks):
        chunk_id = _make_chunk_id(split.source_url, raw.field, index)

        metadata = {
            "chunk_id":       chunk_id,
            "source_url":     split.source_url,
            "scheme_name":    split.scheme_name,
            "amc_name":       split.amc,
            "category":       split.category,
            "field_type":     raw.field,
            "chunk_type":     raw.chunk_type,
            "chunk_index":    index,
            "ingestion_date": split.ingestion_date,
            "ingestion_time": split.ingestion_time,
        }

        tagged.append(TaggedChunk(text=raw.text, metadata=metadata))

    logger.info(
        "Metadata tagger — '%s': tagged %d chunk(s).",
        split.scheme_name,
        len(tagged),
    )
    return tagged
