# RAG Architecture: Mutual Fund FAQ Assistant

## 1. System Overview

The Mutual Fund FAQ Assistant is a **Retrieval-Augmented Generation (RAG)** system that answers factual queries about mutual fund schemes using exclusively official public sources. The architecture is designed to be:

- **Facts-only**: No investment advice, recommendations, or opinions
- **Source-transparent**: Every answer cites exactly one verifiable source link
- **Compliant**: Aligned with SEBI/AMFI data standards
- **Multi-threaded**: Capable of handling multiple independent chat sessions simultaneously

---

## 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│        DAILY SCHEDULER — GitHub Actions  (09:15 AM IST, every day)  │
│   cron: '45 3 * * *'  →  scrape → chunk → embed → upsert            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  trigger
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       SCRAPING SERVICE                              │
│   Fetch → Parse → Diff → Chunk → Embed → Upsert Vector Store        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  updated vectors + ingestion_date
                           ▼  (independent of query traffic)
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE                             │
│   (Chat UI — Welcome Message, Example Qs, Disclaimer Banner)        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  User Query
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       QUERY PIPELINE                                │
│                                                                     │
│   ┌─────────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│   │  Query Classifier│───▶│ Intent Validator │───▶│Query Rewriter│  │
│   │  (factual vs    │    │ (refuse advisory │    │(expand/clean │  │
│   │   advisory)     │    │  queries)        │    │ the query)   │  │
│   └─────────────────┘    └──────────────────┘    └──────┬───────┘  │
└──────────────────────────────────────────────────────────┼─────────┘
                                                           │
                           ▼ (factual queries only)
┌─────────────────────────────────────────────────────────────────────┐
│                       RETRIEVAL ENGINE                              │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                   Query Embedder                             │  │
│   │          (converts query → dense vector)                     │  │
│   └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│   ┌───────────────────────────▼──────────────────────────────────┐  │
│   │          Vector Store — Chroma Cloud (trychroma.com)          │  │
│   │     Top-K semantic search over indexed document chunks       │  │
│   └───────────────────────────┬──────────────────────────────────┘  │
│                               │  Top-K chunks + metadata            │
│   ┌───────────────────────────▼──────────────────────────────────┐  │
│   │              Metadata Filter & Re-Ranker                     │  │
│   │  (filter by scheme name, AMC, doc type; re-rank by score)    │  │
│   └───────────────────────────┬──────────────────────────────────┘  │
└───────────────────────────────┼─────────────────────────────────────┘
                                │  Retrieved context chunks
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       GENERATION ENGINE                             │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                  Prompt Constructor                          │  │
│   │  System prompt + retrieved chunks + user query              │  │
│   │  + strict facts-only + 3-sentence + citation constraints    │  │
│   └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│   ┌───────────────────────────▼──────────────────────────────────┐  │
│   │       LLM — Groq (llama-3.3-70b-versatile)                   │  │
│   │   Configurable via LLM_PROVIDER (fallback: Claude sonnet-4-6)│  │
│   └───────────────────────────┬──────────────────────────────────┘  │
│                               │                                     │
│   ┌───────────────────────────▼──────────────────────────────────┐  │
│   │                  Response Formatter                          │  │
│   │  • Max 3 sentences                                           │  │
│   │  • Exactly 1 citation link                                   │  │
│   │  • Footer: "Last updated from sources: <date>"               │  │
│   └───────────────────────────┬──────────────────────────────────┘  │
└───────────────────────────────┼─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SESSION MANAGER                                │
│     Multi-thread conversation state (per session_id)               │
│     No PII storage — ephemeral session context only                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Scheduler — GitHub Actions

The scheduler is implemented as a **GitHub Actions workflow** with a daily cron trigger at **09:15 AM IST (03:45 UTC)**. It orchestrates the full ingestion pipeline — scraping → chunking → embedding → vector store upsert — as a single automated workflow run. No always-on process or sidecar is required.

```
┌──────────────────────────────────────────────────────────────────────┐
│                  GITHUB ACTIONS SCHEDULER                            │
│                                                                      │
│   Workflow file : .github/workflows/daily_ingestion.yml              │
│   Trigger       : schedule: cron: '45 3 * * *'   # 03:45 UTC        │
│                   = 09:15 AM IST every day                           │
│   Runner        : ubuntu-latest (GitHub-hosted)                      │
│   Concurrency   : group: ingestion  →  cancel-in-progress: false     │
│                   (never cancel a running ingestion mid-way)         │
│                                                                      │
│   Job: ingest                                                        │
│     Step 1 : Checkout repo                                           │
│     Step 2 : Set up Python 3.11                                      │
│     Step 3 : Install dependencies  (pip install -r requirements.txt) │
│     Step 4 : Phase 3.3 — Run scraping service                        │
│              (python -m phases.phase_3_3_scraping_service.run)       │
│     Step 5 : Phase 3.2 — Run chunking + embedding pipeline           │
│              (python -m phases.phase_3_2_chunking_embedding          │
│               .chunk_and_embed)                                      │
│     Step 6 : Phase 3.2 — Upsert to vector store                      │
│              (python -m phases.phase_3_2_chunking_embedding.upsert)  │
│     Step 7 : Write ingestion summary to job summary                  │
│              (cat phases/phase_3_2_chunking_embedding/               │
│               last_run_report.json >> $GITHUB_STEP_SUMMARY)          │
│     On failure : GitHub sends email alert to repo owner              │
└──────────────────────────────────────────────────────────────────────┘
```

**Workflow YAML**

```yaml
# .github/workflows/daily_ingestion.yml

name: Daily Mutual Fund Data Ingestion

on:
  schedule:
    - cron: '45 3 * * *'      # 03:45 UTC = 09:15 AM IST
  workflow_dispatch:           # allow manual trigger from GitHub UI

concurrency:
  group: ingestion
  cancel-in-progress: false    # never abort a running ingestion job

jobs:
  ingest:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Phase 3.3 — Scrape Groww scheme pages
        run: python -m phases.phase_3_3_scraping_service.run
        env:
          GROWW_URLS: ${{ vars.GROWW_URLS }}   # 5 URLs stored as repo variable

      - name: Phase 3.2 — Chunk and embed content
        run: python -m phases.phase_3_2_chunking_embedding.chunk_and_embed

      - name: Phase 3.2 — Upsert into vector store
        run: python -m phases.phase_3_2_chunking_embedding.upsert
        env:
          CHROMA_API_KEY:  ${{ secrets.CHROMA_API_KEY }}
          CHROMA_TENANT:   ${{ vars.CHROMA_TENANT }}
          CHROMA_DATABASE: ${{ vars.CHROMA_DATABASE }}

      - name: Write ingestion summary
        if: always()
        run: |
          echo "## Ingestion Report — $(date -u '+%Y-%m-%d %H:%M UTC')" >> $GITHUB_STEP_SUMMARY
          echo "- Trigger: scheduled cron (09:15 IST)" >> $GITHUB_STEP_SUMMARY
          if [ -f phases/phase_3_2_chunking_embedding/last_run_report.json ]; then
            echo '```json' >> $GITHUB_STEP_SUMMARY
            cat phases/phase_3_2_chunking_embedding/last_run_report.json >> $GITHUB_STEP_SUMMARY
            echo '```' >> $GITHUB_STEP_SUMMARY
          fi
```

**Secrets and Variables**

| Name | Type | Purpose |
|---|---|---|
| `CHROMA_API_KEY` | Secret | Chroma Cloud authentication |
| `CHROMA_TENANT` | Variable | Chroma Cloud tenant identifier |
| `CHROMA_DATABASE` | Variable | Chroma Cloud database name |
| `GROWW_URLS` | Variable | Newline-separated list of the 5 corpus URLs |

**Failure Handling**

| Scenario | Behaviour |
|---|---|
| Groww URL unreachable | Scraper logs warning; retries 3× with backoff; skips URL on final failure |
| All 5 URLs fail | Workflow step exits non-zero → job fails → GitHub sends email alert to owner |
| Partial scrape (some URLs fail) | Upsert only successful chunks; stale vectors retained for failed URLs |
| Chroma Cloud unreachable | Upsert step exits non-zero → job fails → alert triggered; previous day's vectors intact |
| Workflow missed (GitHub outage) | Re-run manually via `workflow_dispatch` from the Actions UI |

---

### 3.2 Chunking and Embedding Pipeline

**Implementation:** `phases/phase_3_2_chunking_embedding/`  
**Entry points:**
- `python -m phases.phase_3_2_chunking_embedding.chunk_and_embed`
- `python -m phases.phase_3_2_chunking_embedding.upsert`

Full specification: **[docs/chunking-and-embedding.md](chunking-and-embedding.md)**

Summary of what that pipeline does after the scraper runs:
- **Text Normaliser** — strips HTML entities, collapses whitespace, standardises currency/percent symbols
- **Field Splitter** — routes structured key-value fields to the Atomic Fact Chunker; routes free-text paragraphs to the Recursive Text Chunker
- **Atomic Fact Chunker** — one sentence per structured field (expense ratio, exit load, min SIP, etc.) for precise retrieval
- **Recursive Text Chunker** — 512-token chunks with 64-token overlap using `RecursiveCharacterTextSplitter`
- **Metadata Tagger** — attaches `chunk_id` (SHA-256), `source_url`, `scheme_name`, `field_type`, `ingestion_date`, `ingestion_time` to every chunk
- **Embedder** — `BAAI/bge-small-en-v1.5` (384-dim), local CPU via sentence-transformers, batched 32 chunks/call, no API key required
- **Vector Store Upsert** — upsert by `chunk_id` into **Chroma Cloud** (`trychroma.com`) via `chromadb.CloudClient`; writes `phases/phase_3_2_chunking_embedding/last_run_report.json` for GitHub Actions summary

---

### 3.3 Scraping Service

**Implementation:** `phases/phase_3_3_scraping_service/`  
**Entry point:** `python -m phases.phase_3_3_scraping_service.run`

The scraping service is invoked by the scheduler. It fetches, parses, diffs, and indexes all 5 Groww scheme pages. **All sources are HTML — no PDFs are used.**

```
SCHEDULER fires at 09:15 AM IST
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│  URL Dispatcher                                               │
│  • Iterates over the 5 corpus URLs                            │
│  • Spawns one async task per URL (concurrent, not sequential) │
└──────────────────────────┬────────────────────────────────────┘
                           │  5 async tasks in parallel
          ┌────────────────┼──────────────────────┐
          ▼                ▼                      ▼
   [URL 1 task]     [URL 2 task]    ...    [URL 5 task]
          │
          │  Each task follows the same pipeline below:
          ▼
┌───────────────────┐
│  HTTP Fetcher     │   • Library  : httpx (async)
│                   │   • Method   : GET with TLS
│                   │   • Headers  :
│                   │       User-Agent: "MutualFundFAQ-Bot/1.0"
│                   │       Accept-Language: en-US
│                   │   • Timeout  : 15 seconds
│                   │   • Retries  : 3 (exponential backoff: 2s, 4s, 8s)
│                   │   • Rate limit: 1 request/URL, no parallel hits
│                   │                 to same domain (polite crawling)
└────────┬──────────┘
         │  Raw HTML (200 OK)
         ▼
┌───────────────────┐
│  HTML Parser      │   • Library  : BeautifulSoup4 (html.parser)
│  & Field          │   • Actions  :
│  Extractor        │       – Remove: nav, footer, script, style, ads
│                   │       – Extract target fields by CSS selector:
│                   │
│                   │   Field              CSS / Aria Target
│                   │   ──────────────     ─────────────────────────
│                   │   Scheme Name        h1.schemeName or page <title>
│                   │   NAV                [data-field="nav"]
│                   │   Expense Ratio      [data-field="expenseRatio"]
│                   │   Exit Load          [data-field="exitLoad"]
│                   │   Min SIP Amount     [data-field="minSipAmount"]
│                   │   Min Lumpsum        [data-field="minLumpsum"]
│                   │   Riskometer         [data-field="riskLevel"]
│                   │   Benchmark Index    [data-field="benchmark"]
│                   │   Fund Manager       [data-field="fundManager"]
│                   │   AUM                [data-field="aum"]
│                   │   Category           [data-field="category"]
│                   │   Lock-in Period     [data-field="lockIn"]
│                   │     (ELSS only)
│                   │   Tax Benefit        free-text section (ELSS only)
│                   │   Fund House         [data-field="fundHouse"]
└────────┬──────────┘
         │  Structured key-value dict per scheme
         ▼
┌───────────────────┐
│  Change Detector  │   • Compare extracted dict with last stored
│  (Diff Check)     │     snapshot in metadata store
│                   │   • If NO change → skip embed + upsert (no-op)
│                   │   • If CHANGED   → proceed to chunker
│                   │   • Benefit: avoids re-embedding unchanged data
│                   │     every day; reduces LLM/embedding API costs
└────────┬──────────┘
         │  Changed fields only (or full set on first run)
         ▼
┌───────────────────┐
│  Chunker          │   • Fixed-size chunks : 512 tokens
│                   │   • Overlap           : 64 tokens
│                   │   • Strategy          : sentence-boundary aware
│                   │   • Atomic facts rule : each structured field
│                   │     (e.g., expense ratio) stored as its own
│                   │     single-sentence chunk for precise retrieval
└────────┬──────────┘
         │  Text chunks
         ▼
┌───────────────────┐
│  Metadata Tagger  │   Each chunk tagged with:
│                   │   • source_url     (Groww scheme URL)
│                   │   • scheme_name    (e.g., "HDFC ELSS Tax Saver Fund")
│                   │   • amc_name       ("HDFC Mutual Fund")
│                   │   • category       (Large Cap / ELSS / Mid Cap / etc.)
│                   │   • field_type     (expense_ratio / exit_load /
│                   │                     min_sip / riskometer /
│                   │                     benchmark / lock_in / general)
│                   │   • ingestion_date (today's date: YYYY-MM-DD)
│                   │   • ingestion_time (HH:MM IST)
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Embedding Model  │   • Model  : BAAI/bge-small-en-v1.5 (local CPU)
│                   │   • Output : 384-dim vectors
│                   │   • Batch  : 32 chunks per encode() call
│                   │   • No API key required
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Vector Store     │   • Store   : Remote ChromaDB (Chroma Cloud)
│  Upsert           │   • Host    : api.trychroma.com (HTTPS)
│                   │   • Auth    : CHROMA_API_KEY secret
│                   │   • Collection: mf_faq_chunks
│                   │   • Strategy: upsert by chunk_id
│                   │     → old chunk for same field replaced with new
│                   │   • Payload : chunk text + full metadata JSON
│                   │   • After upsert: write snapshot for diff check
└───────────────────┘
```

**Scraping Service — Field Extraction Reference**

| Field | Expected Format | Example Value |
|---|---|---|
| `expense_ratio` | Float % string | `"0.77%"` |
| `exit_load` | Text clause | `"1% if redeemed within 1 year"` |
| `min_sip` | Currency string | `"₹100"` |
| `min_lumpsum` | Currency string | `"₹100"` |
| `riskometer` | Enum string | `"Very High"` |
| `benchmark` | Index name | `"Nifty 50 TRI"` |
| `fund_manager` | Name string | `"Rahul Baijal"` |
| `aum` | Currency string | `"₹27,432 Cr"` |
| `category` | Enum string | `"Large Cap"` |
| `lock_in` | Duration string | `"3 years"` (ELSS only) |
| `nav` | Float string | `"1042.35"` |

### 3.4 Query Pipeline (Online / Real-time)

**Implementation:** `phases/phase_3_4_query_pipeline/`

**Step 1 — Query Classification**

Every incoming query is first classified:

| Class | Description | Action |
|---|---|---|
| `factual` | Asks for a verifiable fund fact | Proceed to retrieval |
| `advisory` | Asks for recommendation/opinion | Return polite refusal |
| `out-of-scope` | Unrelated to mutual funds | Return out-of-scope message |
| `pii-risk` | Contains account/PAN/OTP | Sanitize and refuse |

Classification is **rule-based** (no LLM call) — regex patterns for PII, keyword lists for advisory phrases and off-topic signals, and in-scope mutual fund term matching. Ambiguous queries default to `factual` to avoid over-refusing.

**Step 2 — Intent Validation & Refusal**

Advisory queries trigger a structured refusal response:
```
"This assistant provides facts only and cannot offer investment advice or
 recommendations. For guidance, please visit the AMFI investor education portal:
 https://www.amfiindia.com/investor-corner/knowledge-center"
```

**Step 3 — Query Rewriting**

Factual queries are optionally rewritten to improve retrieval:
- Expand abbreviations (e.g., "ELSS" → "Equity Linked Savings Scheme")
- Add domain context (e.g., "expense ratio" → "total expense ratio mutual fund")
- Normalize scheme names

**Step 4 — Embedding & Retrieval**

- Query is embedded using `BAAI/bge-small-en-v1.5` (same model as ingestion, 384-dim)
- BGE asymmetric retrieval: query text is prefixed with `"Represent this sentence: "` before encoding
- Top-K=5 chunks retrieved via cosine similarity from the `mf_faq_chunks` collection on **Chroma Cloud** (`api.trychroma.com`)
- Connection reuses `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE` from environment
- Metadata filters applied (e.g., restrict to a specific scheme if named in query)
- Chunks re-ranked by relevance score; top-3 selected for context

**Step 5 — Prompt Construction**

```
SYSTEM:
You are a facts-only mutual fund FAQ assistant. Answer using only the provided
context. Do not give investment advice. Limit your answer to 3 sentences.
Always cite the source URL from the context metadata.

CONTEXT:
[Chunk 1 text] — Source: <groww_url>, Scheme: <scheme_name>, Field: <field_type>, Date: <ingestion_date>
[Chunk 2 text] — Source: <groww_url>, Scheme: <scheme_name>, Field: <field_type>, Date: <ingestion_date>
[Chunk 3 text] — Source: <groww_url>, Scheme: <scheme_name>, Field: <field_type>, Date: <ingestion_date>

USER QUERY:
{user_query}

RESPONSE FORMAT:
Answer in ≤3 sentences.
Citation: <single source URL>
Last updated from sources: <ingestion_date>
```

**Step 6 — Response Formatting**

The LLM output is post-processed to enforce:
- 3-sentence cap (truncate at 3rd sentence boundary)
- Exactly one citation link present
- Footer injection: `Last updated from sources: YYYY-MM-DD`
- Strip any advisory language detected in output (guardrail pass)

---

### 3.5 Session Manager

**Implementation:** `phases/phase_3_5_session_manager/`

Supports multiple independent chat threads simultaneously:

```
session_id (UUID)
    │
    ├── conversation_history[]  ← ephemeral, in-memory only
    ├── active_scheme_context   ← last mentioned scheme name
    └── created_at / last_active
```

- **No PII is stored** in any session state
- Sessions are isolated — no cross-contamination between threads
- Session context expires after inactivity (configurable TTL, e.g., 30 min)
- Can be backed by Redis for horizontal scaling

---

## 4. Selected AMC and Schemes

**AMC: HDFC Mutual Fund**

| # | Scheme Name | Category | Source URL |
|---|---|---|---|
| 1 | HDFC Large Cap Fund (Direct Growth) | Large Cap | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 2 | HDFC Equity Fund (Direct Growth) | Flexi Cap | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| 3 | HDFC ELSS Tax Saver Fund (Direct Plan Growth) | ELSS | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |
| 4 | HDFC Mid-Cap Fund (Direct Growth) | Mid Cap | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| 5 | HDFC Focused Fund (Direct Growth) | Focused | https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth |

---

## 5. Corpus Definition

**Source: Groww — HDFC Mutual Fund Scheme Pages (HTML only, no PDFs)**

All content is scraped exclusively from the 5 Groww scheme pages listed below. No PDF documents are used in this version of the corpus.

| # | Scheme Name | URL | Data Available on Page |
|---|---|---|---|
| 1 | HDFC Large Cap Fund (Direct Growth) | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth | Expense ratio, exit load, min SIP, NAV, riskometer, benchmark, fund manager, category |
| 2 | HDFC Equity Fund (Direct Growth) | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth | Expense ratio, exit load, min SIP, NAV, riskometer, benchmark, fund manager, category |
| 3 | HDFC ELSS Tax Saver Fund (Direct Plan Growth) | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth | Expense ratio, exit load, lock-in period, min SIP, NAV, riskometer, benchmark, tax benefit |
| 4 | HDFC Mid-Cap Fund (Direct Growth) | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth | Expense ratio, exit load, min SIP, NAV, riskometer, benchmark, fund manager, category |
| 5 | HDFC Focused Fund (Direct Growth) | https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth | Expense ratio, exit load, min SIP, NAV, riskometer, benchmark, fund manager, category |

**Total: 5 URLs**

**Whitelisted Domain:**
- `groww.in`

> **Note:** No PDFs (factsheets, KIMs, SIDs) are used in the current scope. All knowledge is derived solely from the HTML content rendered on the above Groww scheme pages.

---

## 6. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| LLM | `llama-3.3-70b-versatile` via **Groq** (Phase 6 default); `claude-sonnet-4-6` via Anthropic (Phase 3 fallback) | Ultra-low latency (~200 ms) on Groq LPU hardware; switch providers via `LLM_PROVIDER` env var; `MAX_TOKENS=512` |
| Embedding Model | `BAAI/bge-small-en-v1.5` (local CPU, sentence-transformers) | No API key required; 384-dim; strong retrieval performance |
| Vector Store | Chroma Cloud (`trychroma.com`) | Fully managed, persistent, no self-hosted infra; `chromadb.CloudClient` |
| Scheduler | GitHub Actions (`daily_ingestion.yml`) | Cron `45 3 * * *` (09:15 AM IST); GitHub-hosted runner; `workflow_dispatch` for manual runs; email alerts on failure |
| Scraping Service | `httpx` (async HTTP) + `BeautifulSoup4` (HTML parse) | Async concurrent fetch of 5 URLs; polite rate limiting; 3-retry exponential backoff |
| Change Detection | Python `dict` diff + JSON snapshot per scheme | Skip re-embedding when page content is unchanged; avoids redundant Chroma upserts |
| Chunking | Atomic Fact Chunker + `LangChain RecursiveCharacterTextSplitter` | Atomic: one sentence per structured field; recursive: 512-token / 64-token overlap for free-text |
| Query Classifier | Rule-based (regex + keyword lists) | No LLM call; PII regex → advisory keywords → off-topic exclusions → in-scope signals |
| Query Rewriter | Abbreviation expansion + scheme name normalisation | Expands ELSS, NAV, TER, SIP, AUM etc.; maps shorthand to canonical scheme names |
| Query Pipeline | Custom Python orchestration (classifier → rewriter → retriever → prompt → LLM) | No LangChain/LlamaIndex dependency; direct `chromadb` + `anthropic` SDK calls |
| Session State | In-memory dict (dev) / Redis (prod) | Multi-thread isolation; UUID-keyed; 30-min TTL; controlled by `REDIS_URL` env var |
| API Layer | FastAPI + uvicorn | `GET /health`, `POST /sessions/new`, `POST /chat/{session_id}`, `DELETE /sessions/{session_id}` |
| UI | Streamlit (`phases/phase_3_6_ui/`) | Disclaimer banner, welcome message, 8 example questions, chat bubbles, source citation footer |
| Guardrails | Rule-based classifier refusals (pre-retrieval) | Advisory/PII/out-of-scope caught at Step 1 before any LLM call; no post-generation scanning |

---

## 7. Data Flow (End-to-End)

```
[Ingestion - Daily Batch at 09:15 AM IST]     [Query - Real-time]
──────────────────────────────────────         ──────────────────────────────
Scheduler fires (CronTrigger 09:15 IST)        User types query
    │                                              │
    ▼                                              ▼
URL Dispatcher                          ┌── Rule-based Classifier ──┐
(5 async tasks in parallel)             │  (PII / advisory / OOS /  │
    │                                   │   factual) — no LLM call  │
    ▼                                   └───────────┬───────────────┘
HTTP Fetcher (httpx, 3 retries)                     │
    │                                   ┌───────────┴───────────┐
    ▼                           advisory/OOS/PII         factual
HTML Parser + Field Extractor           │                       │
(BeautifulSoup4)                        ▼                       ▼
    │                           Refusal Response         Query Rewriter
    ▼                                   │           (expand abbrev.,
Change Detector (diff check)            ▼            normalise names)
  ├─ No change → skip (no-op)    Return to User              │
  └─ Changed   → continue                                    ▼
    │                                          Embed Query (bge-small,
    ▼                                           BGE query prefix)
Atomic + Recursive Chunker                               │
(512 tok / 64 overlap)                                   ▼
    │                                     Chroma Cloud Top-K=5 Search
    ▼                                     (cosine, optional scheme filter)
Metadata Tagger                                          │
(source_url, scheme, field_type,                         ▼
 ingestion_date, ingestion_time)          Re-Rank → Top-3 chunks
    │                                                    │
    ▼                                                    ▼
Embed Chunks (bge-small, 384-dim)         Prompt Constructor
    │                                     (system + 3 chunks + query)
    ▼                                                    │
Upsert to Chroma Cloud                                   ▼
+ Save JSON snapshot for diff        Groq llama-3.3-70b-versatile (MAX_TOKENS=512)
    │                                                    │
    ▼                                                    ▼
Write last_run_report.json           Return answer + source_url + last_updated
```

---

## 8. Refusal Handling Logic

```
IF query_class == "advisory":
    response = {
        "answer": "This assistant provides verified facts only and cannot 
                   offer investment advice or fund recommendations.",
        "educational_link": "https://www.amfiindia.com/investor-corner/
                             knowledge-center",
        "footer": "Facts-only. No investment advice."
    }

IF query_class == "performance_comparison":
    response = {
        "answer": "Performance data is available in the official factsheet. 
                   Please refer to the link below for the latest NAV and 
                   returns information.",
        "citation": "<official factsheet URL>",
        "footer": "Last updated from sources: <date>"
    }

IF query_class == "pii_detected":
    response = {
        "answer": "For security, please do not share personal information 
                   such as PAN, account numbers, or OTPs here.",
        "footer": "Facts-only. No investment advice."
    }
```

---

## 9. Response Format Specification

Every factual answer must conform to:

```
{answer}         ← max 3 sentences, grounded in retrieved context
                    no advisory language, no performance predictions

Source: {url}    ← exactly one official URL from chunk metadata

Last updated from sources: {YYYY-MM-DD}
```

**Example:**

> The HDFC ELSS Tax Saver Fund has a mandatory lock-in period of 3 years from the date of each SIP installment, as mandated under Section 80C of the Income Tax Act. The minimum SIP investment amount is ₹500 per month. Investments qualify for a tax deduction of up to ₹1.5 lakh per financial year under Section 80C.
>
> Source: https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth
>
> Last updated from sources: 2026-04-16

---

## 10. Multi-Thread Support

```
FastAPI Application
    │
    ├── POST /chat/{session_id}     ← per-thread chat endpoint
    ├── POST /sessions/new          ← create new session
    ├── DELETE /sessions/{id}       ← expire session
    └── GET  /health                ← liveness check

Session Store (Redis or in-memory):
    session_id → {
        history: [...],             ← ephemeral, no PII
        scheme_context: "HDFC Top 100",
        created_at: timestamp,
        last_active: timestamp
    }
```

Each `session_id` is a server-generated UUID. The client stores only this token — no user identity, PAN, or account data is ever associated with a session.

---

## 11. Security and Privacy Controls

| Control | Implementation |
|---|---|
| No PII ingestion | Whitelist-only URL scraping; no user data stored |
| PII query detection | Regex + classifier on incoming query text |
| No cross-session leakage | Sessions are fully isolated in-memory dicts |
| Source domain whitelist | Scraper rejects any URL outside approved domains |
| No advisory output | Post-generation guardrail scans LLM output |
| HTTPS only | All external fetches enforce TLS |
| No logging of user queries | Query logs contain only session_id + timestamp |
| Source domain locked to groww.in | Scraper rejects any URL not in the 5-URL corpus whitelist |

---

## 12. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Groww page layout redesign | HTML selectors may break if Groww restructures the page | Use resilient attribute selectors; daily scrape health check logs failures immediately |
| No PDFs in scope | Detailed SID/KIM clauses (e.g., full exit load slabs) not available | Clearly state limitation; link user to groww.in scheme page for full details |
| No real-time NAV | Cannot answer "what is today's NAV?" | Redirect to the Groww scheme page for live NAV |
| Scheduler downtime | If the scheduler process is down at 09:15 AM, that day's run is missed | coalesce=True fires the job on next restart; alert on missed runs |
| Hindi/regional language queries | System handles English only | Out-of-scope message with AMFI link |
| Ambiguous scheme names | "HDFC Fund" may match multiple schemes | Ask clarifying question or list the 5 in-scope schemes |
| LLM hallucination risk | LLM may generate facts not in retrieved context | System prompt strictly requires grounding in retrieved context only |
| Limited corpus (5 URLs) | Queries about schemes outside the 5 in scope cannot be answered | Return out-of-scope message listing available schemes |

---

## 13. Deployment Architecture

```
  ┌──────────────────────────────────────────────────────────────────┐
  │           SCHEDULER — GitHub Actions                             │
  │   Workflow: .github/workflows/daily_ingestion.yml                │
  │   Cron: '45 3 * * *'  (03:45 UTC = 09:15 AM IST)               │
  │   Runner: ubuntu-latest  |  timeout: 30 min                      │
  │   Manual trigger: workflow_dispatch also available               │
  └──────────────────────────────┬───────────────────────────────────┘
                                 │ fires at 09:15 AM IST
                                 ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                    SCRAPING SERVICE                              │
  │                                                                  │
  │  URL Dispatcher ──► 5 async httpx tasks (concurrent)            │
  │       │                                                          │
  │       ▼                                                          │
  │  HTTP Fetcher  →  HTML Parser  →  Change Detector               │
  │  (httpx async)    (BS4)           (diff vs snapshot)            │
  │       │                                                          │
  │       ▼  (changed content only)                                  │
  │  Chunker  →  Metadata Tagger  →  Embedder      →  Vector Store   │
  │  (512/64)    (url, scheme,        (bge-small-       Upsert       │
  │               field_type,          en-v1.5,         Chroma Cloud │
  │               date, time)          384-dim)         + snapshot   │
  └──────────────────────────────┬───────────────────────────────────┘
                                 │  writes to
                                 ▼
                       ┌──────────────────┐
                       │   Vector DB      │◄──────────────────────┐
                       │  (Chroma Cloud   │                       │
                       │   trychroma.com) │                       │
                       └──────────────────┘                       │
                                                                   │ reads
                        ┌─────────────┐                           │
                        │   Client    │                           │
                        │ (Browser /  │                           │
                        │  Mobile)    │                           │
                        └──────┬──────┘                           │
                               │ HTTPS                            │
                               ▼                                  │
                    ┌──────────────────────┐                      │
                    │   API Gateway /      │                      │
                    │   Load Balancer      │                      │
                    └──────────┬───────────┘                      │
                               │                                  │
              ┌────────────────┼─────────────────┐               │
              ▼                ▼                  ▼               │
      ┌──────────────┐ ┌──────────────┐  ┌──────────────┐        │
      │  FastAPI     │ │  FastAPI     │  │  FastAPI     │        │
      │  Instance 1  │ │  Instance 2  │  │  Instance N  │        │
      └──────┬───────┘ └──────┬───────┘  └──────┬───────┘        │
             │                │                  │                │
             └────────────────┼──────────────────┘                │
                              │                                    │
               ┌──────────────┼──────────────┐                    │
               ▼              ▼              ▼                    │
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
      │  Vector DB   │ │  Redis       │ │  LLM API     │         │
      │  (Chroma     │ │  Session     │ │  (Groq /     │         │
      │   Cloud)     │ │  Store       │ │   Claude)    │         │
      └──────┬───────┘ └──────────────┘ └──────────────┘         │
             └──────────────────────────────────────────────────┘
```

---

*Document generated: 2026-04-16*
*Scope: Mutual Fund FAQ Assistant — RAG Architecture Design*
*Reference: problemStatement.md*
