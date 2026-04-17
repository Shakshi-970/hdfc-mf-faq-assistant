# Phase 4.2 — Evaluation

RAG quality metrics to measure retrieval precision and answer correctness.

## Metrics

| Metric | Description | Tool |
|---|---|---|
| **Retrieval Precision@K** | Are the top-K chunks relevant to the query? | Manual golden set + cosine score threshold |
| **Answer Faithfulness** | Does the answer contain only facts from the retrieved chunks? | LLM-as-judge (Claude) |
| **Answer Relevance** | Does the answer actually address the user's question? | LLM-as-judge (Claude) |
| **Context Recall** | Were all relevant chunks retrieved? | Golden chunk set comparison |
| **Classifier Accuracy** | Are factual / advisory / OOS queries classified correctly? | Labelled query set |

## Planned structure

```
phase_4_2_evaluation/
├── golden_queries.json        ← hand-labelled (query, expected_class, expected_chunks[])
├── run_eval.py                ← end-to-end evaluation runner
├── metrics.py                 ← faithfulness, relevance, precision calculators
└── report.md                  ← evaluation results (generated)
```

## Status

Not yet implemented.
