# Chunking and Embedding Architecture
## Mutual Fund FAQ Assistant — Ingestion Detail

> **Scope:** This document covers exactly what happens between raw scraped HTML text and the final vectors stored in the vector database. It is invoked by the GitHub Actions workflow step `python -m phases.phase_3_2_chunking_embedding.chunk_and_embed` after the scraping step completes.

---

## 1. Overview

```
Scraper output (JSON)
      │
      ▼
┌─────────────────────┐
│   Text Normaliser   │  Clean and standardise raw extracted text
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Field Splitter    │  Split structured fields vs. free-text sections
└──────────┬──────────┘
           │
      ┌────┴────┐
      ▼         ▼
┌──────────┐ ┌────────────────────┐
│ Atomic   │ │ Recursive Text     │
│ Fact     │ │ Chunker            │
│ Chunker  │ │ (free-text only)   │
└────┬─────┘ └─────────┬──────────┘
     │                 │
     └────────┬────────┘
              │  chunks[]
              ▼
┌─────────────────────┐
│  Metadata Tagger    │  Attach source_url, scheme, field_type,
│                     │  ingestion_date, ingestion_time, chunk_id
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Embedding Model    │  Convert each chunk → 384-dim vector
│  (BAAI/bge-small-   │  Local CPU, no API key required
│   en-v1.5)          │
└──────────┬──────────┘
           │  (chunk_text, vector, metadata)[]
           ▼
┌─────────────────────┐
│  Vector Store       │  Upsert by stable chunk_id
│  Upsert             │  (Remote ChromaDB — Chroma Cloud)
└─────────────────────┘
```

---

## 2. Input: Scraper Output Format

The chunking pipeline consumes the JSON file written by the scraping service (`scraper/output/scraped_<date>.json`). That file is written by `phases/phase_3_3_scraping_service/run.py`.

```json
[
  {
    "scheme_name"   : "HDFC ELSS Tax Saver Fund Direct Plan Growth",
    "source_url"    : "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "amc"           : "HDFC Mutual Fund",
    "category"      : "ELSS",
    "scraped_at"    : "2026-04-16T09:16:42+05:30",
    "fields": {
      "nav"           : "1042.35",
      "expense_ratio" : "0.77%",
      "exit_load"     : "Nil (mandatory lock-in of 3 years)",
      "min_sip"       : "₹500",
      "min_lumpsum"   : "₹500",
      "riskometer"    : "Very High",
      "benchmark"     : "Nifty 500 TRI",
      "fund_manager"  : "Rahul Baijal, Dhruv Muchhal",
      "aum"           : "₹14,230 Cr",
      "lock_in"       : "3 years",
      "tax_benefit"   : "Deduction up to ₹1.5 lakh under Section 80C"
    },
    "free_text": [
      "HDFC ELSS Tax Saver Fund is an equity-linked savings scheme...",
      "The fund invests primarily in equity and equity-related instruments..."
    ]
  },
  ...
]
```

---

## 3. Step 1 — Text Normaliser

Before any splitting, all text passes through a normalisation step to ensure consistent, clean input.

```
Raw text input
      │
      ▼
┌──────────────────────────────────────────────────────────────┐
│  Text Normaliser                                             │
│                                                              │
│  Operations (in order):                                      │
│  1. Decode HTML entities  (&amp; → &, &#8377; → ₹)          │
│  2. Collapse whitespace   (\t, \n\n+ → single space/newline) │
│  3. Strip zero-width chars (​\u200b, \u00a0 → space)         │
│  4. Normalise Unicode     (NFC normalisation)                │
│  5. Remove boilerplate    (cookie banners, "Accept all"      │
│                            text detected by keyword list)    │
│  6. Standardise currency  ("Rs." / "INR" → "₹")             │
│  7. Standardise percent   ("percent" → "%")                  │
└──────────────────────────────────────────────────────────────┘
      │
      ▼
Clean text ready for splitting
```

---

## 4. Step 2 — Field Splitter

The scraper already produces a structured `fields` dict and a `free_text` list. The field splitter routes each piece to the correct chunker.

```
Normalised scraper output
        │
        ├─── fields{}  ──────────────────► Atomic Fact Chunker
        │    (key-value pairs:                (Section 5)
        │     expense_ratio, exit_load,
        │     min_sip, riskometer, etc.)
        │
        └─── free_text[]  ──────────────► Recursive Text Chunker
             (paragraph strings:              (Section 6)
              fund description,
              investment objective, etc.)
```

**Why separate routes?**
- Structured fields are already single facts — splitting them further would destroy precision.
- Free-text paragraphs can be long and need overlap-aware splitting to preserve context across chunk boundaries.

---

## 5. Step 3a — Atomic Fact Chunker (for structured fields)

Each key-value field from the scraper becomes exactly **one chunk**, expressed as a complete sentence. This ensures that a retrieval query like *"What is the expense ratio of HDFC ELSS?"* retrieves a single, precise chunk rather than a fragment.

**Sentence Template per Field**

| Field Key | Sentence Template |
|---|---|
| `nav` | `"The NAV of {scheme_name} is {value} as of {date}."` |
| `expense_ratio` | `"The total expense ratio (TER) of {scheme_name} is {value}."` |
| `exit_load` | `"The exit load of {scheme_name} is: {value}."` |
| `min_sip` | `"The minimum SIP investment amount for {scheme_name} is {value}."` |
| `min_lumpsum` | `"The minimum lump sum investment for {scheme_name} is {value}."` |
| `riskometer` | `"The riskometer classification of {scheme_name} is {value}."` |
| `benchmark` | `"The benchmark index for {scheme_name} is {value}."` |
| `fund_manager` | `"The fund manager(s) of {scheme_name} are {value}."` |
| `aum` | `"The Assets Under Management (AUM) of {scheme_name} is {value}."` |
| `lock_in` | `"The lock-in period for {scheme_name} is {value}."` |
| `tax_benefit` | `"The tax benefit for {scheme_name}: {value}."` |
| `category` | `"The fund category of {scheme_name} is {value}."` |

**Output per field — one chunk:**
```
{
  "text"    : "The total expense ratio (TER) of HDFC ELSS Tax Saver Fund
               Direct Plan Growth is 0.77%.",
  "type"    : "atomic_fact",
  "field"   : "expense_ratio"
}
```

---

## 6. Step 3b — Recursive Text Chunker (for free-text sections)

Free-text paragraphs (fund descriptions, investment objectives) are split using **LangChain `RecursiveCharacterTextSplitter`** with sentence-boundary awareness.

```
┌──────────────────────────────────────────────────────────────────┐
│  RecursiveCharacterTextSplitter Configuration                    │
│                                                                  │
│  chunk_size        : 512  tokens  (≈ 400 words)                  │
│  chunk_overlap     : 64   tokens  (≈ 50 words)                   │
│  length_function   : tiktoken (cl100k_base encoder)              │
│  separators        : ["\n\n", "\n", ". ", " ", ""]               │
│                      (tries paragraph → line → sentence → word)  │
└──────────────────────────────────────────────────────────────────┘
```

**Splitting Logic (step-by-step)**

```
Input: free_text paragraph string
        │
        ▼
Try split on "\n\n" (paragraph boundary)
   → If all resulting pieces ≤ 512 tokens  →  use them
   → Else recurse on "\n" (line boundary)
        │
        ▼
Try split on "\n" (line boundary)
   → If all resulting pieces ≤ 512 tokens  →  use them
   → Else recurse on ". " (sentence boundary)
        │
        ▼
Try split on ". " (sentence boundary)  ← preferred natural split
   → If all resulting pieces ≤ 512 tokens  →  use them
   → Else recurse on " " (word boundary)
        │
        ▼
Split on " " (word boundary)  ← last resort
```

**Overlap handling**

Each chunk starts 64 tokens back from where the previous chunk ended. This ensures queries that span a sentence boundary still find a relevant chunk.

```
Chunk 1: [token 0   ... token 511]
Chunk 2: [token 448 ... token 959]   ← 64-token overlap
Chunk 3: [token 896 ... token 1407]
```

**Output per free-text chunk:**
```
{
  "text"    : "HDFC ELSS Tax Saver Fund is an equity-linked savings scheme
               that primarily invests in a diversified portfolio of equity
               and equity-related instruments...",
  "type"    : "free_text",
  "field"   : "general"
}
```

---

## 7. Step 4 — Metadata Tagger

Every chunk (atomic fact or free-text) is tagged with a standard metadata envelope before embedding.

```
┌──────────────────────────────────────────────────────────────────┐
│  Metadata Envelope (attached to every chunk)                     │
│                                                                  │
│  chunk_id        : sha256(source_url + field + chunk_index)      │
│                    → stable ID for upsert deduplication          │
│  source_url      : "https://groww.in/mutual-funds/..."           │
│  scheme_name     : "HDFC ELSS Tax Saver Fund Direct Plan Growth" │
│  amc_name        : "HDFC Mutual Fund"                            │
│  category        : "ELSS"                                        │
│  field_type      : "expense_ratio" | "exit_load" | "min_sip" |   │
│                    "riskometer" | "benchmark" | "lock_in" |      │
│                    "nav" | "aum" | "fund_manager" | "general"    │
│  chunk_type      : "atomic_fact" | "free_text"                   │
│  chunk_index     : 0, 1, 2, ...  (position within scheme)        │
│  ingestion_date  : "2026-04-16"  (YYYY-MM-DD)                    │
│  ingestion_time  : "09:15"       (HH:MM IST)                     │
└──────────────────────────────────────────────────────────────────┘
```

**chunk_id** is a SHA-256 hash of `source_url + field_type + chunk_index`. This makes each chunk's identity deterministic — re-running the pipeline on the same data produces the same IDs, enabling clean upserts without duplicates.

---

## 8. Step 5 — Embedding Model

All chunks are converted to dense vectors using the embedding model.

```
┌──────────────────────────────────────────────────────────────────────┐
│  MODEL:  BAAI/bge-small-en-v1.5  (local CPU, no API key required)   │
│                                                                      │
│  Dimensions    : 384                                                 │
│  Runs on       : CPU (GitHub Actions ubuntu-latest runner)           │
│  Library       : sentence-transformers (pip)                         │
│  Batch size    : 32 chunks per encode() call                         │
│  Query prefix  : "Represent this sentence: " (query time only —      │
│                   not applied during ingestion/document encoding)    │
└──────────────────────────────────────────────────────────────────────┘
```

**Batching Flow**

```
All chunks for all 5 schemes
         │
         ▼
Split into batches of 32
         │
    ┌────┴────┐
    ▼         ▼
Batch 1    Batch 2   ...   Batch N
    │
    ▼
model.encode(batch, convert_to_numpy=True)
    │
    ▼
384-dim float vectors
    │
    ▼
Pair each embedding with its chunk metadata
    │
    ▼
Accumulate (text, vector, metadata) tuples
```

**Typical volume estimate**

| Scheme | Atomic fact chunks | Free-text chunks | Total per scheme |
|---|---|---|---|
| HDFC Large Cap Fund | ~12 | ~4 | ~16 |
| HDFC Equity Fund | ~12 | ~4 | ~16 |
| HDFC ELSS Tax Saver | ~13 | ~5 | ~18 |
| HDFC Mid-Cap Fund | ~12 | ~4 | ~16 |
| HDFC Focused Fund | ~12 | ~4 | ~16 |
| **Total** | **~61** | **~21** | **~82** |

~82 chunks total → processed in 3 batches of 32 → **no external API calls**.

---

## 9. Step 6 — Vector Store Upsert

After embedding, all `(chunk_id, vector, metadata, text)` tuples are written to the remote vector store.

```
┌──────────────────────────────────────────────────────────────────┐
│  Vector Store Upsert                                             │
│                                                                  │
│  Store  : Remote ChromaDB — Chroma Cloud (trychroma.com)         │
│                                                                  │
│  Connection:                                                     │
│    • Host       : api.trychroma.com (HTTPS)                      │
│    • Auth       : CHROMA_API_KEY (GitHub Actions Secret)         │
│    • Tenant     : CHROMA_TENANT  (GitHub Actions Variable)       │
│    • Database   : CHROMA_DATABASE (GitHub Actions Variable)      │
│    • Collection : mf_faq_chunks                                  │
│                                                                  │
│  Upsert strategy:                                                │
│    • Key       : chunk_id (SHA-256 hash)                         │
│    • On match  : overwrite vector + metadata (update in place)   │
│    • On new    : insert new chunk                                │
│    • On absent : stale chunk from previous day remains           │
│                  (intentional — retain data if URL fails today)  │
│                                                                  │
│  Post-upsert:                                                    │
│    • Write phases/phase_3_2_chunking_embedding/last_run_report.json: │
│      {                                                           │
│        "date"          : "2026-04-16",                           │
│        "time_ist"      : "09:15",                                │
│        "total_chunks"  : 82,                                     │
│        "upserted"      : 12,   ← chunks that changed            │
│        "skipped"       : 70,   ← unchanged (diff check)         │
│        "failed_urls"   : [],                                     │
│        "duration_sec"  : 18                                      │
│      }                                                           │
│    • GitHub Actions step summary displays this report            │
└──────────────────────────────────────────────────────────────────┘
```

---

## 10. Complete Pipeline Trace (Example)

**Input:** Scraper output for HDFC ELSS Tax Saver Fund

**Atomic fact chunks generated (13):**

| chunk_id (abbrev.) | field_type | text |
|---|---|---|
| `a1b2...` | `expense_ratio` | The total expense ratio (TER) of HDFC ELSS Tax Saver Fund Direct Plan Growth is 0.77%. |
| `c3d4...` | `exit_load` | The exit load of HDFC ELSS Tax Saver Fund Direct Plan Growth is: Nil (mandatory lock-in of 3 years). |
| `e5f6...` | `min_sip` | The minimum SIP investment amount for HDFC ELSS Tax Saver Fund Direct Plan Growth is ₹500. |
| `g7h8...` | `min_lumpsum` | The minimum lump sum investment for HDFC ELSS Tax Saver Fund Direct Plan Growth is ₹500. |
| `i9j0...` | `riskometer` | The riskometer classification of HDFC ELSS Tax Saver Fund Direct Plan Growth is Very High. |
| `k1l2...` | `benchmark` | The benchmark index for HDFC ELSS Tax Saver Fund Direct Plan Growth is Nifty 500 TRI. |
| `m3n4...` | `fund_manager` | The fund manager(s) of HDFC ELSS Tax Saver Fund Direct Plan Growth are Rahul Baijal, Dhruv Muchhal. |
| `o5p6...` | `aum` | The Assets Under Management (AUM) of HDFC ELSS Tax Saver Fund Direct Plan Growth is ₹14,230 Cr. |
| `q7r8...` | `lock_in` | The lock-in period for HDFC ELSS Tax Saver Fund Direct Plan Growth is 3 years. |
| `s9t0...` | `tax_benefit` | The tax benefit for HDFC ELSS Tax Saver Fund Direct Plan Growth: Deduction up to ₹1.5 lakh under Section 80C. |
| `u1v2...` | `nav` | The NAV of HDFC ELSS Tax Saver Fund Direct Plan Growth is 1042.35 as of 2026-04-16. |
| `w3x4...` | `category` | The fund category of HDFC ELSS Tax Saver Fund Direct Plan Growth is ELSS. |
| `y5z6...` | `general` | HDFC ELSS Tax Saver Fund is an equity-linked savings scheme... *(free-text chunk 1)* |

Each chunk is embedded → 384-dim vector → upserted into Chroma Cloud under its `chunk_id`.

---

## 11. File Structure

```
phases/phase_3_2_chunking_embedding/
├── __init__.py              ← package marker
├── __main__.py              ← python -m phases.phase_3_2_chunking_embedding
├── chunk_and_embed.py       ← main entry point: python -m phases.phase_3_2_chunking_embedding.chunk_and_embed
├── normaliser.py            ← Text Normaliser (Step 1)
├── field_splitter.py        ← Field Splitter (Step 2)
├── atomic_chunker.py        ← Atomic Fact Chunker (Step 3a)
├── text_chunker.py          ← Recursive Text Chunker (Step 3b)
├── metadata_tagger.py       ← Metadata Tagger (Step 4)
├── embedder.py              ← Embedding Model (Step 5, BAAI/bge-small-en-v1.5)
├── upsert.py                ← Vector Store Upsert (Step 6): python -m phases.phase_3_2_chunking_embedding.upsert
├── embedded_chunks.json     ← written by chunk_and_embed, read by upsert (runtime)
└── last_run_report.json     ← written after each run, read by GH Actions summary (runtime)

scraper/output/
└── scraped_<YYYY-MM-DD>.json  ← daily scraper output consumed by chunk_and_embed.py

scraper/snapshots/
└── <scheme_slug>.json         ← previous-day field snapshots for change detection
```

---

## 12. Configuration Reference

| Parameter | Value | Notes |
|---|---|---|
| `CHUNK_SIZE` | 512 tokens | Applies to free-text chunker only |
| `CHUNK_OVERLAP` | 64 tokens | Applies to free-text chunker only |
| `TOKENISER` | `cl100k_base` (tiktoken) | Used for token-accurate free-text chunking |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Local CPU; 384-dim |
| `EMBED_BATCH_SIZE` | 32 | Chunks per encode() call |
| `CHROMA_API_KEY` | Secret (GitHub Actions) | Chroma Cloud authentication |
| `CHROMA_TENANT` | Variable (GitHub Actions) | Chroma Cloud tenant identifier |
| `CHROMA_DATABASE` | Variable (GitHub Actions) | Chroma Cloud database name |
| `CHROMA_COLLECTION` | `mf_faq_chunks` | Collection name in Chroma Cloud |
| `UPSERT_KEY` | `chunk_id` (SHA-256) | Prevents duplicates on re-runs |

---

*Document generated: 2026-04-16*
*Scope: Chunking and Embedding Pipeline — Ingestion Detail*
*Parent: docs/rag-architecture.md*
