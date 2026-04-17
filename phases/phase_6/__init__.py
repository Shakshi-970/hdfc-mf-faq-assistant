"""
phases/phase_6
--------------
Phase 6 — Multi-Provider LLM Integration (Groq + Claude).

Subpackages:
  phase_6_1_groq_pipeline — Groq-backed query pipeline with provider-switchable
                             LLM client; reuses all Phase 3 retrieval components.

Key design: phases/phase_3 components (classifier, rewriter, retriever, session
manager) are imported directly — nothing is duplicated. Only the LLM generation
step is replaced by a configurable client controlled via LLM_PROVIDER env var.
"""
