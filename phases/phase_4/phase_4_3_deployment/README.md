# Phase 4.3 — Deployment

Docker packaging and cloud hosting for the FastAPI backend and Streamlit UI.

## Components to deploy

| Component | Target | Notes |
|---|---|---|
| FastAPI backend (`phase_3_4`) | Container (Docker) | Needs `ANTHROPIC_API_KEY` + Chroma Cloud env vars |
| Streamlit UI (`phase_3_6`) | Container (Docker) | Needs `API_BASE_URL` pointing to backend |
| Redis (optional) | Managed Redis (e.g. Upstash) | Only needed for multi-instance horizontal scaling |

## Planned structure

```
phase_4_3_deployment/
├── Dockerfile.backend          ← FastAPI (uvicorn) container
├── Dockerfile.ui               ← Streamlit container
├── docker-compose.yml          ← local multi-container dev environment
└── README.md
```

## Start commands after deployment

```bash
# Backend
python -m phases.phase_3.phase_3_4_query_pipeline    # port 8000

# UI
python -m phases.phase_3.phase_3_6_ui                # port 8501
```

## Status

Not yet implemented.
