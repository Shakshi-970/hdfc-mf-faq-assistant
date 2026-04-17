"""
phases/phase_3_1_scheduler_github_actions
------------------------------------------
Phase 3.1 — Scheduler (GitHub Actions)

The scheduler is a GitHub Actions workflow that fires daily at 09:15 AM IST.
All orchestration logic lives in the workflow YAML; there is no runtime Python
code in this phase.

Workflow file : .github/workflows/daily_ingestion.yml
Cron trigger  : '45 3 * * *'  (03:45 UTC = 09:15 AM IST)
Manual trigger: workflow_dispatch (available from the GitHub Actions UI)

See docs/rag-architecture.md §3.1 for full specification.
"""
