"""Trafilatura-based content extractor for static HTML pages.

Extracted from rag/url_fetcher.py to be reused by the content router.
"""

from __future__ import annotations

import asyncio
import html as html_module
import logging
import re
import xml.etree.ElementTree as ET

import httpx
import trafilatura

from crawler.base import ContentResult

logger = logging.getLogger(__name__)

_MAX_HTML_BYTES = 5 * 1024 * 1024  # 5MB
_USER_AGENT = "Mozilla/5.0 (compatible; uStudyBot/1.0)"


async def extract(url: str, *, timeout: int = 30) -> ContentResult | None:
    """Extract content from a URL using trafilatura.

    Returns None if trafilatura cannot extract meaningful content,
    signalling the router to try the next extractor in the chain.
    """
    raw_html = await _fetch_html(url, timeout=timeout)
    if raw_html is None:
        return None

    extracted = await asyncio.to_thread(
        trafilatura.extract,
        raw_html,
        include_comments=False,
        include_tables=True,
        output_format="txt",
    )

    if not extracted or not extracted.strip():
        return None

    # Heuristic: if trafilatura returns very little text but the HTML is large,
    # the page likely requires JS rendering.
    if len(extracted.strip()) < 200 and len(raw_html) > 10_000:
        logger.info(
            "trafilatura extracted only %d chars from %d bytes HTML — likely JS-rendered: %s",
            len(extracted.strip()),
            len(raw_html),
            url[:100],
        )
        return None

    title = _extract_title(raw_html)
    return ContentResult(
        content=extracted,
        title=title or url,
        url=url,
        content_type="webpage",
        extraction_method="trafilatura",
        metadata={"content_length": len(extracted), "html_length": len(raw_html)},
    )


async def _fetch_html(url: str, *, timeout: int = 30) -> str | None:
    """Fetch raw HTML from a URL with size guard."""
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            if len(response.content) > _MAX_HTML_BYTES:
                logger.warning("HTML too large (%d bytes): %s", len(response.content), url[:100])
                return None

            return response.text
    except Exception as exc:
        logger.warning("Failed to fetch HTML for trafilatura: %s — %s", url[:100], exc)
        return None


def _extract_title(raw_html: str) -> str:
    """Try trafilatura XML output first, fall back to <title> regex."""
    try:
        xml_output = trafilatura.extract(
            raw_html,
            output_format="xml",
            include_comments=False,
        )
        if xml_output:
            root = ET.fromstring(xml_output)
            title = root.attrib.get("title", "")
            if title:
                return title
    except (ET.ParseError, Exception):
        pass

    match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    if match:
        return html_module.unescape(match.group(1)).strip()
    return ""
