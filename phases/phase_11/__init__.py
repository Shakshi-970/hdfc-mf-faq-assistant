"""
phases/phase_11
---------------
Phase 11 — Security and Privacy Controls

Implements Section 11 of docs/rag-architecture.md.

Eight controls are enforced and tested:

  Control                       Module
  ───────────────────────────── ────────────────────────────────────────────
  No PII ingestion              domain_whitelist — corpus-URL allowlist only
  PII query detection           phases/phase_3/phase_3_4_query_pipeline/classifier.py
  No cross-session leakage      phases/phase_3/phase_3_5_session_manager/ (isolated dicts)
  Source domain whitelist       domain_whitelist.validate_url()
  No advisory output            phases/phase_8/phase_8_1_response_formatter/guardrail.py
  HTTPS only                    domain_whitelist.validate_url() (rejects http://)
  No logging of user queries    audit_log.log_query_event() — session_id+class only
  Source domain locked groww.in domain_whitelist.ALLOWED_DOMAIN

  phase_11_1_security/
    domain_whitelist.py  — CORPUS_URLS allowlist, validate_url(), is_corpus_url()
    audit_log.py         — privacy-safe query event logger (no query text in logs)
"""
