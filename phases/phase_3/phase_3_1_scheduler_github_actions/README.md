# Phase 3.1 — Scheduler (GitHub Actions)

Fires the full ingestion pipeline daily at **09:15 AM IST** (03:45 UTC).

## Workflow file

[`.github/workflows/daily_ingestion.yml`](../../.github/workflows/daily_ingestion.yml)

## Trigger

| Type | Value |
|---|---|
| Scheduled | `cron: '45 3 * * *'` — 03:45 UTC = 09:15 AM IST every day |
| Manual | `workflow_dispatch` — one-click re-run from the GitHub Actions UI |

## Secrets and Variables

| Name | Type | Used by |
|---|---|---|
| `OPENAI_API_KEY` | Secret | Phase 3.2 — embedder |
| `VECTOR_STORE_PATH` | Variable | Phase 3.2 — upsert |
| `GROWW_URLS` | Variable | Phase 3.3 — scraper |

## Steps executed

1. Checkout repository
2. Set up Python 3.11
3. `pip install -r requirements.txt`
4. `python -m phases.phase_3_3_scraping_service.run` → writes `scraper/output/scraped_<date>.json`
5. `python -m phases.phase_3_2_chunking_embedding.chunk_and_embed` → writes embedded chunks
6. `python -m phases.phase_3_2_chunking_embedding.upsert` → upserts into ChromaDB / FAISS
7. Write `last_run_report.json` to GitHub job summary

See also: [`docs/rag-architecture.md`](../../docs/rag-architecture.md) §3.1
