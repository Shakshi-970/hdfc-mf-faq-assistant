"""
phases/phase_5/phase_5_2_monitoring/log_config.py
--------------------------------------------------
Structured JSON logging configuration for the FastAPI backend.

Replaces the default plaintext log format with single-line JSON records,
making logs easy to ingest by log aggregators (CloudWatch, GCP Logging,
Datadog, etc.).

Usage — call once at application startup in app.py:

    from phases.phase_5.phase_5_2_monitoring.log_config import configure_logging
    configure_logging()

Each log record is emitted as a single JSON line:

    {"timestamp":"2026-04-16T09:15:00.123+00:00","level":"INFO",
     "logger":"phases.phase_3.phase_3_4_query_pipeline.app",
     "message":"New session created: abc123",
     "session_id":"abc123"}

Optional extra fields (attached via LogRecord attributes):
  session_id   — set by query/session handlers
  query_class  — factual | advisory | out-of-scope | pii-risk
  latency_ms   — integer milliseconds for the full query round-trip
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _JSONFormatter(logging.Formatter):
    """Formats each LogRecord as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Optional structured fields set by application code
        for field in ("session_id", "query_class", "latency_ms"):
            if hasattr(record, field):
                entry[field] = getattr(record, field)

        # Exception traceback (if any)
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """
    Replace the root logger's handlers with a single structured JSON handler
    writing to stdout.

    Call this once at application startup before any other logging occurs.

    Parameters
    ----------
    level : str
        Root log level (default "INFO"). Accepts "DEBUG", "INFO", "WARNING",
        "ERROR", "CRITICAL".
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Reduce noise from verbose third-party libraries
    for noisy_logger in ("uvicorn.access", "httpx", "chromadb", "hpack"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
