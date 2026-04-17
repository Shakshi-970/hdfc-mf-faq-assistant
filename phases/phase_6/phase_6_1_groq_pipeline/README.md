# Phase 6.1 — Groq-Backed Query Pipeline

Replaces the LLM generation step with **Groq inference** (default: `llama-3.3-70b-versatile`).
Every other component — classifier, rewriter, retriever, session manager — is imported
directly from Phase 3 with no duplication.

## Why Groq?

| Property | Groq | Claude (Phase 3) |
|---|---|---|
| Latency | ~200 ms P50 (LPU hardware) | ~1–2 s P50 |
| Cost | Free tier + cheap pay-as-you-go | Per-token billing |
| Model | Open-weight (Llama 3.3, Mixtral, Gemma 2) | Proprietary |
| API key | `GROQ_API_KEY` from console.groq.com | `ANTHROPIC_API_KEY` |

---

## Quick start

```bash
# Set environment (add GROQ_API_KEY to your .env)
export GROQ_API_KEY=gsk_...
export CHROMA_API_KEY=...
export CHROMA_TENANT=...
export CHROMA_DATABASE=...

# Start Phase 6 backend (port 8001)
python -m phases.phase_6.phase_6_1_groq_pipeline

# Phase 3 Claude backend still works on port 8000
python -m phases.phase_3.phase_3_4_query_pipeline
```

---

## Provider switching

Control the LLM backend via the `LLM_PROVIDER` env var:

```bash
# Groq (default)
LLM_PROVIDER=groq python -m phases.phase_6.phase_6_1_groq_pipeline

# Fall back to Claude
LLM_PROVIDER=claude ANTHROPIC_API_KEY=... python -m phases.phase_6.phase_6_1_groq_pipeline
```

---

## Supported Groq models

Set `GROQ_MODEL` to override the default:

| Model ID | Size | Best for |
|---|---|---|
| `llama-3.3-70b-versatile` | 70B | **Default** — highest quality |
| `llama3-8b-8192` | 8B | Ultra-fast; lower quality |
| `mixtral-8x7b-32768` | 8×7B | Long context; good reasoning |
| `gemma2-9b-it` | 9B | Fast; Google-trained |

```bash
GROQ_MODEL=mixtral-8x7b-32768 python -m phases.phase_6.phase_6_1_groq_pipeline
```

---

## REST API

Same contract as Phase 3.4 — the Streamlit UI works with both backends.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — includes `llm_provider` field |
| `POST` | `/sessions/new` | Create session → returns `session_id` UUID |
| `POST` | `/chat/{session_id}` | Submit query → returns answer + citation + `llm_provider` |
| `DELETE` | `/sessions/{session_id}` | Expire session |

### Health response (Phase 6 extra field)

```json
{
  "status": "ok",
  "version": "2.0.0",
  "active_sessions": 3,
  "llm_provider": "groq/llama-3.3-70b-versatile"
}
```

### Chat response (Phase 6 extra field)

```json
{
  "session_id": "abc123",
  "answer": "The HDFC ELSS Tax Saver Fund has a lock-in period of 3 years...",
  "source_url": "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
  "last_updated": "2026-04-16",
  "query_class": "factual",
  "llm_provider": "groq/llama-3.3-70b-versatile"
}
```

---

## Point the Streamlit UI to Phase 6

```bash
# Start Phase 6 backend
python -m phases.phase_6.phase_6_1_groq_pipeline   # port 8001

# Start UI pointed at Phase 6
API_BASE_URL=http://localhost:8001 python -m phases.phase_3.phase_3_6_ui
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes (Groq) | — | Get at console.groq.com |
| `ANTHROPIC_API_KEY` | Yes (Claude) | — | Required only if LLM_PROVIDER=claude |
| `LLM_PROVIDER` | No | `groq` | `"groq"` or `"claude"` |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Any Groq model ID |
| `LLM_MAX_TOKENS` | No | `512` | Max output tokens |
| `API_PORT` | No | `8001` | FastAPI bind port |
| `CHROMA_API_KEY` | Yes | — | Chroma Cloud auth |
| `CHROMA_TENANT` | Yes | — | Chroma Cloud tenant |
| `CHROMA_DATABASE` | Yes | — | Chroma Cloud database |
| `REDIS_URL` | No | — | Redis for session store (omit = in-memory) |

---

## Architecture

```
User Query
    │
    ▼
[Phase 3] classify_query      ← rule-based, no LLM call
    │
    ▼ (factual only)
[Phase 3] rewrite_query       ← abbreviation expansion
    │
    ▼
[Phase 3] retrieve            ← bge-small-en-v1.5 + Chroma Cloud
    │
    ▼
[Phase 3] build_messages      ← system prompt + context chunks
    │
    ▼  ← only this step changes vs Phase 3
[Phase 6] LLMClient.generate  ← Groq (llama-3.3-70b-versatile)
    │                            or Claude (fallback)
    ▼
Return answer + source_url + last_updated + llm_provider
```
