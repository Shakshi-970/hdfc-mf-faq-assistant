"""
phases/phase_3_3_scraping_service/run.py
-----------------------------------------
Entry point for the scraping service, called by the GitHub Actions workflow:

    python -m phases.phase_3_3_scraping_service.run

Orchestrates:
  1. URL Dispatcher  — reads corpus URLs (env var or config)
  2. HTTP Fetcher    — async concurrent fetch of all 5 Groww pages
  3. HTML Parser     — extract structured fields + free-text per scheme
  4. Change Detector — diff against yesterday's snapshot
  5. Output writer   — writes scraper/output/scraped_<date>.json
                       (only changed schemes are marked for downstream use)

Exit codes:
  0 — success (all or some URLs scraped)
  1 — all URLs failed (triggers GitHub Actions job failure + email alert)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .change_detector import diff_report
from .config import GROWW_URLS, SCRAPER_OUTPUT_DIR
from .fetcher import fetch_all
from .parser import parse_scheme_page

IST = ZoneInfo("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("phase_3_3_scraping_service.run")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_urls() -> list[str]:
    """
    Return the list of URLs to scrape.

    Priority:
      1. GROWW_URLS environment variable (newline or comma-separated)
         — set as a GitHub Actions repo variable
      2. Hardcoded list from config.py
    """
    env_urls = os.environ.get("GROWW_URLS", "").strip()
    if env_urls:
        urls = [u.strip() for u in env_urls.replace(",", "\n").splitlines() if u.strip()]
        logger.info("Using %d URL(s) from GROWW_URLS environment variable.", len(urls))
        return urls
    logger.info("GROWW_URLS env var not set — using hardcoded config URLs.")
    return GROWW_URLS


def _write_output(records: list[dict], date_str: str) -> str:
    """Write scraped records to a dated JSON file and return the path."""
    os.makedirs(SCRAPER_OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(SCRAPER_OUTPUT_DIR, f"scraped_{date_str}.json")
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    logger.info("Scraper output written to %s", output_path)
    return output_path


def _print_summary(records: list[dict], failed_urls: list[str]) -> None:
    """Print a human-readable run summary to stdout (picked up by GH Actions logs)."""
    changed = [r for r in records if r.get("_changed")]
    unchanged = [r for r in records if not r.get("_changed")]

    print("\n" + "=" * 60)
    print("SCRAPER RUN SUMMARY")
    print("=" * 60)
    print(f"  Total URLs     : {len(records) + len(failed_urls)}")
    print(f"  Successful     : {len(records)}")
    print(f"  Failed         : {len(failed_urls)}")
    print(f"  Changed        : {len(changed)}  (will proceed to chunking/embedding)")
    print(f"  Unchanged      : {len(unchanged)}  (skipped downstream)")
    if failed_urls:
        print("\n  Failed URLs:")
        for url in failed_urls:
            print(f"    - {url}")
    if changed:
        print("\n  Changed schemes:")
        for r in changed:
            print(f"    - {r.get('scheme_name', r.get('source_url'))}")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def main() -> int:
    """
    Run the full scraping pipeline.
    Returns 0 on success, 1 if all URLs failed.
    """
    now_ist = datetime.now(tz=IST)
    date_str = now_ist.strftime("%Y-%m-%d")
    time_str = now_ist.strftime("%H:%M")

    logger.info("Scraper started at %s IST", now_ist.strftime("%Y-%m-%d %H:%M:%S"))

    urls = _resolve_urls()
    if not urls:
        logger.error("No URLs to scrape. Exiting.")
        return 1

    # Step 1: Fetch all URLs concurrently
    logger.info("Fetching %d URL(s)...", len(urls))
    html_results = await fetch_all(urls)

    failed_urls = [url for url, html in html_results.items() if html is None]
    successful_html = {url: html for url, html in html_results.items() if html is not None}

    if not successful_html:
        logger.error(
            "All %d URL(s) failed to fetch. No data to process.", len(urls)
        )
        return 1

    if failed_urls:
        logger.warning(
            "%d URL(s) failed: %s. Continuing with %d successful.",
            len(failed_urls),
            failed_urls,
            len(successful_html),
        )

    # Step 2: Parse each fetched page
    records: list[dict] = []
    for url, html in successful_html.items():
        logger.info("Parsing %s ...", url)
        try:
            parsed = parse_scheme_page(url, html)
            parsed["scraped_at"] = now_ist.isoformat()
            parsed["ingestion_date"] = date_str
            parsed["ingestion_time"] = time_str

            # Step 3: Change detection
            report = diff_report(url, parsed)
            parsed["_changed"] = report["changed"]
            parsed["_is_new"] = report["is_new"]

            records.append(parsed)

        except Exception as exc:
            logger.error("Failed to parse %s: %s", url, exc, exc_info=True)
            failed_urls.append(url)

    if not records:
        logger.error("All pages failed to parse. Exiting with error.")
        return 1

    # Step 4: Write output file
    output_path = _write_output(records, date_str)

    # Step 5: Summary
    _print_summary(records, failed_urls)

    changed_count = sum(1 for r in records if r.get("_changed"))
    logger.info(
        "Scraper finished. Output: %s | Changed: %d | Failed: %d",
        output_path,
        changed_count,
        len(failed_urls),
    )

    # Exit 0 even if some URLs failed — partial success is acceptable.
    # The ingestion pipeline will use whatever was successfully scraped.
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
