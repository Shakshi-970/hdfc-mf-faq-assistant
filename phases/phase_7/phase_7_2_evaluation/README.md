# Phase 7.2 — RAG Evaluation

Runs 20 golden questions through the live pipeline and reports quality metrics.  
**Requires live API keys** (GROQ_API_KEY + Chroma Cloud).

## Files

| File | Purpose |
|---|---|
| `eval_questions.json` | 20 golden questions: 15 factual (all 5 HDFC schemes) + 5 refusals |
| `metrics.py` | Pure functions: classification accuracy, refusal accuracy, retrieval hit rate, latency stats |
| `evaluator.py` | Runs the golden set, prints metrics report, optionally saves JSON results |

---

## Quick start

```bash
# Run from repo root (reads .env automatically)
python -m phases.phase_7.phase_7_2_evaluation.evaluator

# Save raw results to JSON
python -m phases.phase_7.phase_7_2_evaluation.evaluator --out eval_results.json

# Use Claude instead of Groq
LLM_PROVIDER=claude python -m phases.phase_7.phase_7_2_evaluation.evaluator
```

---

## Metrics explained

| Metric | Formula | Target |
|---|---|---|
| **Classification accuracy** | Correct class / total queries | ≥ 95% |
| **Refusal accuracy** | Correctly refused (advisory + OOS + PII) / all refusal queries | 100% |
| **Retrieval hit rate** | Factual queries where source_url contains expected scheme URL fragment | ≥ 80% |
| **Latency P50** | Median query latency (wall-clock, ms) | < 2 000 ms |
| **Latency P95** | 95th percentile query latency | < 5 000 ms |

---

## Example output

```
============================================================
  Mutual Fund FAQ — RAG Evaluation
============================================================

Loaded 20 evaluation questions from eval_questions.json
LLM provider: groq

  [OK ] q01  ✓class=factual       312 ms  What is the expense ratio of HDFC Large Cap Fund?
  [OK ] q02  ✓class=factual       287 ms  What is the benchmark index of HDFC Large Cap Fund?
  ...
  [OK ] q16  ✓class=advisory       14 ms  Should I invest in HDFC ELSS for tax saving?
  [OK ] q20  ✓class=pii_risk        8 ms  My PAN is ABCDE1234F what is my SIP status?

============================================================
  Mutual Fund FAQ — RAG Evaluation Report
============================================================
  LLM provider  : groq/llama-3.3-70b-versatile
  Total queries : 20  (factual: 15, refusals: 5)
  Errors        : 0
------------------------------------------------------------
  Classification accuracy : 100.0%
  Refusal accuracy        : 100.0%
  Retrieval hit rate      : 93.3%
------------------------------------------------------------
  Latency P50  : 298 ms
  Latency P95  : 412 ms
  Latency mean : 271 ms
  Latency range: 8–512 ms
============================================================
```

---

## Golden question set

| Category | Count | Schemes covered |
|---|---|---|
| Factual — expense ratio | 3 | Large Cap, Mid-Cap, Focused |
| Factual — NAV | 1 | Equity |
| Factual — exit load | 2 | Equity, Focused |
| Factual — lock-in / tax | 2 | ELSS |
| Factual — benchmark / AUM / risk / manager | 5 | Large Cap, Equity, Mid-Cap, Focused |
| Refusal — advisory | 2 | — |
| Refusal — out of scope | 2 | — |
| Refusal — PII | 1 | — |
| **Total** | **20** | |
