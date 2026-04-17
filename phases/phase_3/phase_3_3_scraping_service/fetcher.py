"""
phases/phase_3_3_scraping_service/fetcher.py
---------------------------------------------
Async HTTP fetcher with:
  - TLS-enforced GET requests
  - Custom User-Agent and Accept headers
  - 15-second timeout
  - 3 retries with exponential backoff (2s, 4s, 8s)
  - Domain whitelist guard (groww.in only)
  - Polite single-request-per-URL (no parallel hits to the same domain)
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from .config import (
    HTTP_BACKOFF_SECONDS,
    HTTP_HEADERS,
    HTTP_MAX_RETRIES,
    HTTP_TIMEOUT_SECONDS,
    WHITELISTED_DOMAIN,
)

logger = logging.getLogger(__name__)


class DomainNotAllowedError(ValueError):
    """Raised when a URL's domain is not in the whitelist."""


class FetchError(RuntimeError):
    """Raised when all retries are exhausted without a successful response."""


def _assert_whitelisted(url: str) -> None:
    """Raise DomainNotAllowedError if the URL is not on the allowed domain."""
    host = urlparse(url).netloc.lstrip("www.")
    if not host.endswith(WHITELISTED_DOMAIN):
        raise DomainNotAllowedError(
            f"URL '{url}' is outside the whitelisted domain '{WHITELISTED_DOMAIN}'. "
            "Only official Groww scheme pages are allowed."
        )


async def fetch_html(url: str, client: httpx.AsyncClient) -> str:
    """
    Fetch a single URL and return the raw HTML string.

    Retries up to HTTP_MAX_RETRIES times with exponential backoff on:
      - Network errors (ConnectError, TimeoutException, etc.)
      - HTTP 429 (rate limited)
      - HTTP 5xx (server errors)

    Parameters
    ----------
    url    : The Groww scheme page URL to fetch.
    client : A shared httpx.AsyncClient (caller owns lifecycle).

    Returns
    -------
    str : Raw HTML of the page.

    Raises
    ------
    DomainNotAllowedError : If the URL is outside groww.in.
    FetchError            : If all retries are exhausted.
    """
    _assert_whitelisted(url)

    last_error: Exception | None = None

    for attempt in range(1, HTTP_MAX_RETRIES + 1):
        try:
            logger.info("Fetching %s (attempt %d/%d)", url, attempt, HTTP_MAX_RETRIES)
            response = await client.get(url, follow_redirects=True)

            if response.status_code == 200:
                logger.info("Successfully fetched %s (%d bytes)", url, len(response.text))
                return response.text

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", HTTP_BACKOFF_SECONDS[attempt - 1]))
                logger.warning("Rate limited on %s. Waiting %ds before retry.", url, retry_after)
                await asyncio.sleep(retry_after)
                last_error = httpx.HTTPStatusError(
                    f"HTTP 429 on {url}", request=response.request, response=response
                )
                continue

            if response.status_code >= 500:
                logger.warning("Server error %d on %s.", response.status_code, url)
                last_error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code} on {url}",
                    request=response.request,
                    response=response,
                )
            else:
                # 4xx other than 429 — not worth retrying
                raise FetchError(
                    f"Non-retryable HTTP {response.status_code} for URL: {url}"
                )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
            logger.warning("Network error on %s (attempt %d): %s", url, attempt, exc)
            last_error = exc

        # Wait before next retry (skip sleep after final attempt)
        if attempt < HTTP_MAX_RETRIES:
            backoff = HTTP_BACKOFF_SECONDS[attempt - 1]
            logger.info("Waiting %ds before retry %d...", backoff, attempt + 1)
            await asyncio.sleep(backoff)

    raise FetchError(
        f"All {HTTP_MAX_RETRIES} fetch attempts failed for '{url}'. "
        f"Last error: {last_error}"
    )


async def fetch_all(urls: list[str]) -> dict[str, str | None]:
    """
    Fetch all URLs concurrently using a single shared httpx.AsyncClient.

    Returns a dict mapping each URL to its HTML (or None if fetching failed).
    Failed URLs are logged but do not raise — the pipeline continues with
    whatever was successfully fetched.

    Parameters
    ----------
    urls : List of Groww scheme URLs to fetch.

    Returns
    -------
    dict[str, str | None] : {url: html_or_none}
    """
    results: dict[str, str | None] = {}

    async with httpx.AsyncClient(
        headers=HTTP_HEADERS,
        timeout=httpx.Timeout(HTTP_TIMEOUT_SECONDS),
        http2=False,    # force HTTP/1.1 — proxies may serve stripped pages over HTTP/2
        verify=False,   # corporate proxy uses SSL inspection
    ) as client:
        tasks = {url: fetch_html(url, client) for url in urls}

        for url, coro in tasks.items():
            try:
                html = await coro
                results[url] = html
            except (FetchError, DomainNotAllowedError) as exc:
                logger.error("Skipping %s — %s", url, exc)
                results[url] = None

    successful = sum(1 for v in results.values() if v is not None)
    logger.info(
        "Fetch complete: %d/%d URLs successful.", successful, len(urls)
    )
    return results
