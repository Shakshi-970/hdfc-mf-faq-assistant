# Phase 4.4 — Monitoring

Structured logging, metrics, and alerting for production operations.

## What to monitor

| Signal | Source | Alert condition |
|---|---|---|
| Ingestion success / failure | GitHub Actions job status | Any step exits non-zero |
| Upsert chunk count | `last_run_report.json` | `upserted == 0` when changed schemes exist |
| API error rate | FastAPI 503 responses | Error rate > 5% over 5 min |
| API latency (P95) | Response time per `/chat` request | P95 > 10 s |
| Active sessions | `GET /health` → `active_sessions` | Spike indicating traffic anomaly |
| Chroma Cloud reachability | Upsert step HTTP response | `401` / `503` from api.trychroma.com |

## Planned structure

```
phase_4_4_monitoring/
├── log_config.py          ← structured JSON logging setup (for FastAPI)
├── healthcheck.py         ← hits /health endpoint; exits non-zero if unhealthy
└── README.md
```

## Status

Not yet implemented.
