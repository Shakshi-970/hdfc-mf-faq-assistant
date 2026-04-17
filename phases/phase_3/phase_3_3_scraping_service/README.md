# Phase 3.3 — Scraping Service

Fetches, parses, diffs, and stores structured data from 5 Groww HDFC scheme pages daily.

## Components

| File | Role |
|---|---|
| `config.py` | Corpus URLs, scheme metadata, HTTP settings, multi-strategy field selectors |
| `fetcher.py` | Async HTTP fetcher (httpx, HTTP/2) — 15s timeout, 3 retries, 2s/4s/8s backoff |
| `parser.py` | HTML parser — `__NEXT_DATA__` JSON → CSS selectors → regex fallback |
| `change_detector.py` | Snapshot diff — skips re-embedding when page content is unchanged |
| `run.py` | Pipeline entry point — fetch → parse → diff → write JSON |

## Run

```bash
python -m phases.phase_3_3_scraping_service.run
```

## Output

`scraper/output/scraped_<YYYY-MM-DD>.json` — one file per daily run.

## 5 Core Fields extracted per scheme

| Field | Key |
|---|---|
| Net Asset Value | `nav` |
| Minimum SIP Amount | `min_sip` |
| Assets Under Management | `aum` |
| Total Expense Ratio | `expense_ratio` |
| Groww Star Rating | `rating` |

## Data directories (runtime — not code)

| Path | Contents |
|---|---|
| `scraper/output/` | Daily scraped JSON files |
| `scraper/snapshots/` | Previous-day snapshots used for change detection |

See also: [`docs/rag-architecture.md`](../../docs/rag-architecture.md) §3.3
