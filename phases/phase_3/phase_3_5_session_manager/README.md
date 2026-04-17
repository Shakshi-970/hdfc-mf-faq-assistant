# Phase 3.5 — Session Manager

Multi-thread conversation state — each `session_id` is an isolated in-memory context.

## Session object

```
session_id (UUID)
    ├── conversation_history[]  ← ephemeral, in-memory only
    ├── active_scheme_context   ← last mentioned scheme name
    └── created_at / last_active
```

## Properties

| Property | Value |
|---|---|
| PII storage | None — sessions contain only conversation history and scheme context |
| Isolation | Fully isolated — no cross-session leakage |
| TTL | Configurable inactivity timeout (default 30 min) |
| Backend (dev) | In-memory dict |
| Backend (prod) | Redis — enables horizontal scaling across FastAPI instances |

## API endpoints (Phase 3.4)

| Method | Path | Description |
|---|---|---|
| `POST` | `/sessions/new` | Create a new session, returns `session_id` |
| `POST` | `/chat/{session_id}` | Send a query within a session |
| `DELETE` | `/sessions/{session_id}` | Expire a session |
| `GET` | `/health` | Liveness check |

## Module layout

```
phase_3_5_session_manager/
├── session.py              ← Session dataclass + DEFAULT_TTL_SECONDS
├── manager.py              ← Backend factory + public API functions
├── backends/
│   ├── memory.py           ← InMemorySessionBackend (dev)
│   └── redis_backend.py    ← RedisSessionBackend (prod)
└── __init__.py             ← Re-exports public interface
```

## Usage

```python
from phases.phase_3_5_session_manager import (
    create_session, get_session, append_message,
    set_scheme_context, delete_session, active_session_count,
)

sid = create_session()              # returns UUID string
append_message(sid, "user", "...")
append_message(sid, "assistant", "...")
session = get_session(sid)          # Session | None (None if expired)
active_session_count()              # int
delete_session(sid)                 # True if existed
```

Phase 3.4 (`pipeline.py`, `app.py`) accesses this module through the
thin proxy at `phase_3_4_query_pipeline/session_store.py`.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | _(unset)_ | Set to activate Redis backend, e.g. `redis://localhost:6379/0` |
| `SESSION_TTL_SECONDS` | `1800` | Inactivity TTL in seconds (30 min) |

## Start the API

```bash
python -m phases.phase_3_4_query_pipeline   # starts uvicorn on :8000
```

## Status

Implemented. See [`docs/rag-architecture.md`](../../docs/rag-architecture.md) for full architecture.
