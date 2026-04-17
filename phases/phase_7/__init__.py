"""
phases/phase_7
--------------
Phase 7 — Testing and Evaluation.

Subpackages:
  phase_7_1_unit_tests  — pytest unit tests for classifier, rewriter, and pipeline
                          (no API keys required — retriever and LLM are mocked)
  phase_7_2_evaluation  — RAG quality evaluation against a golden Q&A set
                          (requires live GROQ_API_KEY + Chroma Cloud credentials)

Run unit tests:
    pytest phases/phase_7/phase_7_1_unit_tests/ -v

Run evaluation:
    python -m phases.phase_7.phase_7_2_evaluation.evaluator
"""
