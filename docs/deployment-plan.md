# Deployment Plan — HDFC Mutual Fund FAQ Assistant

## Overview

| Layer | Platform | Purpose |
|---|---|---|
| Daily ingestion scheduler | GitHub Actions | Scrape → chunk → embed → upsert to Chroma Cloud |
| Backend API | Render | FastAPI + Groq LLM query pipeline |
| Frontend UI | Vercel | Next.js 14 chat interface |

---

## 1. GitHub Actions — Daily Ingestion Scheduler

The ingestion pipeline is already configured at `.github/workflows/daily_ingestion.yml`. No additional setup is needed beyond adding secrets to the repository.

### Schedule
Runs automatically at **09:15 AM IST (03:45 UTC)** every day. Can also be triggered manually from the GitHub Actions UI via `workflow_dispatch`.

### Required GitHub Secrets
Go to **Settings → Secrets and variables → Actions → Secrets** and add:

| Secret name | Where to get it |
|---|---|
| `CHROMA_API_KEY` | Chroma Cloud dashboard → API Keys |

### Required GitHub Variables
Go to **Settings → Secrets and variables → Actions → Variables** and add:

| Variable name | Example value |
|---|---|
| `CHROMA_TENANT` | `1f98fd08-3154-4c37-be62-4d116e515183` |
| `CHROMA_DATABASE` | `Demo` |

### Pipeline steps (automated)
1. **Scrape** — fetches 5 Groww scheme pages concurrently; marks only changed schemes
2. **Chunk + Embed** — normalises text, splits into atomic + recursive chunks, embeds with `BAAI/bge-small-en-v1.5` (local CPU, no API key)
3. **Upsert** — pushes embeddings to Chroma Cloud collection `mf_faq_chunks`
4. **Summary** — posts ingestion report to the GitHub Actions run summary

### HuggingFace model caching
The workflow caches `~/.cache/huggingface/hub` between runs using `actions/cache`. The ~130 MB `BAAI/bge-small-en-v1.5` model is only downloaded on the first run.

---

## 2. Render — Backend API

### Service type
**Web Service** — Python environment (no Docker needed).

### Setup steps

1. Go to [render.com](https://render.com) → **New → Web Service**
2. Connect your GitHub repository
3. Configure the service:

| Setting | Value |
|---|---|
| **Name** | `mf-faq-backend` (or any name) |
| **Region** | Singapore (closest to India) |
| **Branch** | `main` |
| **Root Directory** | *(leave blank — repo root)* |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python -m phases.phase_6.phase_6_1_groq_pipeline` |
| **Instance Type** | Free (512 MB RAM) or Starter ($7/month for no spin-down) |

### Environment variables
Add these under **Environment → Environment Variables**:

| Key | Value | Required |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | Yes |
| `CHROMA_API_KEY` | `ck-...` | Yes |
| `CHROMA_TENANT` | `1f98fd08-...` | Yes |
| `CHROMA_DATABASE` | `Demo` | Yes |
| `LLM_PROVIDER` | `groq` | No (defaults to groq) |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | No (only if using Claude fallback) |

### Health check
Render will call **GET /health** to verify the service is up. The FastAPI backend already exposes this endpoint. Set the health check path to `/health` in Render's service settings.

### Important notes
- **Free tier cold starts**: The free Render instance spins down after 15 minutes of inactivity. The first request after spin-down takes ~30–60 seconds (embedding model reload). Use the **Starter** plan ($7/month) to keep it always-on.
- **Embedding model**: `BAAI/bge-small-en-v1.5` is downloaded from HuggingFace on the first deploy (~130 MB). Subsequent deploys use the cached model.
- The backend **does not need** a `Dockerfile` — Render's native Python runtime handles it directly.

### Backend URL
```
https://hdfc-mf-faq-assistant.onrender.com
```

---

## 3. Vercel — Frontend

### Setup steps

1. Go to [vercel.com](https://vercel.com) → **Add New → Project**
2. Import your GitHub repository
3. Configure the project:

| Setting | Value |
|---|---|
| **Framework Preset** | Next.js *(auto-detected)* |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` *(default)* |
| **Output Directory** | `.next` *(default)* |
| **Install Command** | `npm install` *(default)* |
| **Node.js Version** | 18.x or 20.x |

### Environment variables
Add under **Settings → Environment Variables**:

| Key | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://hdfc-mf-faq-assistant.onrender.com` |

> Set this for **Production**, **Preview**, and **Development** environments.

### Deploy
Click **Deploy**. Vercel builds and deploys automatically. Subsequent pushes to `main` trigger automatic redeployments.

### Frontend URL
Vercel provides a URL like:
```
https://mf-faq-ui.vercel.app
```

---

## 4. End-to-End Data Flow (Production)

```
GitHub Actions (09:15 AM IST daily)
    ↓ scrape → chunk → embed → upsert
Chroma Cloud (mf_faq_chunks collection)
    ↑ retrieval queries
Render — FastAPI backend (https://hdfc-mf-faq-assistant.onrender.com)
    ↑ REST API calls (/sessions/new, /chat/{id})
Vercel — Next.js frontend (https://mf-faq-ui.vercel.app)
    ↑ user queries
Browser
```

---

## 5. Environment Variables Summary

### Render (backend)
```
GROQ_API_KEY=gsk_...
CHROMA_API_KEY=ck-...
CHROMA_TENANT=<uuid>
CHROMA_DATABASE=Demo
```

### Vercel (frontend)
```
NEXT_PUBLIC_API_URL=https://hdfc-mf-faq-assistant.onrender.com
```

### GitHub Actions (ingestion)
```
# Secrets:
CHROMA_API_KEY=ck-...

# Variables:
CHROMA_TENANT=<uuid>
CHROMA_DATABASE=Demo
```

---

## 6. Post-Deployment Checklist

- [ ] GitHub Actions: add `CHROMA_API_KEY` secret and `CHROMA_TENANT`, `CHROMA_DATABASE` variables
- [ ] Trigger `Daily Mutual Fund Data Ingestion` manually once to verify ingestion pipeline
- [ ] Render: deploy backend, confirm `/health` returns `{"status": "ok"}`
- [ ] Vercel: set `NEXT_PUBLIC_API_URL` to Render backend URL, deploy frontend
- [ ] Open the Vercel URL, send a test query, verify response + source link
- [ ] Confirm daily ingestion runs automatically the next morning at 09:15 AM IST
