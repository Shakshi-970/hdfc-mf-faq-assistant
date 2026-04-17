"""
phases/phase_3_3_scraping_service/parser.py
---------------------------------------------
HTML parser and field extractor for Groww mutual fund scheme pages.

Extraction strategy (tried in order per field):
  1. window.__NEXT_DATA__ JSON  — most reliable for Next.js/Groww SSR data
  2. data-field attribute       — [data-field="<fieldName>"]
  3. CSS class selector         — class*='fieldName' patterns
  4. Regex on visible text      — last resort

Free-text sections (fund description, investment objective) are extracted
separately and returned as a list of paragraph strings.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from .config import (
    ELSS_ONLY_FIELDS,
    FIELD_SELECTORS,
    SCHEME_META,
    STANDARD_FIELDS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug_from_url(url: str) -> str:
    """Extract the scheme slug from a Groww URL path."""
    return urlparse(url).path.rstrip("/").split("/")[-1]


def _extract_next_data(soup: BeautifulSoup) -> dict[str, Any]:
    """
    Parse window.__NEXT_DATA__ from the <script id="__NEXT_DATA__"> tag.
    Returns an empty dict if the tag is absent or malformed.
    """
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return {}
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError as exc:
        logger.debug("Failed to parse __NEXT_DATA__: %s", exc)
        return {}


def _resolve_dotpath(data: dict[str, Any], dotpath: str) -> str | None:
    """
    Walk a nested dict by a dot-separated key path.
    Returns the stringified value, or None if any key is missing.

    Example: _resolve_dotpath(d, "props.pageProps.schemeData.nav")
    """
    parts = dotpath.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None

    # Flatten lists (e.g. fund managers returned as a list of names)
    if isinstance(current, list):
        return ", ".join(str(item) for item in current if item)

    return str(current).strip() if current is not None else None


def _extract_visible_text(soup: BeautifulSoup) -> str:
    """
    Return all visible text from the page with boilerplate removed.
    Used as the corpus for regex-based fallback extraction.
    """
    # Remove non-content tags
    for tag in soup(["script", "style", "noscript", "nav", "footer",
                     "header", "aside", "iframe", "svg"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _get_tag_text(tag: Tag | None) -> str | None:
    """Return stripped text content of a BS4 tag, or None if tag is falsy."""
    if tag is None:
        return None
    text = tag.get_text(strip=True)
    return text if text else None


# ---------------------------------------------------------------------------
# Core extractor
# ---------------------------------------------------------------------------

def _extract_field(
    field_name: str,
    soup: BeautifulSoup,
    next_data: dict[str, Any],
    visible_text: str,
) -> str | None:
    """
    Try all configured strategies for a single field.
    Returns the first non-empty value found, or None.
    """
    strategies = FIELD_SELECTORS.get(field_name, [])

    for strategy in strategies:
        stype = strategy["type"]
        value = strategy["value"]
        result: str | None = None

        try:
            if stype == "next_data":
                result = _resolve_dotpath(next_data, value)

            elif stype == "data_attr":
                tag = soup.find(attrs={"data-field": value})
                result = _get_tag_text(tag)

            elif stype == "css":
                tag = soup.select_one(value)
                result = _get_tag_text(tag)

            elif stype == "text_re":
                match = re.search(value, visible_text, re.IGNORECASE)
                if match:
                    result = match.group(1).strip()

        except Exception as exc:
            logger.debug("Strategy %s/%s failed for field '%s': %s", stype, value, field_name, exc)
            continue

        if result:
            logger.debug("Field '%s' resolved via strategy '%s': %s", field_name, stype, result[:80])
            return result

    logger.warning("Field '%s' could not be extracted — all strategies exhausted.", field_name)
    return None


def _extract_free_text(soup: BeautifulSoup, next_data: dict[str, Any]) -> list[str]:
    """
    Extract free-text sections: fund description, investment objective, etc.

    Tries __NEXT_DATA__ JSON paths first, then falls back to <p> tags
    inside content sections.
    """
    paragraphs: list[str] = []

    # Strategy 1: __NEXT_DATA__ known keys
    text_paths = [
        "props.pageProps.schemeData.overview",
        "props.pageProps.schemeData.investmentObjective",
        "props.pageProps.schemeData.aboutFund",
        "props.pageProps.fundData.overview",
    ]
    for path in text_paths:
        text = _resolve_dotpath(next_data, path)
        if text and len(text) > 30:
            # Split into sentences / paragraphs
            for para in re.split(r"\n{2,}|\. (?=[A-Z])", text):
                para = para.strip()
                if len(para) > 40:
                    paragraphs.append(para)

    if paragraphs:
        return paragraphs

    # Strategy 2: <p> tags inside known content containers
    content_selectors = [
        "[class*='overview']",
        "[class*='about']",
        "[class*='objective']",
        "[class*='description']",
        "main",
        "article",
    ]
    for selector in content_selectors:
        container = soup.select_one(selector)
        if container:
            for p in container.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 40:
                    paragraphs.append(text)
            if paragraphs:
                break

    return paragraphs


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def parse_scheme_page(url: str, html: str) -> dict[str, Any]:
    """
    Parse a Groww scheme page HTML and return a structured dict.

    Parameters
    ----------
    url  : The source URL (used for slug lookup and metadata).
    html : Raw HTML string from the fetcher.

    Returns
    -------
    dict with keys:
        scheme_name, source_url, amc, category, scraped_at,
        fields: {field_name: value_or_null},
        free_text: [paragraph_strings]
    """
    slug = _slug_from_url(url)
    meta = SCHEME_META.get(slug, {})
    is_elss = meta.get("category", "").upper() == "ELSS"

    soup = BeautifulSoup(html, "html.parser")
    next_data = _extract_next_data(soup)
    visible_text = _extract_visible_text(soup)

    # Determine which fields to extract for this scheme
    fields_to_extract = list(STANDARD_FIELDS)
    if is_elss:
        fields_to_extract += ELSS_ONLY_FIELDS

    extracted_fields: dict[str, str | None] = {}
    for field_name in fields_to_extract:
        extracted_fields[field_name] = _extract_field(
            field_name, soup, next_data, visible_text
        )

    # Use static category from config if page didn't yield one
    if not extracted_fields.get("category"):
        extracted_fields["category"] = meta.get("category")

    free_text = _extract_free_text(soup, next_data)

    # Use the canonical scheme_name from SCHEME_META so chunk metadata
    # matches the names used in the rewriter's scheme aliases and session context.
    # Fall back to the page-extracted name only if the slug is unrecognised.
    canonical_name = meta.get("scheme_name") or extracted_fields.pop("scheme_name")
    _ = extracted_fields.pop("scheme_name", None)   # discard if still present

    result = {
        "scheme_name": canonical_name,
        "source_url": url,
        "amc": meta.get("amc", "HDFC Mutual Fund"),
        "category": extracted_fields.pop("category", None) or meta.get("category"),
        "fields": extracted_fields,
        "free_text": free_text,
    }

    extracted_count = sum(1 for v in extracted_fields.values() if v is not None)
    logger.info(
        "Parsed '%s': %d/%d fields extracted, %d free-text paragraphs.",
        result["scheme_name"],
        extracted_count,
        len(extracted_fields),
        len(free_text),
    )
    return result
