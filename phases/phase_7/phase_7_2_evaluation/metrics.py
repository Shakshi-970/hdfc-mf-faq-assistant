"""
phases/phase_7/phase_7_2_evaluation/metrics.py
-----------------------------------------------
Metric calculations for RAG pipeline evaluation.

All functions take a list of result dicts produced by evaluator.py and
return a scalar or dict. No external dependencies.

Metrics:
  classification_accuracy  — % queries classified with the expected class
  refusal_accuracy         — % advisory/OOS/PII queries correctly refused
  retrieval_hit_rate       — % factual queries whose source_url matches the expected scheme
  latency_stats            — P50 / P95 / min / max latency in milliseconds
  summary_report           — formatted string of all metrics in one call
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Individual metrics
# ---------------------------------------------------------------------------

def classification_accuracy(results: list[dict]) -> float:
    """
    Fraction of queries where actual query_class matches expected_class.

    Parameters
    ----------
    results : list of result dicts from evaluator.py (must have
              'expected_class' and 'actual_class' keys).

    Returns
    -------
    float in [0, 1]
    """
    if not results:
        return 0.0
    correct = sum(
        1 for r in results
        if r.get("actual_class") == r.get("expected_class")
    )
    return correct / len(results)


def refusal_accuracy(results: list[dict]) -> float:
    """
    Fraction of advisory / out_of_scope / pii_risk queries that were
    correctly refused (no source_url returned).

    A refusal is correct when the pipeline returned no source_url AND
    the expected class is one of the three refusal categories.
    """
    refusal_classes = {"advisory", "out_of_scope", "pii_risk"}
    target = [r for r in results if r.get("expected_class") in refusal_classes]
    if not target:
        return 0.0
    # Correctly refused = query_class matched + no source_url
    correct = sum(
        1 for r in target
        if r.get("actual_class") == r.get("expected_class")
        and r.get("source_url") is None
    )
    return correct / len(target)


def retrieval_hit_rate(results: list[dict]) -> float:
    """
    Fraction of factual queries where the returned source_url contains
    the expected URL fragment (e.g. 'hdfc-large-cap-fund-direct-growth').

    Measures whether the retriever fetched the right scheme's chunks.
    """
    factual = [
        r for r in results
        if r.get("expected_class") == "factual"
        and r.get("expected_url_fragment")
    ]
    if not factual:
        return 0.0
    hits = sum(
        1 for r in factual
        if r.get("source_url")
        and r["expected_url_fragment"] in r["source_url"]
    )
    return hits / len(factual)


def latency_stats(results: list[dict]) -> dict:
    """
    Latency percentiles (P50, P95) and range in milliseconds.

    Only includes rows that have a 'latency_ms' key.
    """
    times = sorted(r["latency_ms"] for r in results if "latency_ms" in r)
    if not times:
        return {"count": 0}
    n = len(times)
    return {
        "count": n,
        "p50_ms":  times[n // 2],
        "p95_ms":  times[min(int(n * 0.95), n - 1)],
        "min_ms":  times[0],
        "max_ms":  times[-1],
        "mean_ms": round(sum(times) / n),
    }


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------

def summary_report(results: list[dict], llm_provider: str = "unknown") -> str:
    """
    Build a formatted plain-text evaluation report.

    Parameters
    ----------
    results      : list of result dicts from evaluator.py
    llm_provider : provider string to include in the header

    Returns
    -------
    Multi-line string suitable for printing or writing to a file.
    """
    cls_acc  = classification_accuracy(results)
    ref_acc  = refusal_accuracy(results)
    ret_hit  = retrieval_hit_rate(results)
    lat      = latency_stats(results)

    total    = len(results)
    factual  = sum(1 for r in results if r.get("expected_class") == "factual")
    refusals = total - factual
    errors   = sum(1 for r in results if r.get("error"))

    lines = [
        "=" * 60,
        "  Mutual Fund FAQ — RAG Evaluation Report",
        "=" * 60,
        f"  LLM provider  : {llm_provider}",
        f"  Total queries : {total}  (factual: {factual}, refusals: {refusals})",
        f"  Errors        : {errors}",
        "-" * 60,
        f"  Classification accuracy : {cls_acc * 100:.1f}%",
        f"  Refusal accuracy        : {ref_acc * 100:.1f}%",
        f"  Retrieval hit rate      : {ret_hit * 100:.1f}%",
        "-" * 60,
    ]

    if lat.get("count", 0) > 0:
        lines += [
            f"  Latency P50  : {lat['p50_ms']} ms",
            f"  Latency P95  : {lat['p95_ms']} ms",
            f"  Latency mean : {lat['mean_ms']} ms",
            f"  Latency range: {lat['min_ms']}–{lat['max_ms']} ms",
        ]
    else:
        lines.append("  Latency      : no data")

    lines.append("=" * 60)
    return "\n".join(lines)
