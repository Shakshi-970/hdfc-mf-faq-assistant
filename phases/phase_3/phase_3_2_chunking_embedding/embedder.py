"""
phases/phase_3_2_chunking_embedding/embedder.py
-------------------------------------------------
Step 5 — Embedding Model

Converts TaggedChunks into dense vectors using:

  MODEL : BAAI/bge-small-en-v1.5 (384-dim, local CPU)
          - No API key required
          - Batch size : 32 chunks per encode() call
          - Library    : sentence-transformers

Returns EmbeddedChunk objects: TaggedChunk + vector list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .metadata_tagger import TaggedChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384
EMBEDDING_BATCH_SIZE = 32


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class EmbeddedChunk:
    """
    A TaggedChunk paired with its dense vector embedding.

    Attributes
    ----------
    text      : The chunk text.
    metadata  : Full metadata envelope from MetadataTagger.
    vector    : Dense float list (384-dim).
    model     : Name of the model used to produce this vector.
    """
    text: str
    metadata: dict = field(default_factory=dict)
    vector: list[float] = field(default_factory=list)
    model: str = ""

    @property
    def chunk_id(self) -> str:
        return self.metadata["chunk_id"]


# ---------------------------------------------------------------------------
# Embedding backend
# ---------------------------------------------------------------------------

def _embed(texts: list[str]) -> list[list[float]]:
    """
    Embed texts locally using BAAI/bge-small-en-v1.5.
    Processes in batches of EMBEDDING_BATCH_SIZE.

    BGE models expect queries to be prefixed with "Represent this sentence: "
    when used for retrieval. For document chunks (ingestion side) no prefix
    is needed — the model is asymmetric at query time only.

    Returns a flat list of vectors in the same order as the input texts.
    """
    from sentence_transformers import SentenceTransformer

    logger.info("Loading model '%s'...", EMBEDDING_MODEL)
    model = SentenceTransformer(EMBEDDING_MODEL)

    all_vectors: list[list[float]] = []

    for batch_start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[batch_start: batch_start + EMBEDDING_BATCH_SIZE]
        logger.info(
            "Embedding: batch %d–%d (%d chunks).",
            batch_start + 1,
            batch_start + len(batch),
            len(batch),
        )
        embeddings = model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
        all_vectors.extend(embeddings.tolist())

    return all_vectors


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def embed(chunks: list[TaggedChunk]) -> list[EmbeddedChunk]:
    """
    Embed all tagged chunks and return EmbeddedChunk objects.

    Uses BAAI/bge-small-en-v1.5 locally via sentence-transformers.
    No API key or network access required.

    Parameters
    ----------
    chunks : List of TaggedChunk objects from the metadata tagger.

    Returns
    -------
    list[EmbeddedChunk] — one per input chunk, with vector attached.
    """
    if not chunks:
        logger.info("No chunks to embed. Returning empty list.")
        return []

    texts = [c.text for c in chunks]

    logger.info(
        "Using '%s' to embed %d chunk(s).", EMBEDDING_MODEL, len(chunks)
    )
    vectors = _embed(texts)

    if len(vectors) != len(chunks):
        raise RuntimeError(
            f"Vector count mismatch: got {len(vectors)} vectors for {len(chunks)} chunks."
        )

    embedded = [
        EmbeddedChunk(
            text=chunk.text,
            metadata=chunk.metadata,
            vector=vector,
            model=EMBEDDING_MODEL,
        )
        for chunk, vector in zip(chunks, vectors)
    ]

    logger.info(
        "Embedding complete: %d chunk(s) embedded using '%s' (%d-dim).",
        len(embedded),
        EMBEDDING_MODEL,
        len(embedded[0].vector) if embedded else 0,
    )
    return embedded
