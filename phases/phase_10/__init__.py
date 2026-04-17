"""
phases/phase_10
---------------
Phase 10 — API Gateway, Rate Limiting, and Request Cache

Implements the API Gateway / Load Balancer layer from Section 13 of
docs/rag-architecture.md:

  ┌─────────────────────────────────────┐
  │   API Gateway / Load Balancer       │  ← Nginx reverse proxy
  └──────────────┬──────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
  FastAPI     FastAPI     FastAPI
  Instance 1  Instance 2  Instance N

  phase_10_1_api_gateway/   — Nginx config + Dockerfile.nginx
  phase_10_2_rate_limiting/ — Sliding-window rate limiter middleware (FastAPI)
  phase_10_3_request_cache/ — Query response cache (in-memory LRU or Redis)

CI workflow: .github/workflows/ci.yml — runs pytest on every push/PR
"""
