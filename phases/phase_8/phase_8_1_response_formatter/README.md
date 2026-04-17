# Phase 8.1 — Response Formatter + Post-Generation Guardrail

Post-processing layer applied to every factual LLM answer before it is
returned to the caller.  No API keys or network calls required.

## Files

| File | Purpose |
|---|---|
| `formatter.py` | 3-sentence cap, Source injection, Last-updated footer |
| `guardrail.py` | Advisory-language scanner; replaces body with safe fallback if triggered |

---

## formatter.py — `format_response`

```python
from phases.phase_8.phase_8_1_response_formatter.formatter import format_response

answer = format_response(raw_llm_text, source_url, ingestion_date)
```

Enforces the canonical response structure from the architecture spec:

```
{answer body — max 3 sentences}

Source: {source_url}

Last updated from sources: {YYYY-MM-DD}
```

Rules applied (in order):
1. Strip any existing `Source:` / `Last updated from sources:` lines from the LLM output.
2. Truncate the body to 3 sentences (split on `. ? !` + whitespace).
3. Inject one canonical `Source:` line from chunk metadata.
4. Inject `Last updated from sources:` footer (omitted if `ingestion_date` is empty).

---

## guardrail.py — `sanitize_output`

```python
from phases.phase_8.phase_8_1_response_formatter.guardrail import sanitize_output

clean_text, was_modified = sanitize_output(raw_llm_text)
```

Scans the body of the LLM response for advisory phrases:

| Pattern | Example trigger |
|---|---|
| `I recommend` | "I recommend this fund for growth." |
| `you should invest` | "You should invest in HDFC ELSS." |
| `I suggest` | "I suggest considering this fund." |
| `consider investing` | "Consider investing ₹500/month." |
| `good choice/option/investment` | "This is a good choice for tax saving." |
| `best fund/option/choice` | "This is the best fund for your goal." |
| `would recommend` | "I would recommend HDFC ELSS." |
| `ideally` | "Ideally, you should start a SIP." |
| `suitable for` | "This fund is suitable for long-term goals." |
| `for your (financial) goal` | "This fund suits your financial goal." |

If any pattern matches, the body is replaced with:

> "This assistant provides verified facts only and cannot offer investment advice or recommendations. Please refer to the source page for full details."

`Source:` and `Last updated from sources:` lines are **preserved** in the sanitized output.

---

## Integration in pipeline.py

Phase 6 pipeline calls both functions after LLM generation (Step 6.5):

```python
answer, was_sanitized = sanitize_output(answer)
if was_sanitized:
    logger.warning("Advisory language detected in LLM output — sanitized.")

answer = format_response(answer, source_url, ingestion_date)
```

---

## Unit tests

```bash
pytest phases/phase_7/phase_7_1_unit_tests/test_formatter.py -v
```

Expected: **30 tests passed**.
