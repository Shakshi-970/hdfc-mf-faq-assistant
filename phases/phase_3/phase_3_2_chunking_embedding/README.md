# Phase 3.2 — Chunking, Embedding, and Vector Store Upsert

Processes scraper output into searchable vectors in ChromaDB / FAISS.

## Pipeline (per changed scheme)

```
scraped_<date>.json
        │
        ▼
normaliser.py       — 7-step text clean (HTML entities, whitespace, ₹, %)
        │
        ▼
field_splitter.py   — route: structured fields → atomic chunker
                            free-text paragraphs → text chunker
        │
        ├──▶ atomic_chunker.py  — one sentence per field  (atomic_fact chunks)
        └──▶ text_chunker.py    — 512-tok / 64-overlap    (free_text chunks)
        │
        ▼
metadata_tagger.py  — chunk_id (SHA-256) + source_url + scheme_name + dates
        │
        ▼
embedder.py         — OpenAI text-embedding-3-small (1536-dim)
                      fallback: all-MiniLM-L6-v2 (384-dim)
        │
        ▼
upsert.py           — ChromaDB (dev) or FAISS (prod)
                      upsert by chunk_id → overwrites stale vectors
```

## Entry points

```bash
# Step 1: chunk and embed
python -m phases.phase_3_2_chunking_embedding.chunk_and_embed

# Step 2: upsert into vector store
python -m phases.phase_3_2_chunking_embedding.upsert
```

## Output files

| File | Purpose |
|---|---|
| `phases/phase_3_2_chunking_embedding/embedded_chunks.json` | Serialised vectors passed from chunk_and_embed → upsert |
| `phases/phase_3_2_chunking_embedding/last_run_report.json` | Run summary read by GitHub Actions job summary step |

## Vector store

| Property | Value |
|---|---|
| Collection | `mf_faq_chunks` |
| Distance metric | cosine |
| Dimensions | 1536 (OpenAI) or 384 (local) |
| Upsert key | `chunk_id` — SHA-256 of `(source_url, field_type, chunk_index)` |
| Core vectors | 25 minimum (5 fields × 5 schemes) |

See also: [`docs/chunking-and-embedding.md`](../../docs/chunking-and-embedding.md) and [`docs/data-storage-design.md`](../../docs/data-storage-design.md)
