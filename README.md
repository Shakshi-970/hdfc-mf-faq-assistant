# HDFC Mutual Fund FAQ Assistant

A **facts-only RAG chatbot** that answers verifiable questions about 5 HDFC Mutual Fund schemes using content scraped exclusively from official Groww scheme pages.

> **Disclaimer: Facts-only. No investment advice.**
> This assistant does not provide investment recommendations, performance comparisons, or opinions of any kind. For personalised guidance, consult a SEBI-registered investment adviser or visit the [AMFI Investor Education Portal](https://www.amfiindia.com/investor-corner/knowledge-center).

---

## Selected AMC and Schemes

**AMC: HDFC Mutual Fund**

| # | Scheme | Category | Source |
|---|---|---|---|
| 1 | HDFC Large Cap Fund (Direct Growth) | Large Cap | [groww.in](https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth) |
| 2 | HDFC Equity Fund (Direct Growth) | Flexi Cap | [groww.in](https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth) |
| 3 | HDFC ELSS Tax Saver Fund (Direct Plan Growth) | ELSS | [groww.in](https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth) |
| 4 | HDFC Mid-Cap Fund (Direct Growth) | Mid Cap | [groww.in](https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth) |
| 5 | HDFC Focused Fund (Direct Growth) | Focused | [groww.in](https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth) |

Fields available per scheme: expense ratio, exit load, minimum SIP, NAV, riskometer, benchmark index, fund manager, AUM, category. ELSS scheme additionally: lock-in period, tax benefit under Section 80C.

---

## Architecture Overview

The system is a **Retrieval-Augmented Generation (RAG)** pipeline with two independent paths:

```
[Daily Ingestion — 09:15 AM IST via GitHub Actions]
  Scraping Service (httpx + BeautifulSoup4)
      → Change Detector (JSON snapshot diff)
      → Chunker (atomic facts + recursive 512-token/64-overlap)
      → Embedder (BAAI/bge-small-en-v1.5, 384-dim, local CPU)
      → Vector Store Upsert (Chroma Cloud, mf_faq_chunks collection)

[Query — Real-time]
  User query
      → Classifier  (PII / advisory / out-of-scope / factual — rule-based, no LLM)
      → Refusal guard (advisory, PII, out-of-scope returned immediately)
      → Rewriter  (abbreviation expansion + scheme name normalisation)
      → Retriever  (Top-5 cosine similarity from Chroma Cloud → re-rank → Top-3)
      → Prompt Constructor  (system prompt + 3 chunks + user query)
      → LLM  (Groq llama-3.3-70b-versatile by default; Claude as fallback)
      → Response Formatter  (3-sentence cap · one Source: URL · Last updated footer)
      → Post-generation Guardrail  (advisory language scan → fallback if triggered)
      → Session Manager  (conversation history per UUID session)
```

Every factual answer is formatted as:

```
{answer — max 3 sentences, grounded in retrieved context only}

Source: {official Groww scheme URL}

Last updated from sources: {YYYY-MM-DD}
```

Full architecture specification: [`docs/rag-architecture.md`](docs/rag-architecture.md)

---

## Environment Setup

### Prerequisites

- Python 3.11+
- Chroma Cloud account ([trychroma.com](https://trychroma.com)) — free tier works
- Groq API key ([console.groq.com](https://console.groq.com)) — free tier works
- Anthropic API key (optional — only needed if `LLM_PROVIDER=claude`)

### 1. Clone and install

```bash
git clone <repo-url>
cd M2
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your keys:
```

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq inference API key |
| `CHROMA_API_KEY` | Yes | Chroma Cloud authentication |
| `CHROMA_TENANT` | Yes | Chroma Cloud tenant ID |
| `CHROMA_DATABASE` | Yes | Chroma Cloud database name |
| `ANTHROPIC_API_KEY` | Optional | Only needed when `LLM_PROVIDER=claude` |
| `LLM_PROVIDER` | Optional | `groq` (default) or `claude` |
| `REDIS_URL` | Optional | Redis for production session store; omit to use in-memory |

---

## Running Locally

### Run the API backend (Phase 6 — Groq pipeline)

```bash
python -m phases.phase_6.phase_6_1_groq_pipeline
# Starts FastAPI on http://localhost:8001
```

Endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/sessions/new` | Create a new chat session |
| `POST` | `/chat/{session_id}` | Send a query |
| `DELETE` | `/sessions/{session_id}` | Expire a session |

### Run the chat UI

```bash
# Make sure the backend is running first, then:
API_BASE_URL=http://localhost:8001 streamlit run phases/phase_3/phase_3_6_ui/app.py
# Opens at http://localhost:8501
```

### Run with Docker Compose

```bash
# From repo root — reads .env automatically
docker compose -f phases/phase_5/phase_5_1_docker/docker-compose.yml up --build
# Backend: http://localhost:8000  |  UI: http://localhost:8501
```

### Run the ingestion pipeline manually

```bash
# 1. Scrape all 5 Groww scheme pages
python -m phases.phase_3.phase_3_3_scraping_service.run

# 2. Chunk and embed the scraped content
python -m phases.phase_3.phase_3_2_chunking_embedding.chunk_and_embed

# 3. Upsert embeddings into Chroma Cloud
python -m phases.phase_3.phase_3_2_chunking_embedding.upsert
```

The ingestion pipeline also runs automatically every day at **09:15 AM IST** via GitHub Actions (`.github/workflows/daily_ingestion.yml`).

---

## Running Tests

```bash
# All unit tests (no API keys required — external calls are mocked)
pytest -v

# Individual test files
pytest phases/phase_7/phase_7_1_unit_tests/test_classifier.py -v
pytest phases/phase_7/phase_7_1_unit_tests/test_rewriter.py -v
pytest phases/phase_7/phase_7_1_unit_tests/test_pipeline.py -v
pytest phases/phase_7/phase_7_1_unit_tests/test_formatter.py -v

# RAG quality evaluation (requires live API keys + Chroma Cloud)
python -m phases.phase_7.phase_7_2_evaluation.evaluator
```

Expected: **95 unit tests passed** in ~0.5 s.

---

## Project Structure

```
M2/
├── README.md                          ← this file
├── problemStatement.md                ← original project brief
├── requirements.txt
├── pytest.ini
├── .env.example
├── .github/workflows/
│   └── daily_ingestion.yml            ← daily cron at 09:15 AM IST
├── docs/
│   ├── rag-architecture.md            ← full architecture specification
│   ├── chunking-and-embedding.md      ← ingestion pipeline detail
│   └── data-storage-design.md        ← vector store schema
└── phases/
    ├── phase_1/                       ← problem definition & design
    ├── phase_2/                       ← scraped corpus data
    │   └── phase_2_1_scraper_data/    ← JSON output + per-scheme snapshots
    ├── phase_3/                       ← core RAG pipeline
    │   ├── phase_3_1_scheduler_github_actions/
    │   ├── phase_3_2_chunking_embedding/
    │   ├── phase_3_3_scraping_service/
    │   ├── phase_3_4_query_pipeline/  ← classifier · rewriter · retriever · prompt
    │   ├── phase_3_5_session_manager/ ← in-memory or Redis session backend
    │   └── phase_3_6_ui/              ← Streamlit chat UI
    ├── phase_4/                       ← QA plans (testing, evaluation, deployment, monitoring)
    ├── phase_5/                       ← Docker deployment + JSON logging + health check
    ├── phase_6/                       ← Groq LLM integration (provider-switchable)
    ├── phase_7/                       ← pytest unit tests + RAG evaluation (20 golden Qs)
    ├── phase_8/                       ← response formatter + post-generation guardrail
    └── phase_9/                       ← project documentation (this README)
```

---

## Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Groww page layout redesign | HTML selectors may break | Resilient attribute selectors; daily scrape health check |
| No PDFs in scope | Full SID/KIM clauses not available | Links user to official scheme page |
| No real-time NAV | Cannot answer "today's NAV" | Redirects to Groww scheme page |
| English only | Hindi/regional queries not handled | Out-of-scope message with AMFI link |
| 5-scheme corpus | Cannot answer about other HDFC schemes | Out-of-scope message lists in-scope schemes |
| LLM hallucination risk | LLM may exceed retrieved context | System prompt strictly grounds answers in retrieved text |

---

## Evaluation Targets

| Metric | Target |
|---|---|
| Classification accuracy | ≥ 95% |
| Refusal accuracy (advisory + OOS + PII) | 100% |
| Retrieval hit rate (factual queries) | ≥ 80% |
| Latency P50 | < 2 000 ms |
| Latency P95 | < 5 000 ms |

Run `python -m phases.phase_7.phase_7_2_evaluation.evaluator` to measure against the 20-question golden set.

---

*Built with Python 3.11 · FastAPI · Streamlit · Groq (llama-3.3-70b-versatile) · Chroma Cloud · BAAI/bge-small-en-v1.5*
