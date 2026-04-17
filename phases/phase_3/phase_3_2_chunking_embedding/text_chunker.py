"""
phases/phase_3_2_chunking_embedding/text_chunker.py
-----------------------------------------------------
Step 3b — Recursive Text Chunker

Splits free-text paragraphs using LangChain's RecursiveCharacterTextSplitter
with tiktoken token counting (cl100k_base, same tokeniser as OpenAI embeddings).

Configuration (from docs/chunking-and-embedding.md §6):
  chunk_size    : 512 tokens
  chunk_overlap : 64  tokens
  separators    : ["\n\n", "\n", ". ", " ", ""]
  length_fn     : tiktoken cl100k_base encoder

All free-text paragraphs for a scheme are joined and split together so
overlap can span paragraph boundaries naturally.
"""

from __future__ import annotations

import logging

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .atomic_chunker import RawChunk
from .field_splitter import SplitResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHUNK_SIZE = 512       # tokens
CHUNK_OVERLAP = 64     # tokens
TOKENISER_NAME = "cl100k_base"

SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# Module-level cached encoder and splitter (initialised once)
_encoder: tiktoken.Encoding | None = None
_splitter: RecursiveCharacterTextSplitter | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding(TOKENISER_NAME)
    return _encoder


def _token_length(text: str) -> int:
    """Return the number of tokens in text using the cl100k_base encoder."""
    return len(_get_encoder().encode(text))


def _get_splitter() -> RecursiveCharacterTextSplitter:
    global _splitter
    if _splitter is None:
        _splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=_token_length,
            separators=SEPARATORS,
            keep_separator=True,
        )
    return _splitter


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def build_text_chunks(split: SplitResult) -> list[RawChunk]:
    """
    Split all free-text paragraphs for a scheme into overlapping chunks.

    All paragraphs are joined with double newlines before splitting so that
    the splitter can use paragraph boundaries as natural split points and
    the 64-token overlap can span across paragraph boundaries.

    Parameters
    ----------
    split : Output from field_splitter.split().

    Returns
    -------
    list[RawChunk] — zero or more free-text chunks.
    """
    if not split.free_text_paras:
        logger.debug("No free-text paragraphs for '%s'. Skipping.", split.scheme_name)
        return []

    # Join paragraphs into one document for the splitter
    combined = "\n\n".join(split.free_text_paras)

    splitter = _get_splitter()
    pieces = splitter.split_text(combined)

    chunks = [
        RawChunk(text=piece.strip(), chunk_type="free_text", field="general")
        for piece in pieces
        if piece.strip()
    ]

    logger.info(
        "Text chunker -- '%s': %d free-text paragraph(s) -> %d chunk(s) "
        "(size=%d tok, overlap=%d tok).",
        split.scheme_name,
        len(split.free_text_paras),
        len(chunks),
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )
    return chunks
