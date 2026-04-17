"""
phases/phase_5/phase_5_2_monitoring/healthcheck.py
---------------------------------------------------
Liveness check for the Mutual Fund FAQ Assistant backend.

Hits the /health endpoint and exits with:
  0 — backend is healthy   (status == "ok")
  1 — backend is unhealthy or unreachable

Usage:
    # Default (localhost:8000)
    python phases/phase_5/phase_5_2_monitoring/healthcheck.py

    # Custom URL
    python phases/phase_5/phase_5_2_monitoring/healthcheck.py --url http://api:8000/health

Used as:
  • Docker HEALTHCHECK in Dockerfile.backend
  • CI/CD pipeline smoke test after deployment
  • Manual on-call check

Intentionally uses only the standard library (no third-party deps) so it
works inside a slim container without installing requests or httpx.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

_DEFAULT_URL = "http://localhost:8000/health"
_TIMEOUT_S = 8


def check(url: str) -> int:
    """
    Perform a single health check against *url*.

    Returns 0 on success, 1 on failure.
    Prints a one-line status to stdout (success) or stderr (failure).
    """
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT_S) as resp:
            payload = json.loads(resp.read())
    except urllib.error.URLError as exc:
        print(f"[unhealthy] {url} — connection error: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[unhealthy] {url} — invalid JSON in response: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {url} — unexpected error: {exc}", file=sys.stderr)
        return 1

    status = payload.get("status", "")
    if status == "ok":
        sessions = payload.get("active_sessions", 0)
        version = payload.get("version", "?")
        print(f"[healthy] {url} — version={version}, active_sessions={sessions}")
        return 0

    print(
        f"[unhealthy] {url} — unexpected status field: {status!r}  payload={payload}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Liveness check for the Mutual Fund FAQ backend."
    )
    parser.add_argument(
        "--url",
        default=_DEFAULT_URL,
        help=f"Health endpoint URL (default: {_DEFAULT_URL})",
    )
    args = parser.parse_args()
    return check(args.url)


if __name__ == "__main__":
    sys.exit(main())
