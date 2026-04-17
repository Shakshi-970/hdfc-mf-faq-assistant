# Phase 3.4 — Query Pipeline

Handles real-time user queries end-to-end: classify → retrieve → generate.

## Pipeline steps

| Step | Component | Description |
|---|---|---|
| 1 | Query Classifier | `factual` / `advisory` / `out-of-scope` / `pii-risk` |
| 2 | Intent Validator | Polite refusal for advisory / PII queries |
| 3 | Query Rewriter | Expand abbreviations, normalise scheme names |
| 4 | Query Embedder | `BAAI/bge-small-en-v1.5` (384-dim) with BGE query prefix |
| 5 | Vector Store Search | Top-K=5 cosine search on Chroma Cloud (`mf_faq_chunks`) |
| 6 | Metadata Filter + Re-Rank | Filter by scheme; re-rank; select top-3 |
| 7 | Prompt Constructor | System + retrieved chunks + user query |
| 8 | LLM | Claude / GPT-4o — grounded, citation-backed answer |
| 9 | Response Formatter | Max 3 sentences · 1 citation · date footer |

## Vector Store — Chroma Cloud

Queries hit the same `mf_faq_chunks` collection that the ingestion pipeline writes to.

| Parameter | Value |
|---|---|
| Host | `api.trychroma.com` |
| Protocol | HTTPS |
| Auth | `CHROMA_API_KEY` environment variable |
| Tenant | `CHROMA_TENANT` environment variable |
| Database | `CHROMA_DATABASE` environment variable |
| Collection | `mf_faq_chunks` |
| Similarity | Cosine |
| Top-K | 5 (retrieve), 3 (after re-rank) |

## BGE Query Encoding

`BAAI/bge-small-en-v1.5` is an asymmetric retrieval model:

- **Document side (ingestion):** encode chunk text as-is (already done in Phase 3.2)
- **Query side (this phase):** prefix query with `"Represent this sentence: "` before encoding

```python
query_text = "Represent this sentence: " + user_query
query_vector = model.encode(query_text)
```

This prefix is applied only at query time — ingestion-side chunks are stored without it.

## REST Endpoints (planned)

| Method | Path | Description |
|---|---|---|
| `POST` | `/sessions/new` | Create session, return UUID |
| `POST` | `/chat/{session_id}` | Submit query, return answer |
| `DELETE` | `/sessions/{session_id}` | Expire session |
| `GET` | `/health` | Liveness check |

## Status

Not yet implemented. See [`docs/rag-architecture.md`](../../docs/rag-architecture.md) §3.4 for full specification.
