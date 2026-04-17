# Phase 5.1 — Docker Deployment

Containerised packaging for the FastAPI backend and Streamlit UI.

## Files

| File | Purpose |
|---|---|
| `Dockerfile.backend` | FastAPI + uvicorn image (port 8000) |
| `Dockerfile.ui` | Streamlit chat UI image (port 8501) |
| `docker-compose.yml` | Multi-container local dev / single-host prod environment |

---

## Quick Start (docker compose)

```bash
# From repo root — docker compose reads .env for ${VAR} substitution
docker compose -f phases/phase_5/phase_5_1_docker/docker-compose.yml up --build
```

| Service | URL |
|---|---|
| FastAPI backend | http://localhost:8000 |
| FastAPI docs (Swagger) | http://localhost:8000/docs |
| Streamlit UI | http://localhost:8501 |

Stop:

```bash
docker compose -f phases/phase_5/phase_5_1_docker/docker-compose.yml down
```

---

## Build individual images

```bash
# Backend
docker build \
  -f phases/phase_5/phase_5_1_docker/Dockerfile.backend \
  -t mf-faq-backend \
  .

# UI
docker build \
  -f phases/phase_5/phase_5_1_docker/Dockerfile.ui \
  -t mf-faq-ui \
  .
```

---

## Run individual containers

```bash
# Backend
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=... \
  -e CHROMA_API_KEY=... \
  -e CHROMA_TENANT=... \
  -e CHROMA_DATABASE=... \
  mf-faq-backend

# UI (point to running backend)
docker run -p 8501:8501 \
  -e API_BASE_URL=http://host.docker.internal:8000 \
  mf-faq-ui
```

---

## Environment variables

| Variable | Required by | Source |
|---|---|---|
| `ANTHROPIC_API_KEY` | backend | GitHub Secret / `.env` |
| `CHROMA_API_KEY` | backend | GitHub Secret / `.env` |
| `CHROMA_TENANT` | backend | GitHub Variable / `.env` |
| `CHROMA_DATABASE` | backend | GitHub Variable / `.env` |
| `API_BASE_URL` | ui | Set in compose; default `http://localhost:8000` |
| `REDIS_URL` | backend | Set in compose; omit for in-memory sessions |

---

## Notes

- **Embedding model pre-cached**: `Dockerfile.backend` downloads `BAAI/bge-small-en-v1.5`
  (~130 MB) during the image build (`RUN python -c "SentenceTransformer(...)"`) so there
  is no cold-start delay on the first query.
- **Redis is optional**: The backend auto-selects in-memory sessions when `REDIS_URL` is
  unset. The compose file wires Redis so horizontal scaling works without code changes.
- **Health check**: Docker polls `GET /health` every 30 s. The container is marked
  unhealthy after 3 consecutive failures, triggering an automatic restart.
