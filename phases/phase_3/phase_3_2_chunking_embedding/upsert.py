"""
phases/phase_3_2_chunking_embedding/upsert.py
-----------------------------------------------
Step 6 — Vector Store Upsert

Upserts EmbeddedChunks into Chroma Cloud and writes the run report.

Backend (from docs/chunking-and-embedding.md §9):
  Remote ChromaDB — Chroma Cloud (trychroma.com)

Required environment variables:
  CHROMA_API_KEY   : Chroma Cloud authentication key  (GitHub Actions Secret)
  CHROMA_TENANT    : Chroma Cloud tenant identifier   (GitHub Actions Variable)
  CHROMA_DATABASE  : Chroma Cloud database name       (GitHub Actions Variable)

Upsert strategy:
  - Key: chunk_id (SHA-256 hash, deterministic across runs)
  - On match  : overwrite vector + metadata
  - On new    : insert
  - On absent : stale chunk from a previous day is left intact
                (intentional: retain data if a URL failed today)

Post-upsert:
  - Writes phases/phase_3_2_chunking_embedding/last_run_report.json
    (read by GitHub Actions summary step)
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .embedder import EmbeddedChunk

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

CHROMA_COLLECTION = "mf_faq_chunks"
# Use __file__-relative paths so these work regardless of where the package lives.
_HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(_HERE, "last_run_report.json")
EMBEDDED_CHUNKS_PATH = os.path.join(_HERE, "embedded_chunks.json")


# ---------------------------------------------------------------------------
# Chroma Cloud backend
# ---------------------------------------------------------------------------

def _upsert_chroma_cloud(chunks: list[EmbeddedChunk]) -> int:
    """
    Upsert chunks into the remote Chroma Cloud collection.

    Reads connection parameters from environment variables:
      CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE

    Returns the number of chunks upserted.
    """
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

    logger.info(
        "Chroma Cloud upsert: tenant='%s', database='%s', collection='%s'.",
        tenant, database, CHROMA_COLLECTION,
    )

    client = chromadb.CloudClient(
        tenant=tenant,
        database=database,
        api_key=api_key,
    )

    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [c.chunk_id for c in chunks]
    embeddings = [c.vector for c in chunks]
    documents = [c.text for c in chunks]
    # ChromaDB metadata values must be str / int / float / bool
    metadatas = [
        {k: (str(v) if v is not None else "") for k, v in c.metadata.items()}
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    logger.info("Chroma Cloud upsert complete: %d chunk(s) written.", len(chunks))
    return len(chunks)


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(
    total_chunks: int,
    upserted: int,
    skipped: int,
    failed_urls: list[str],
    duration_sec: float,
    model_used: str,
) -> None:
    """Write last_run_report.json for the GitHub Actions summary step."""
    now = datetime.now(tz=IST)
    report = {
        "date":         now.strftime("%Y-%m-%d"),
        "time_ist":     now.strftime("%H:%M"),
        "model":        model_used,
        "total_chunks": total_chunks,
        "upserted":     upserted,
        "skipped":      skipped,
        "failed_urls":  failed_urls,
        "duration_sec": round(duration_sec, 1),
    }
    os.makedirs(os.path.dirname(REPORT_PATH) or ".", exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    logger.info("Run report written to %s", REPORT_PATH)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def upsert(
    chunks: list[EmbeddedChunk],
    skipped_count: int = 0,
    failed_urls: list[str] | None = None,
    start_time: float | None = None,
) -> None:
    """
    Upsert all EmbeddedChunks into Chroma Cloud.

    Parameters
    ----------
    chunks        : EmbeddedChunks to write.
    skipped_count : Number of chunks skipped due to no change (for reporting).
    failed_urls   : URLs that failed in the scraping step (for reporting).
    start_time    : time.time() value from the start of the pipeline (for duration).
    """
    if failed_urls is None:
        failed_urls = []

    model_used = chunks[0].model if chunks else "none"

    if not chunks:
        logger.info("No chunks to upsert. Writing empty report.")
        _write_report(
            total_chunks=0,
            upserted=0,
            skipped=skipped_count,
            failed_urls=failed_urls,
            duration_sec=time.time() - (start_time or time.time()),
            model_used=model_used,
        )
        return

    logger.info("Upserting %d chunk(s) to Chroma Cloud.", len(chunks))

    try:
        upserted = _upsert_chroma_cloud(chunks)
    except Exception as exc:
        logger.error("Chroma Cloud upsert failed: %s", exc, exc_info=True)
        _write_report(
            total_chunks=len(chunks) + skipped_count,
            upserted=0,
            skipped=skipped_count,
            failed_urls=failed_urls,
            duration_sec=time.time() - (start_time or time.time()),
            model_used=model_used,
        )
        raise

    duration = time.time() - (start_time or time.time())
    _write_report(
        total_chunks=upserted + skipped_count,
        upserted=upserted,
        skipped=skipped_count,
        failed_urls=failed_urls,
        duration_sec=duration,
        model_used=model_used,
    )


# ---------------------------------------------------------------------------
# Entry point (called directly by GitHub Actions step)
# ---------------------------------------------------------------------------

def main() -> int:
    """
    Standalone entry point for the upsert step.
    Reads embedded chunks from embedded_chunks.json
    (written by chunk_and_embed.py) and upserts them to Chroma Cloud.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if not os.path.exists(EMBEDDED_CHUNKS_PATH):
        logger.error(
            "No embedded_chunks.json found at '%s'. Run chunk_and_embed.py first.",
            EMBEDDED_CHUNKS_PATH,
        )
        return 1

    with open(EMBEDDED_CHUNKS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    chunks = [
        EmbeddedChunk(
            text=item["text"],
            metadata=item["metadata"],
            vector=item["vector"],
            model=item.get("model", ""),
        )
        for item in data.get("chunks", [])
    ]

    skipped = data.get("skipped_count", 0)
    failed = data.get("failed_urls", [])
    start = data.get("pipeline_start_time", time.time())

    logger.info("Loaded %d embedded chunk(s) from %s.", len(chunks), EMBEDDED_CHUNKS_PATH)
    upsert(chunks, skipped_count=skipped, failed_urls=failed, start_time=start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
