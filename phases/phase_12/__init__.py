"""
phases/phase_12
---------------
Phase 12 — Known Limitations Mitigations (Section 12, docs/rag-architecture.md).

Architecture requirement (Section 12):
  "Ambiguous scheme names — 'HDFC Fund' may match multiple schemes
   → Ask clarifying question or list the 5 in-scope schemes."

  "No real-time NAV — Cannot answer 'what is today's NAV?'
   → Redirect to the Groww scheme page for live NAV."

Modules
-------
phase_12_1_clarification/
  scheme_resolver.py   — detect_ambiguous_schemes(), is_realtime_nav_query(),
                         clarification_message(), nav_redirect_message()

Pipeline integration (phases/phase_6/phase_6_1_groq_pipeline/pipeline.py):
  Step 2.5 added between the refusal guard and query rewriting:
    • Ambiguous scheme   → clarification_message() returned immediately
    • Real-time NAV ask  → nav_redirect_message() returned immediately
"""
