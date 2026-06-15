"""Lightweight web research: fetch a company page and extract readable text."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 20.0
_MAX_CHARS = 12_000
_USER_AGENT = (
    "Mozilla/5.0 (compatible; DealPulse/1.0; +https://github.com/ak-abdullah/DealPulse)"
)


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme:
        return f"https://{url}"
    return url


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    collapsed = "\n".join(line for line in lines if line)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed[:_MAX_CHARS]


def fetch_company_page_text(url: str | None) -> str:
    """
    Fetch a company homepage (or given URL) and return plain text for the LLM.

    Returns an empty string when the URL is missing or the fetch fails.
    """
    normalized = _normalize_url(url or "")
    if not normalized:
        LOGGER.info("No company website URL; skipping web fetch")
        return ""

    try:
        with httpx.Client(
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response = client.get(normalized)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        LOGGER.warning("Failed to fetch %s: %s", normalized, exc)
        return ""

    content_type = (response.headers.get("content-type") or "").lower()
    if "html" not in content_type and "<html" not in response.text[:500].lower():
        LOGGER.warning("Non-HTML response from %s (%s)", normalized, content_type)
        return ""

    text = _extract_text(response.text)
    LOGGER.info("Fetched %s chars from %s", len(text), normalized)
    return text
