"""
phases/phase_3_2_chunking_embedding/chunk_and_embed.py
--------------------------------------------------------
Phase 3.2 entry point — Chunking and Embedding Pipeline

Called by the GitHub Actions workflow step:
    python -m phases.phase_3_2_chunking_embedding.chunk_and_embed

Reads the latest scraper output from scraper/output/scraped_<date>.json,
runs the full pipeline for every scheme where _changed=True, and writes
phases/phase_3_2_chunking_embedding/embedded_chunks.json for the downstream
upsert step.

Pipeline (per changed scheme):
  1. Text Normaliser     — clean & standardise all text
  2. Field Splitter      — route structured fields vs. free-text
  3a. Atomic Chunker     — one sentence per structured field
  3b. Text Chunker       — recursive split of free-text paragraphs
  4.  Metadata Tagger    — attach chunk_id, source_url, dates, etc.
  5.  Embedder           — BAAI/bge-small-en-v1.5 (384-dim, local CPU, no API key)

Output written to:
  phases/phase_3_2_chunking_embedding/embedded_chunks.json
  — consumed by upsert.py
"""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .atomic_chunker import build_atomic_chunks
from .embedder import EmbeddedChunk, embed
from .field_splitter import SplitResult, split
from .metadata_tagger import TaggedChunk, tag_chunks
from .normaliser import normalise_record
from .text_chunker import build_text_chunks

IST = ZoneInfo("Asia/Kolkata")

SCRAPER_OUTPUT_DIR = "scraper/output"
# Use __file__-relative path so this works regardless of where the package lives.
EMBEDDED_OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embedded_chunks.json")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("phase_3_2_chunking_embedding.chunk_and_embed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_latest_scraper_output() -> str | None:
    """
    Return the path to the most recently created scraped_*.json file,
    or None if no files exist.
    """
    pattern = os.path.join(SCRAPER_OUTPUT_DIR, "scraped_*.json")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def _load_scraper_output(path: str) -> tuple[list[dict], list[str]]:
    """
    Load and parse the scraper output JSON.

    Returns
    -------
    (changed_records, failed_urls)
      changed_records : Records where _changed=True (need re-embedding).
      failed_urls     : URLs that the scraper flagged as failed.
    """
    with open(path, encoding="utf-8") as fh:
        records: list[dict] = json.load(fh)

    changed = [r for r in records if r.get("_changed", True)]
    skipped = [r for r in records if not r.get("_changed", True)]
    failed_urls: list[str] = []   # scraper writes failed URLs to its own log

    logger.info(
        "Scraper output: %d total records, %d changed, %d unchanged (skipped).",
        len(records),
        len(changed),
        len(skipped),
    )
    return changed, failed_urls


def _process_scheme(record: dict) -> list[TaggedChunk]:
    """
    Run the full chunking pipeline for a single scheme record.

    Steps 1–4: normalise → split → chunk → tag.
    Returns a list of TaggedChunks ready for embedding.
    """
    # Step 1: Text Normaliser
    normalised = normalise_record(record)

    # Step 2: Field Splitter
    split_result: SplitResult = split(normalised)

    # Step 3a: Atomic Fact Chunker
    atomic_chunks = build_atomic_chunks(split_result)

    # Step 3b: Recursive Text Chunker
    text_chunks = build_text_chunks(split_result)

    # Combine: atomic facts first, then free-text (order determines chunk_index)
    all_raw = atomic_chunks + text_chunks

    if not all_raw:
        logger.warning("No chunks produced for '%s'.", split_result.scheme_name)
        return []

    # Step 4: Metadata Tagger
    tagged = tag_chunks(all_raw, split_result)

    logger.info(
        "Pipeline — '%s': %d atomic + %d free-text = %d total chunks.",
        split_result.scheme_name,
        len(atomic_chunks),
        len(text_chunks),
        len(tagged),
    )
    return tagged


def _write_embedded_output(
    embedded: list[EmbeddedChunk],
    skipped_count: int,
    failed_urls: list[str],
    start_time: float,
) -> None:
    """
    Serialise EmbeddedChunks to embedded_chunks.json
    so that upsert.py can read them as a separate step.
    """
    os.makedirs(os.path.dirname(EMBEDDED_OUTPUT_PATH) or ".", exist_ok=True)

    payload = {
        "generated_at": datetime.now(tz=IST).isoformat(),
        "pipeline_start_time": start_time,
        "total_embedded": len(embedded),
        "skipped_count": skipped_count,
        "failed_urls": failed_urls,
        "chunks": [
            {
                "text":     ec.text,
                "metadata": ec.metadata,
                "vector":   ec.vector,
                "model":    ec.model,
            }
            for ec in embedded
        ],
    }

    with open(EMBEDDED_OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)

    logger.info(
        "Embedded output written to %s (%d chunks, %.1f KB).",
        EMBEDDED_OUTPUT_PATH,
        len(embedded),
        os.path.getsize(EMBEDDED_OUTPUT_PATH) / 1024,
    )


def _print_summary(
    total_tagged: int,
    total_embedded: int,
    skipped: int,
    model: str,
    duration: float,
) -> None:
    print("\n" + "=" * 60)
    print("CHUNK + EMBED SUMMARY")
    print("=" * 60)
    print(f"  Chunks tagged    : {total_tagged}")
    print(f"  Chunks embedded  : {total_embedded}")
    print(f"  Schemes skipped  : {skipped}  (no change detected)")
    print(f"  Embedding model  : {model}")
    print(f"  Duration         : {duration:.1f}s")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main() -> int:
    start_time = time.time()

    # Locate scraper output
    output_path = _find_latest_scraper_output()
    if not output_path:
        logger.error(
            "No scraper output found in '%s'. Run the scraping service first.",
            SCRAPER_OUTPUT_DIR,
        )
        return 1

    logger.info("Reading scraper output from: %s", output_path)
    changed_records, failed_urls = _load_scraper_output(output_path)

    # Count how many records were skipped (unchanged)
    with open(output_path, encoding="utf-8") as fh:
        all_records: list[dict] = json.load(fh)
    skipped_scheme_count = sum(1 for r in all_records if not r.get("_changed", True))

    if not changed_records:
        logger.info("No changed schemes detected. Nothing to embed.")
        _write_embedded_output([], 0, failed_urls, start_time)
        return 0

    # Steps 1–4: Process all changed schemes
    all_tagged: list[TaggedChunk] = []
    for record in changed_records:
        tagged = _process_scheme(record)
        all_tagged.extend(tagged)

    if not all_tagged:
        logger.warning("No chunks produced across all changed schemes.")
        _write_embedded_output([], skipped_scheme_count, failed_urls, start_time)
        return 0

    # Step 5: Embed all chunks in one batched call
    logger.info("Embedding %d chunk(s) across %d scheme(s)...", len(all_tagged), len(changed_records))
    embedded = embed(all_tagged)

    # Write output for upsert step
    _write_embedded_output(embedded, skipped_scheme_count, failed_urls, start_time)

    model_used = embedded[0].model if embedded else "none"
    _print_summary(
        total_tagged=len(all_tagged),
        total_embedded=len(embedded),
        skipped=skipped_scheme_count,
        model=model_used,
        duration=time.time() - start_time,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
