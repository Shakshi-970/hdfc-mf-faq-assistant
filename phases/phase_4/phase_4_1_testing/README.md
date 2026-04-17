# Phase 4.1 — Testing

Unit tests and integration tests for all Phase 3 components.

## Scope

| Module | Test Type | What to verify |
|---|---|---|
| `phase_3_2_chunking_embedding` | Unit | Normaliser, atomic chunker, text chunker, metadata tagger, embedder |
| `phase_3_3_scraping_service` | Unit + Integration | Parser field extraction, change detector diff logic, fetcher retries |
| `phase_3_4_query_pipeline` | Unit | Classifier labels, rewriter expansions, prompt builder output format |
| `phase_3_4_query_pipeline` | Integration | Full pipeline with mock Chroma + mock Claude responses |
| `phase_3_5_session_manager` | Unit | TTL eviction, session isolation, Redis serialisation roundtrip |
| `phase_3_6_ui` | Integration | UI renders without error; API calls handled correctly |

## Planned structure

```
phase_4_1_testing/
├── conftest.py                        ← shared fixtures (mock Chroma, mock Claude)
├── test_normaliser.py
├── test_chunkers.py
├── test_metadata_tagger.py
├── test_classifier.py
├── test_rewriter.py
├── test_prompt_builder.py
├── test_session_manager.py
├── test_pipeline_integration.py
└── test_scraper_parser.py
```

## Status

Not yet implemented.
