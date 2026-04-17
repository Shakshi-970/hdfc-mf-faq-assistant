# Phase 5.2 — Monitoring

Structured logging and liveness health check for production operations.

## Files

| File | Purpose |
|---|---|
| `log_config.py` | Replaces default plaintext logs with structured JSON for log aggregators |
| `healthcheck.py` | CLI script — hits `/health`, exits 0 (healthy) or 1 (unhealthy) |

---

## log_config.py

### What it does

Reconfigures the root Python logger to emit one JSON object per line:

```json
{"timestamp":"2026-04-16T09:15:00.123+00:00","level":"INFO",
 "logger":"phases.phase_3.phase_3_4_query_pipeline.app",
 "message":"New session created: abc123",
 "session_id":"abc123"}
```

Structured logs are directly ingestible by AWS CloudWatch, GCP Cloud Logging,
Datadog, Elastic, and most SaaS log platforms — no regex parsing required.

### Usage

Call once at application startup in [app.py](../../../phase_3/phase_3_4_query_pipeline/app.py):

```python
from phases.phase_5.phase_5_2_monitoring.log_config import configure_logging
configure_logging()          # default level: INFO
configure_logging("DEBUG")   # more verbose
```

### Optional structured fields

Attach extra context to any log record:

```python
logger.info("Query processed", extra={
    "session_id": session_id,
    "query_class": "factual",
    "latency_ms": 342,
})
```

---

## healthcheck.py

### What it does

Hits `GET /health` and checks that `status == "ok"`.

```
[healthy]   http://localhost:8000/health — version=1.0.0, active_sessions=3
[unhealthy] http://localhost:8000/health — connection error: <urlopen error ...>
```

Exit codes:
- `0` — healthy
- `1` — unhealthy or unreachable

Uses only the Python standard library — works inside a slim Docker container
without any extra packages.

### Usage

```bash
# Default (localhost:8000)
python phases/phase_5/phase_5_2_monitoring/healthcheck.py

# Custom URL
python phases/phase_5/phase_5_2_monitoring/healthcheck.py --url http://api:8000/health
```

### Docker HEALTHCHECK

Already wired into `Dockerfile.backend`:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python phases/phase_5/phase_5_2_monitoring/healthcheck.py || exit 1
```

---

## Signals to monitor in production

| Signal | Source | Alert condition |
|---|---|---|
| Ingestion success / failure | GitHub Actions job status | Any step exits non-zero |
| Upsert chunk count | `last_run_report.json` → `upserted` | `upserted == 0` when changes exist |
| API error rate | FastAPI 503 responses | Error rate > 5% over 5 min |
| API latency (P95) | `latency_ms` in structured logs | P95 > 10 s |
| Active sessions | `GET /health` → `active_sessions` | Spike indicating traffic anomaly |
| Chroma Cloud reachability | Upsert step HTTP response | 401 / 503 from api.trychroma.com |
