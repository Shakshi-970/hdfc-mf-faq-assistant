"""
phases/phase_3_4_query_pipeline
--------------------------------
Phase 3.4 — Query Pipeline (Online / Real-time)

Handles all incoming user queries:
  1. Query Classifier  — classifies as factual / advisory / out-of-scope / pii-risk
  2. Intent Validator  — returns refusal message for advisory or pii-risk queries
  3. Query Rewriter    — expands abbreviations, adds domain context
  4. Query Embedder    — converts query to dense vector (same model as ingestion)
  5. Vector Store      — top-K cosine search over indexed chunks
  6. Re-Ranker         — metadata filter + relevance re-rank; selects top-3
  7. Prompt Builder    — system prompt + chunks + user query
  8. LLM              — Claude / GPT-4o; generates grounded, citation-backed answer
  9. Response Formatter — enforces 3-sentence cap, 1 citation, date footer

Status: not yet implemented — see docs/rag-architecture.md §3.4
"""
