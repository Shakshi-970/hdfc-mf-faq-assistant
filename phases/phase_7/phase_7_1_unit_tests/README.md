# Phase 7.1 — Unit Tests

pytest test suite for the classifier, rewriter, and query pipeline.  
**No API keys required** — the retriever and LLM are mocked.

## Test files

| File | Component tested | Tests |
|---|---|---|
| `test_classifier.py` | `classifier.classify_query` | 25 — PII, advisory, OOS, factual, fallback |
| `test_rewriter.py` | `rewriter.rewrite_query` | 18 — abbreviation expansion, scheme normalisation, combined |
| `test_pipeline.py` | `pipeline.run_query` (Phase 6) | 12 — refusals, session handling, factual path, error handling |

---

## Run all unit tests

```bash
# From repo root
pytest -v
```

## Run a specific file

```bash
pytest phases/phase_7/phase_7_1_unit_tests/test_classifier.py -v
pytest phases/phase_7/phase_7_1_unit_tests/test_rewriter.py -v
pytest phases/phase_7/phase_7_1_unit_tests/test_pipeline.py -v
```

## Run a single test

```bash
pytest phases/phase_7/phase_7_1_unit_tests/test_classifier.py::TestFactualClassification::test_expense_ratio -v
```

---

## What is mocked in test_pipeline.py

| Real component | Mock | Why |
|---|---|---|
| `retrieve()` | `unittest.mock.patch` returns `[_MOCK_CHUNK]` | Avoids Chroma Cloud network call |
| `_llm` (module-level) | `MagicMock` with `generate()` | Avoids Groq/Anthropic API call |
| Session manager | Real in-memory backend | Fast, no external deps |

Advisory / PII / out-of-scope tests do **not** need mocks — the pipeline returns early before calling either the retriever or LLM.

---

## Expected output

```
phases/phase_7/phase_7_1_unit_tests/test_classifier.py::TestPIIDetection::test_pan_card_format PASSED
phases/phase_7/phase_7_1_unit_tests/test_classifier.py::TestPIIDetection::test_aadhaar_twelve_digits PASSED
...
phases/phase_7/phase_7_1_unit_tests/test_pipeline.py::TestFactualPipeline::test_answer_returned_for_factual_query PASSED
...
55 passed in ~2s
```
