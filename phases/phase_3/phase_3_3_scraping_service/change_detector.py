"""
phases/phase_3_3_scraping_service/change_detector.py
------------------------------------------------------
Snapshot-based change detection.

On every run, the scraper saves a JSON snapshot of each scheme's extracted
fields. Before passing data downstream to the chunker/embedder, the change
detector diffs today's extracted fields against the stored snapshot.

Outcomes:
  - NO_CHANGE  : fields identical to snapshot → skip chunking/embedding (cost saving)
  - CHANGED    : one or more fields differ    → proceed with full upsert
  - NEW        : no snapshot exists yet       → treat as full change (first run)

Snapshots are stored at: scraper/snapshots/<scheme_slug>.json
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .config import SNAPSHOTS_DIR
from .parser import _slug_from_url

logger = logging.getLogger(__name__)


def _snapshot_path(slug: str) -> str:
    return os.path.join(SNAPSHOTS_DIR, f"{slug}.json")


def load_snapshot(url: str) -> dict[str, Any] | None:
    """
    Load the previous snapshot for a scheme URL.
    Returns None if no snapshot exists.
    """
    slug = _slug_from_url(url)
    path = _snapshot_path(slug)
    if not os.path.exists(path):
        logger.debug("No snapshot found for slug '%s'.", slug)
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read snapshot for '%s': %s. Treating as new.", slug, exc)
        return None


def save_snapshot(url: str, data: dict[str, Any]) -> None:
    """
    Persist the current scrape result as the new snapshot for a scheme URL.
    Overwrites any existing snapshot.
    """
    slug = _slug_from_url(url)
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    path = _snapshot_path(slug)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    logger.debug("Snapshot saved for slug '%s' at %s.", slug, path)


def has_changed(current: dict[str, Any], previous: dict[str, Any] | None) -> bool:
    """
    Return True if the current scrape result differs from the stored snapshot.

    Comparison is done only on the `fields` dict (structured data).
    Changes to `free_text` also trigger a re-embed.

    A missing snapshot (None) is always treated as changed.
    """
    if previous is None:
        logger.info("No previous snapshot — treating as new data.")
        return True

    current_fields = current.get("fields", {})
    previous_fields = previous.get("fields", {})

    changed_fields = [
        key
        for key in set(current_fields) | set(previous_fields)
        if current_fields.get(key) != previous_fields.get(key)
    ]

    current_text = current.get("free_text", [])
    previous_text = previous.get("free_text", [])
    text_changed = current_text != previous_text

    if changed_fields or text_changed:
        if changed_fields:
            logger.info("Changed fields: %s", changed_fields)
        if text_changed:
            logger.info("Free-text content changed.")
        return True

    logger.info("No changes detected — skipping chunking/embedding for this scheme.")
    return False


def diff_report(url: str, current: dict[str, Any]) -> dict[str, Any]:
    """
    Convenience function that loads the snapshot, computes the diff,
    saves the new snapshot, and returns a report dict.

    Returns
    -------
    {
        "url"       : str,
        "scheme"    : str,
        "changed"   : bool,
        "is_new"    : bool,   (True if no prior snapshot existed)
    }
    """
    previous = load_snapshot(url)
    is_new = previous is None
    changed = has_changed(current, previous)

    # Always save the latest snapshot (even if no change, to refresh timestamp)
    save_snapshot(url, current)

    return {
        "url": url,
        "scheme": current.get("scheme_name", url),
        "changed": changed,
        "is_new": is_new,
    }
