"""
phases
------
All pipeline phases for the Mutual Fund FAQ Assistant.

Phase map (mirrors docs/rag-architecture.md):
  phase_1/  — Problem definition & system design
    phase_1_1_problem_statement/   — Project brief (objectives, scope, constraints)
    phase_1_2_design_docs/         — rag-architecture.md, chunking-and-embedding.md,
                                     data-storage-design.md

  phase_2/  — Data collection & corpus
    phase_2_1_scraper_data/        — Daily scraped JSON output + per-scheme snapshots
    phase_2_2_ingestion/           — Ingestion artifacts (written by chunking pipeline)

  phase_3/  — Core RAG pipeline
    phase_3_1_scheduler_github_actions/ — Daily cron trigger at 09:15 AM IST
    phase_3_2_chunking_embedding/       — Chunking, embedding, and vector store upsert
    phase_3_3_scraping_service/         — HTTP fetcher, HTML parser, change detector
    phase_3_4_query_pipeline/           — Query classification, retrieval, and generation
    phase_3_5_session_manager/          — Multi-thread ephemeral session state
    phase_3_6_ui/                       — Streamlit chat UI

  phase_4/  — Quality assurance
    phase_4_1_testing/                  — Unit and integration test plans
    phase_4_2_evaluation/               — RAG quality metrics (faithfulness, relevance)
    phase_4_3_deployment/               — Deployment plans (see phase_5_1_docker)
    phase_4_4_monitoring/               — Monitoring plans (see phase_5_2_monitoring)

  phase_5/  — Deployment and monitoring (implemented)
    phase_5_1_docker/                   — Dockerfile.backend, Dockerfile.ui, docker-compose.yml
    phase_5_2_monitoring/               — Structured JSON logging + health check script

  phase_6/  — Multi-provider LLM integration (implemented)
    phase_6_1_groq_pipeline/            — Groq inference backend (llama-3.3-70b-versatile);
                                          provider-switchable via LLM_PROVIDER env var;
                                          reuses all Phase 3 retrieval components unchanged

  phase_7/  — Testing and evaluation (implemented)
    phase_7_1_unit_tests/               — pytest unit tests (classifier, rewriter, pipeline,
                                          formatter, guardrail); no API keys required; all
                                          external calls mocked
    phase_7_2_evaluation/               — RAG quality evaluation against 20-question golden set;
                                          metrics: classification accuracy, refusal accuracy,
                                          retrieval hit rate, latency P50/P95

  phase_8/  — Response formatter + post-generation guardrail (implemented)
    phase_8_1_response_formatter/       — formatter.py: 3-sentence cap, Source injection,
                                          Last-updated footer;
                                          guardrail.py: advisory-language scanner;
                                          integrated into Phase 6 pipeline at Step 6.5

  phase_9/  — Project documentation (implemented)
    phase_9_1_readme/                   — README.md at repo root: setup instructions,
                                          selected AMC/schemes, architecture overview,
                                          evaluation targets, known limitations, disclaimer

  phase_10/ — API Gateway, rate limiting, and request cache (implemented)
    phase_10_1_api_gateway/             — nginx.conf: rate-limit zones, upstream block,
                                          proxy pass; Dockerfile.nginx (nginx:1.27-alpine)
    phase_10_2_rate_limiting/           — SlidingWindowCounter + RateLimitMiddleware:
                                          10 req/min per session, 60 req/min per IP;
                                          returns HTTP 429 with Retry-After header
    phase_10_3_request_cache/           — LRU response cache (in-memory or Redis);
                                          keyed on SHA-256(query.lower()); TTL 3600 s;
                                          integrated into Phase 6 app.py
    CI: .github/workflows/ci.yml        — pytest on every push/PR (Python 3.11 + 3.12)

  phase_12/ — Known Limitations Mitigations (implemented)
    phase_12_1_clarification/               — scheme_resolver.py:
                                              detect_ambiguous_schemes() — returns all 5
                                              scheme names when "hdfc" is present but no
                                              scheme-specific term (triggers clarification);
                                              is_realtime_nav_query() — detects "today's
                                              NAV" / "current NAV" / "live NAV" variants;
                                              clarification_message() — numbered list of
                                              candidate schemes + example query;
                                              nav_redirect_message() — Groww URL with
                                              data-freshness caveat;
                                              Phase 6 pipeline.py: Step 2.5 inserted
                                              between refusal guard and query rewriting

  phase_11/ — Security and Privacy Controls (implemented)
    phase_11_1_security/                — domain_whitelist.py: validate_url() (HTTPS +
                                          domain + corpus membership checks), is_corpus_url(),
                                          CORPUS_URLS (5-URL frozenset), ALLOWED_DOMAIN;
                                          audit_log.py: log_query_event() (session_id +
                                          class only — query text NEVER logged),
                                          log_session_event(), log_rewrite_event() (boolean
                                          flag only — rewritten text NEVER logged);
                                          Phase 6 pipeline.py updated: replaced two
                                          privacy-violating log statements with Phase 11
                                          audit functions
"""
