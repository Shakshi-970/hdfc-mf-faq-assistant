"""
phases/phase_3_3_scraping_service
-----------------------------------
Phase 3.3 — Scraping Service for the Mutual Fund FAQ Assistant.
Triggered daily at 09:15 AM IST by GitHub Actions (.github/workflows/daily_ingestion.yml).

Components:
  config.py          — corpus URLs, scheme metadata, HTTP settings, field selectors
  fetcher.py         — async HTTP fetcher (httpx, HTTP/2) with retries and exponential backoff
  parser.py          — HTML parser + field extractor (BeautifulSoup4 + __NEXT_DATA__ JSON)
  change_detector.py — snapshot-based diff to skip unchanged data (saves embedding API cost)
  run.py             — entry point: python -m phases.phase_3_3_scraping_service.run
"""
