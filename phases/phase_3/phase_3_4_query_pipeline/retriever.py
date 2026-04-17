"""
phases/phase_3_4_query_pipeline/retriever.py
---------------------------------------------
Step 4 — Query Embedder + Vector Store Search + Re-Rank

Converts a rewritten query to a dense vector, searches the Chroma Cloud
`mf_faq_chunks` collection, and returns the top-N most relevant chunks.

BGE asymmetric retrieval:
  - Document side (ingestion): chunks encoded as-is (done in Phase 3.2)
  - Query side (this module):  query prefixed with "Represent this sentence: "
    before encoding, as recommended for BAAI/bge-small-en-v1.5

Connection:
  CHROMA_API_KEY  : Chroma Cloud auth key   (env var)
  CHROMA_TENANT   : Chroma Cloud tenant     (env var)
  CHROMA_DATABASE : Chroma Cloud database   (env var)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

COLLECTION_NAME = "mf_faq_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
BGE_QUERY_PREFIX = "Represent this sentence: "

TOP_K = 5   # chunks retrieved from Chroma
TOP_N = 3   # chunks returned after re-rank

# Module-level caches — loaded once per process
_model = None
_collection = None


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------

def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        logger.info("Loading embedding model '%s' via fastembed...", EMBEDDING_MODEL)
        _model = TextEmbedding(EMBEDDING_MODEL)
        logger.info("Embedding model loaded.")
    return _model


def _embed_query(query: str) -> list[float]:
    """Embed query with BGE query prefix via fastembed. Returns a 384-dim float list."""
    model = _get_model()
    # fastembed.query_embed() adds the BGE query prefix internally
    vectors = list(model.query_embed([query]))
    return vectors[0].tolist()


# ---------------------------------------------------------------------------
# Chroma Cloud connection
# ---------------------------------------------------------------------------

def _get_collection():
    """Return the mf_faq_chunks collection from Chroma Cloud (cached per process)."""
    global _collection
    if _collection is not None:
        return _collection

    import chromadb

    api_key = os.environ.get("CHROMA_API_KEY", "").strip()
    tenant = os.environ.get("CHROMA_TENANT", "").strip()
    database = os.environ.get("CHROMA_DATABASE", "").strip()

    if not api_key:
        raise EnvironmentError("CHROMA_API_KEY is not set.")
    if not tenant:
        raise EnvironmentError("CHROMA_TENANT is not set.")
    if not database:
        raise EnvironmentError("CHROMA_DATABASE is not set.")

    client = chromadb.CloudClient(
        tenant=tenant,
        database=database,
        api_key=api_key,
    )
    _collection = client.get_collection(name=COLLECTION_NAME)
    logger.info("Chroma collection '%s' connected.", COLLECTION_NAME)
    return _collection


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    scheme_filter: Optional[str] = None,
) -> list[dict]:
    """
    Embed query, search Chroma Cloud, re-rank, return top-N chunks.

    Parameters
    ----------
    query         : Rewritten query string (from rewriter.py).
    scheme_filter : If set, restrict search to chunks for this scheme_name.
                    Used when the session has an active_scheme_context.

    Returns
    -------
    List of dicts, each with keys:
      text     : chunk text
      metadata : full metadata dict (source_url, scheme_name, field_type, ...)
      score    : cosine similarity (0–1, higher is better)
    """
    logger.info(
        "Retrieving for query='%s...' scheme_filter=%s",
        query[:60], scheme_filter,
    )

    query_vector = _embed_query(query)
    collection = _get_collection()

    where = {"scheme_name": {"$eq": scheme_filter}} if scheme_filter else None

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=TOP_K,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[dict] = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # ChromaDB cosine distance: 0 = identical, 1 = orthogonal, 2 = opposite
        # Convert to similarity: 1 - distance (clamped to [0, 1])
        similarity = max(0.0, min(1.0, 1.0 - dist))
        chunks.append({
            "text": doc,
            "metadata": meta,
            "score": round(similarity, 4),
        })

    # Re-rank by score descending, take top-N
    chunks.sort(key=lambda x: x["score"], reverse=True)
    top = chunks[:TOP_N]

    logger.info(
        "Retrieved %d chunk(s) (from %d candidates). Top score: %.4f",
        len(top), len(chunks), top[0]["score"] if top else 0.0,
    )
    return top
