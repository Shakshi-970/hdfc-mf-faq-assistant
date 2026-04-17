"""
phases/phase_6/phase_6_1_groq_pipeline
---------------------------------------
Groq-backed query pipeline for the Mutual Fund FAQ Assistant.

Public API:
  from phases.phase_6.phase_6_1_groq_pipeline.pipeline import run_query
  from phases.phase_6.phase_6_1_groq_pipeline.llm_client import get_llm_client

Environment variables:
  LLM_PROVIDER  — "groq" (default) or "claude"
  GROQ_API_KEY  — required when LLM_PROVIDER=groq
  GROQ_MODEL    — Groq model ID (default: llama-3.3-70b-versatile)
  ANTHROPIC_API_KEY — required when LLM_PROVIDER=claude
"""
