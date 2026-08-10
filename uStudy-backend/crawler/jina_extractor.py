"""Jina Reader API content extractor.

Uses Jina Reader (https://r.jina.ai/) to extract content from URLs.
Particularly effective for JS-rendered pages (SPAs, React sites, etc.)
since Jina handles browser rendering on their end.
"""

from __future__ import annotations

import logging

import httpx

from crawler.base import ContentResult
from config import get_settings

logger = logging.getLogger(__name__)

_JINA_READER_BASE = "https://r.jina.ai/"


async def extract(url: str, *, timeout: int | None = None) -> ContentResult | None:
    """Extract content from a URL using Jina Reader API.

    Returns None if extraction fails or Jina is disabled.
    """
    settings = get_settings()

    if not settings.jina_reader_enabled:
        logger.debug("Jina Reader disabled, skipping")
        return None

    if timeout is None:
        timeout = settings.jina_reader_timeout_seconds

    headers: dict[str, str] = {
        "Accept": "text/markdown",
        "X-Return-Format": "markdown",
    }
    if settings.jina_api_key:
        headers["Authorization"] = f"Bearer {settings.jina_api_key}"

    jina_url = f"{_JINA_READER_BASE}{url}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(jina_url, headers=headers)
            response.raise_for_status()

            content = response.text.strip()
            if not content:
                logger.warning("Jina Reader returned empty content for: %s", url[:100])
                return None

            # Jina returns markdown; extract title from first # heading if present
            title = _extract_title_from_markdown(content) or url

            return ContentResult(
                content=content,
                title=title,
                url=url,
                content_type="webpage",
                extraction_method="jina",
                metadata={"content_length": len(content)},
            )

    except httpx.TimeoutException:
        logger.warning("Jina Reader timeout for: %s", url[:100])
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("Jina Reader HTTP %d for: %s", exc.response.status_code, url[:100])
        return None
    except Exception as exc:
        logger.warning("Jina Reader error for %s: %s", url[:100], exc)
        return None


def _extract_title_from_markdown(md: str) -> str:
    """Extract title from the first markdown heading."""
    for line in md.split("\n", 10):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""
