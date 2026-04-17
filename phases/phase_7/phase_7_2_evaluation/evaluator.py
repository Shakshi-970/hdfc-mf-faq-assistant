"""
phases/phase_7/phase_7_2_evaluation/evaluator.py
-------------------------------------------------
RAG pipeline evaluator — runs the golden Q&A set through the live pipeline
and prints a quality report.

Usage:
    python -m phases.phase_7.phase_7_2_evaluation.evaluator

    # Use Claude instead of Groq
    LLM_PROVIDER=claude python -m phases.phase_7.phase_7_2_evaluation.evaluator

    # Save JSON results to a file
    python -m phases.phase_7.phase_7_2_evaluation.evaluator --out results.json

Required environment variables (same as Phase 6):
    GROQ_API_KEY, CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE

What it measures:
    - Classification accuracy  (actual vs expected query class)
    - Refusal accuracy         (advisory / OOS / PII correctly refused)
    - Retrieval hit rate       (source_url matches expected scheme)
    - Latency P50 / P95        (ms per query, wall-clock)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env before importing any phase module (Chroma / Groq creds needed)
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    env_path = Path(__file__).parents[3] / ".env"   # repo root/.env
    if not env_path.exists():
        return
    with open(env_path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

_load_dotenv()

# ---------------------------------------------------------------------------
# Now import pipeline
# ---------------------------------------------------------------------------

from phases.phase_3.phase_3_5_session_manager import create_session
from phases.phase_6.phase_6_1_groq_pipeline.pipeline import _get_llm, run_query

from .metrics import summary_report

_HERE = Path(__file__).parent
_QUESTIONS_PATH = _HERE / "eval_questions.json"


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate(questions_path: Path = _QUESTIONS_PATH) -> list[dict]:
    """
    Run all questions in the golden set through the pipeline.

    Returns a list of result dicts, one per question, each with:
      id, query, expected_class, expected_url_fragment,
      actual_class, source_url, last_updated, answer,
      llm_provider, latency_ms, error (if any)
    """
    with open(questions_path) as f:
        data = json.load(f)

    questions = data["questions"]
    print(f"Loaded {len(questions)} evaluation questions from {questions_path.name}")
    print(f"LLM provider: {os.environ.get('LLM_PROVIDER', 'groq')}")
    print()

    # Single shared session for all eval queries (stateless enough for eval)
    session_id = create_session()

    results: list[dict] = []

    for q in questions:
        qid   = q["id"]
        query = q["query"]

        t0 = time.perf_counter()
        pipeline_result = run_query(session_id, query)
        latency_ms = round((time.perf_counter() - t0) * 1000)

        # Determine llm_provider (only set on factual answers)
        try:
            provider = _get_llm().provider_name
        except Exception:
            provider = "unavailable"

        row = {
            "id":                    qid,
            "query":                 query,
            "expected_class":        q["expected_class"],
            "expected_url_fragment": q.get("expected_url_fragment"),
            "actual_class":          pipeline_result.get("query_class"),
            "source_url":            pipeline_result.get("source_url"),
            "last_updated":          pipeline_result.get("last_updated"),
            "answer":                pipeline_result.get("answer", ""),
            "llm_provider":          pipeline_result.get("llm_provider", provider),
            "latency_ms":            latency_ms,
        }
        if "error" in pipeline_result:
            row["error"] = pipeline_result["error"]

        results.append(row)

        # Progress line
        status = "OK " if "error" not in row else "ERR"
        match = "✓" if row["actual_class"] == row["expected_class"] else "✗"
        print(
            f"  [{status}] {qid}  {match}class={row['actual_class']:<12} "
            f"{latency_ms:>5} ms  {query[:55]}"
        )

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the Mutual Fund FAQ RAG pipeline."
    )
    parser.add_argument(
        "--questions",
        default=str(_QUESTIONS_PATH),
        help="Path to eval_questions.json (default: bundled golden set)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write JSON results (e.g. results.json)",
    )
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  Mutual Fund FAQ — RAG Evaluation")
    print("=" * 60)
    print()

    try:
        results = evaluate(Path(args.questions))
    except EnvironmentError as exc:
        print(f"\n[ERROR] Missing environment variable: {exc}", file=sys.stderr)
        print("Set GROQ_API_KEY, CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE", file=sys.stderr)
        return 1

    try:
        provider = _get_llm().provider_name
    except Exception:
        provider = "unknown"

    print()
    print(summary_report(results, llm_provider=provider))

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\nResults saved to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
