"""
phases/phase_3_2_chunking_embedding
--------------------------------------
Phase 3.2 — Chunking, Embedding, and Vector Store Upsert pipeline.
Invoked by GitHub Actions after the scraping service step completes.

Components:
  normaliser.py      — 7-step text normalisation (unicode, whitespace, currency symbols)
  field_splitter.py  — separates structured fields from free-text paragraphs
  atomic_chunker.py  — one sentence per structured field using field-specific templates
  text_chunker.py    — recursive character splitter for free-text (512 tok / 64 overlap)
  metadata_tagger.py — attaches 10-field metadata envelope + deterministic SHA-256 chunk_id
  embedder.py        — OpenAI text-embedding-3-small (primary) + all-MiniLM-L6-v2 (fallback)
  chunk_and_embed.py — pipeline entry point: normalise → split → chunk → tag → embed
  upsert.py          — vector store upsert (ChromaDB dev / FAISS prod)
"""
