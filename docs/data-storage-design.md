# Data Storage Design
## Mutual Fund FAQ Assistant — Core Fields & Storage Architecture

---

## 1. The 5 Core Fields

These are the primary data points extracted from each of the 5 Groww scheme URLs every day at 09:15 AM IST.

| Field | Internal Key | Source on Groww Page | Example Value |
|---|---|---|---|
| **NAV** | `nav` | NAV section / `__NEXT_DATA__` | `₹1042.35` |
| **Minimum SIP** | `min_sip` | Investment details section | `₹100` |
| **Fund Size** | `aum` | Fund details / AUM section | `₹27,432 Cr` |
| **Expense Ratio** | `expense_ratio` | Fund details section | `0.77%` |
| **Rating** | `rating` | Groww star rating (CRISIL / Value Research) | `4 out of 5` |

> NAV changes every trading day. The other four fields change less frequently but are still re-checked daily and updated only when a change is detected.

---

## 2. Storage Architecture — 3 Layers

Every core field value passes through three storage layers, each serving a distinct purpose.

```
Groww Page (live HTML)
        │
        │  scraper fetches at 09:15 AM IST
        ▼
┌─────────────────────────────────────────────────────┐
│  LAYER 1 — Raw Scraper Output                       │
│  scraper/output/scraped_YYYY-MM-DD.json             │
│  One JSON file per day, 5 scheme records            │
└──────────────────────────┬──────────────────────────┘
                           │
                           │  change detector diffs against snapshot
                           ▼
┌─────────────────────────────────────────────────────┐
│  LAYER 2 — Snapshot Store (Diff Cache)              │
│  scraper/snapshots/<scheme-slug>.json               │
│  One JSON file per scheme, updated daily            │
└──────────────────────────┬──────────────────────────┘
                           │
                           │  changed fields → chunked → embedded
                           ▼
┌─────────────────────────────────────────────────────┐
│  LAYER 3 — Vector Store (ChromaDB)                  │
│  vector_store/  (collection: mf_faq_chunks)         │
│  One vector per field per scheme                    │
│  Queried at runtime to answer user questions        │
└─────────────────────────────────────────────────────┘
```

---

## 3. Layer 1 — Raw Scraper Output JSON

**File:** `scraper/output/scraped_2026-04-16.json`

One file is written per daily run. It contains all 5 scheme records with every extracted field value as a raw string.

```json
[
  {
    "scheme_name"    : "HDFC ELSS Tax Saver Fund Direct Plan Growth",
    "source_url"     : "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "amc"            : "HDFC Mutual Fund",
    "category"       : "ELSS",
    "ingestion_date" : "2026-04-16",
    "ingestion_time" : "09:15",
    "scraped_at"     : "2026-04-16T09:16:42+05:30",
    "_changed"       : true,
    "_is_new"        : false,

    "fields": {
      "nav"            : "1042.35",
      "min_sip"        : "₹100",
      "aum"            : "₹14,230 Cr",
      "expense_ratio"  : "0.77%",
      "rating"         : "4",
      "exit_load"      : "Nil (mandatory lock-in of 3 years)",
      "min_lumpsum"    : "₹500",
      "riskometer"     : "Very High",
      "benchmark"      : "Nifty 500 TRI",
      "fund_manager"   : "Rahul Baijal, Dhruv Muchhal",
      "fund_house"     : "HDFC Mutual Fund"
    },

    "free_text": [
      "HDFC ELSS Tax Saver Fund is an equity-linked savings scheme...",
      "The fund invests primarily in diversified equity instruments..."
    ]
  },
  { ... },   ← HDFC Large Cap Fund
  { ... },   ← HDFC Equity Fund
  { ... },   ← HDFC Mid-Cap Fund
  { ... }    ← HDFC Focused Fund
]
```

**Key flags:**
- `_changed: true` — this scheme's fields differ from the previous day → proceed to embed
- `_changed: false` — no change → skip embedding (saves API cost)
- `_is_new: true` — first ever scrape for this scheme

---

## 4. Layer 2 — Snapshot Store

**Directory:** `scraper/snapshots/`

One JSON file per scheme, storing the **previous day's field values**. Used by the change detector to decide whether re-embedding is needed.

```
scraper/snapshots/
├── hdfc-elss-tax-saver-fund-direct-plan-growth.json
├── hdfc-large-cap-fund-direct-growth.json
├── hdfc-equity-fund-direct-growth.json
├── hdfc-mid-cap-fund-direct-growth.json
└── hdfc-focused-fund-direct-growth.json
```

**Snapshot file format** (`hdfc-elss-tax-saver-fund-direct-plan-growth.json`):

```json
{
  "scheme_name" : "HDFC ELSS Tax Saver Fund Direct Plan Growth",
  "source_url"  : "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
  "fields": {
    "nav"           : "1040.10",
    "min_sip"       : "₹100",
    "aum"           : "₹14,230 Cr",
    "expense_ratio" : "0.77%",
    "rating"        : "4"
  },
  "free_text": [ "..." ]
}
```

**Diff logic:**
```
Today's nav   = "1042.35"
Previous nav  = "1040.10"
→ CHANGED — re-embed the nav chunk

Today's expense_ratio   = "0.77%"
Previous expense_ratio  = "0.77%"
→ NO CHANGE — skip (no embedding cost)
```

Only the fields that actually changed are re-processed, minimising OpenAI embedding API calls.

---

## 5. Layer 3 — Vector Store (ChromaDB)

**Directory:** `vector_store/`  
**Collection:** `mf_faq_chunks`

Each of the 5 core fields for each of the 5 schemes is stored as **one vector (chunk)** in ChromaDB. That is a minimum of **25 core vectors** (5 fields × 5 schemes) plus supporting-field vectors and free-text chunks.

### What one stored chunk looks like

Each record in ChromaDB has three parts:

```
┌──────────────────────────────────────────────────────────────────┐
│  ID (chunk_id)                                                   │
│  sha256("https://groww.in/...hdfc-elss...::nav::0")              │
│  = "a1b2c3d4e5f6..."  (64-char hex, stable across re-runs)       │
├──────────────────────────────────────────────────────────────────┤
│  DOCUMENT (text — what gets embedded and searched)               │
│  "The NAV of HDFC ELSS Tax Saver Fund Direct Plan Growth         │
│   is ₹1042.35 as of 2026-04-16."                                 │
├──────────────────────────────────────────────────────────────────┤
│  EMBEDDING (vector — 1536 floats, OpenAI text-embedding-3-small) │
│  [0.021, -0.034, 0.087, ..., -0.012]                             │
├──────────────────────────────────────────────────────────────────┤
│  METADATA (filter keys — used to narrow retrieval)               │
│  {                                                               │
│    "chunk_id"      : "a1b2c3d4...",                              │
│    "source_url"    : "https://groww.in/mutual-funds/hdfc-elss-…",│
│    "scheme_name"   : "HDFC ELSS Tax Saver Fund Direct Plan Grth",│
│    "amc_name"      : "HDFC Mutual Fund",                         │
│    "category"      : "ELSS",                                     │
│    "field_type"    : "nav",                                      │
│    "chunk_type"    : "atomic_fact",                              │
│    "chunk_index"   : 0,                                          │
│    "ingestion_date": "2026-04-16",                               │
│    "ingestion_time": "09:15"                                     │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
```

### All 5 core field chunks for HDFC ELSS (example)

| chunk_id (short) | field_type | Stored text |
|---|---|---|
| `a1b2...` | `nav` | The NAV of HDFC ELSS Tax Saver Fund Direct Plan Growth is ₹1042.35 as of 2026-04-16. |
| `c3d4...` | `min_sip` | The minimum SIP investment amount for HDFC ELSS Tax Saver Fund Direct Plan Growth is ₹100. |
| `e5f6...` | `aum` | The Assets Under Management (AUM) of HDFC ELSS Tax Saver Fund Direct Plan Growth is ₹14,230 Cr. |
| `g7h8...` | `expense_ratio` | The total expense ratio (TER) of HDFC ELSS Tax Saver Fund Direct Plan Growth is 0.77%. |
| `i9j0...` | `rating` | The Groww rating of HDFC ELSS Tax Saver Fund Direct Plan Growth is 4 out of 5. |

---

## 6. Full Storage Flow — Core Field Example

**Scenario:** User asks *"What is the NAV of HDFC ELSS fund?"*

```
09:15 AM — GitHub Actions fires
    │
    ├─ Groww page fetched (httpx)
    ├─ nav = "1042.35" extracted (parser)
    ├─ Diff: previous nav = "1040.10" → CHANGED
    │
    ├─ Atomic chunk built:
    │    "The NAV of HDFC ELSS Tax Saver Fund Direct Plan Growth
    │     is ₹1042.35 as of 2026-04-16."
    │
    ├─ Metadata attached:
    │    { field_type: "nav", ingestion_date: "2026-04-16", ... }
    │
    ├─ Embedded → 1536-dim vector (OpenAI text-embedding-3-small)
    │
    └─ Upserted into ChromaDB at chunk_id "a1b2..."
         (overwrites yesterday's NAV vector in-place)

─────────────────────────────────────────────────────────────────────

User asks: "What is the NAV of HDFC ELSS fund?"
    │
    ├─ Query embedded → 1536-dim vector
    ├─ ChromaDB cosine search → top match: chunk_id "a1b2..."
    │    score: 0.97, field_type: "nav", scheme: "HDFC ELSS..."
    │
    ├─ LLM receives:
    │    Context: "The NAV of HDFC ELSS Tax Saver Fund Direct Plan Growth
    │              is ₹1042.35 as of 2026-04-16."
    │    Source:  "https://groww.in/mutual-funds/hdfc-elss-..."
    │
    └─ Response:
         "The NAV of HDFC ELSS Tax Saver Fund Direct Plan Growth is
          ₹1042.35 as of 16 April 2026."

         Source: https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth
         Last updated from sources: 2026-04-16
```

---

## 7. Storage Summary Table

| Layer | Location | Format | Updated | Purpose |
|---|---|---|---|---|
| Raw output | `scraper/output/scraped_YYYY-MM-DD.json` | JSON array | Every day at 09:15 | Full record of what the scraper collected |
| Snapshot | `scraper/snapshots/<slug>.json` | JSON object | Every day at 09:15 | Previous-day values for diff comparison |
| Vector store | `vector_store/` (ChromaDB collection) | Vectors + metadata | Only when a field changes | Semantic search at query time |

---

## 8. ChromaDB Collection Schema

| Property | Value |
|---|---|
| Collection name | `mf_faq_chunks` |
| Distance metric | `cosine` |
| Embedding dimensions | `1536` (OpenAI) or `384` (local fallback) |
| Upsert key | `chunk_id` (SHA-256, deterministic) |
| Total core vectors | 25 minimum (5 fields × 5 schemes) |
| Total all vectors | ~82 (core + supporting + free-text) |
| Metadata filter keys | `scheme_name`, `field_type`, `category`, `ingestion_date` |

---

*Document generated: 2026-04-16*
*Scope: Core field storage design — NAV, Min SIP, Fund Size, Expense Ratio, Rating*
*Parent: docs/rag-architecture.md*
