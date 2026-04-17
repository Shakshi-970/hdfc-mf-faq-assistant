"""
run_ingestion_local.py
----------------------
Local trigger for the full ingestion pipeline — mirrors what the GitHub Actions
daily_ingestion.yml workflow does at 09:15 AM IST.

Phases executed in order:
  Phase 3.3 — Scraping service   (fetch + parse + diff Groww pages)
  Phase 3.2 — Chunk + embed      (normalise → chunk → embed)
  Phase 3.2 — Upsert             (push embedded chunks to Chroma Cloud)

Logging:
  - Console : coloured, human-readable
  - File    : logs/ingestion_<YYYY-MM-DD_HH-MM-SS>.log  (plain text, all detail)

Usage:
  python run_ingestion_local.py

Exit codes:
  0 — all phases passed
  1 — one or more phases failed
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Force UTF-8 on Windows stdout/stderr so Unicode characters don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Bootstrap: load .env before anything else
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; env vars may already be set

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IST = ZoneInfo("Asia/Kolkata")
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

RUN_TS = datetime.now(tz=IST).strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = LOGS_DIR / f"ingestion_{RUN_TS}.log"

PHASES: list[dict] = [
    {
        "id": "3.3",
        "name": "Scraping Service",
        "description": "Fetch Groww scheme pages → parse fields → diff against snapshots → write scraped JSON",
        "module": "phases.phase_3.phase_3_3_scraping_service.run",
    },
    {
        "id": "3.2a",
        "name": "Chunk + Embed",
        "description": "Normalise → field split → atomic/recursive chunk → embed with bge-small-en-v1.5 → write embedded_chunks.json",
        "module": "phases.phase_3.phase_3_2_chunking_embedding.chunk_and_embed",
    },
    {
        "id": "3.2b",
        "name": "Upsert to Chroma Cloud",
        "description": "Read embedded_chunks.json → upsert vectors + metadata to mf_faq_chunks collection → write last_run_report.json",
        "module": "phases.phase_3.phase_3_2_chunking_embedding.upsert",
    },
]

# ANSI colours (disabled on non-TTY)
_USE_COLOUR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

BOLD    = lambda t: _c("1", t)
GREEN   = lambda t: _c("32", t)
RED     = lambda t: _c("31", t)
YELLOW  = lambda t: _c("33", t)
CYAN    = lambda t: _c("36", t)
DIM     = lambda t: _c("2", t)


# ---------------------------------------------------------------------------
# Logging setup — writes to both console and log file
# ---------------------------------------------------------------------------

def _setup_logging() -> tuple[logging.Logger, logging.FileHandler]:
    logger = logging.getLogger("ingestion")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — everything, no colour
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler — INFO+
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    return logger, fh


# ---------------------------------------------------------------------------
# Phase runner
# ---------------------------------------------------------------------------

def _run_phase(phase: dict, logger: logging.Logger) -> dict:
    """
    Run a single pipeline phase as a subprocess.
    Captures stdout + stderr, streams to both console and log file.
    Returns a result dict with keys: id, name, passed, duration_sec, output_lines.
    """
    phase_label = f"Phase {phase['id']} - {phase['name']}"
    separator = "-" * 70

    logger.info("")
    logger.info(separator)
    logger.info(BOLD(f">>  {phase_label}"))
    logger.info(DIM(phase["description"]))
    logger.info(separator)

    cmd = [sys.executable, "-m", phase["module"]]
    logger.info(DIM(f"   Command : {' '.join(cmd)}"))
    logger.info(DIM(f"   Started : {datetime.now(tz=IST).strftime('%H:%M:%S IST')}"))
    logger.info("")

    t0 = time.monotonic()
    output_lines: list[str] = []

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"   # force UTF-8 in subprocess on Windows

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=Path(__file__).parent,
        )

        # Stream output line-by-line
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            output_lines.append(line)
            # Write raw line to log file via logger (DEBUG so it always hits file)
            logger.debug("  |  %s", line)
            # Print to console with indent
            print(f"  |  {line}", flush=True)

        proc.wait()
        exit_code = proc.returncode

    except Exception as exc:
        duration = time.monotonic() - t0
        logger.error("  Phase failed with exception: %s", exc)
        return {
            "id": phase["id"],
            "name": phase["name"],
            "passed": False,
            "exit_code": -1,
            "duration_sec": duration,
            "output_lines": output_lines,
            "error": str(exc),
        }

    duration = time.monotonic() - t0

    if exit_code == 0:
        status_str = GREEN("  [OK]  PASSED")
        logger.info(status_str)
    else:
        status_str = RED(f"  [FAIL]  FAILED  (exit code {exit_code})")
        logger.error(status_str)

    logger.info(DIM(f"   Duration : {duration:.1f}s"))
    logger.info("")

    return {
        "id": phase["id"],
        "name": phase["name"],
        "passed": exit_code == 0,
        "exit_code": exit_code,
        "duration_sec": duration,
        "output_lines": output_lines,
    }


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(results: list[dict], total_duration: float, logger: logging.Logger) -> None:
    separator = "=" * 70
    logger.info("")
    logger.info(separator)
    logger.info(BOLD("  INGESTION RUN SUMMARY"))
    logger.info(separator)

    all_passed = all(r["passed"] for r in results)
    overall = GREEN("ALL PHASES PASSED [OK]") if all_passed else RED("ONE OR MORE PHASES FAILED [FAIL]")
    logger.info(f"  Overall   : {overall}")
    logger.info(f"  Total time: {total_duration:.1f}s")
    logger.info(f"  Log file  : {LOG_FILE}")
    logger.info("")
    logger.info(f"  {'Phase':<8} {'Name':<30} {'Status':<10} {'Duration':>10}")
    logger.info(f"  {'-'*8} {'-'*30} {'-'*10} {'-'*10}")

    for r in results:
        status = GREEN("PASSED") if r["passed"] else RED("FAILED")
        logger.info(
            f"  {r['id']:<8} {r['name']:<30} {status:<10} {r['duration_sec']:>8.1f}s"
        )

    logger.info("")
    logger.info(separator)

    if not all_passed:
        failed = [r for r in results if not r["passed"]]
        logger.info("")
        logger.info(RED("  Failed phases:"))
        for r in failed:
            logger.info(RED(f"    [FAIL]  Phase {r['id']} - {r['name']}  (exit code {r.get('exit_code', '?')})"))
        logger.info("")
        logger.info("  Check the log file for full output:")
        logger.info(f"  {LOG_FILE}")

    logger.info("")


# ---------------------------------------------------------------------------
# Env var check
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = [
    ("CHROMA_API_KEY",  "Chroma Cloud authentication"),
    ("CHROMA_TENANT",   "Chroma Cloud tenant ID"),
    ("CHROMA_DATABASE", "Chroma Cloud database name"),
]

def _check_env(logger: logging.Logger) -> bool:
    missing = [
        (var, desc) for var, desc in REQUIRED_ENV_VARS
        if not os.environ.get(var, "").strip()
    ]
    if missing:
        logger.error(RED("  Missing required environment variables:"))
        for var, desc in missing:
            logger.error(RED(f"    [FAIL]  {var}  ({desc})"))
        logger.error("")
        logger.error("  Set them in your .env file or export them before running.")
        return False
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    logger, _ = _setup_logging()

    header = "=" * 70
    run_time = datetime.now(tz=IST).strftime("%Y-%m-%d %H:%M:%S IST")

    logger.info(header)
    logger.info(BOLD("  HDFC MF FAQ - LOCAL INGESTION SCHEDULER"))
    logger.info(f"  Run started : {run_time}")
    logger.info(f"  Log file    : {LOG_FILE}")
    logger.info(f"  Phases      : {', '.join(p['id'] for p in PHASES)}")
    logger.info(header)

    # Pre-flight env check
    logger.info("")
    logger.info(BOLD("  Pre-flight checks"))
    if not _check_env(logger):
        logger.error(RED("  Aborting - fix missing env vars and re-run."))
        return 1
    logger.info(GREEN("  [OK]  All required environment variables present"))
    logger.info("")

    # Run phases sequentially — stop on first failure
    results: list[dict] = []
    pipeline_start = time.monotonic()

    for phase in PHASES:
        result = _run_phase(phase, logger)
        results.append(result)

        if not result["passed"]:
            logger.error(
                RED(f"  Phase {phase['id']} failed - stopping pipeline to avoid cascading errors.")
            )
            # Add skipped entries for remaining phases
            remaining = PHASES[len(results):]
            for skipped in remaining:
                results.append({
                    "id": skipped["id"],
                    "name": skipped["name"],
                    "passed": False,
                    "exit_code": "skipped",
                    "duration_sec": 0.0,
                    "output_lines": [],
                    "error": f"Skipped because Phase {phase['id']} failed.",
                })
            break

    total_duration = time.monotonic() - pipeline_start
    _print_summary(results, total_duration, logger)

    all_passed = all(r["passed"] for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
