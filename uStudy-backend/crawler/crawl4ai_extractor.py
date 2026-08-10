"""Crawl4AI REST API content extractor.

Crawl4AI runs as a Docker service with headless Chromium,
enabling JS rendering for SPA pages.

API docs: https://docs.crawl4ai.com/
"""

from __future__ import annotations

import logging

import httpx

from crawler.base import ContentResult
from config import get_settings

logger = logging.getLogger(__name__)


async def extract(url: str, *, timeout: int | None = None) -> ContentResult | None:
    """Extract content from a URL using the Crawl4AI REST API.

    Returns None if Crawl4AI is disabled or the request fails.
    """
    settings = get_settings()

    if not settings.crawl4ai_enabled or not settings.crawl4ai_api_url:
        logger.debug("Crawl4AI disabled or not configured, skipping")
        return None

    if timeout is None:
        timeout = settings.crawl4ai_timeout_seconds

    api_url = settings.crawl4ai_api_url.rstrip("/")
    crawl_endpoint = f"{api_url}/crawl"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.crawl4ai_api_token:
        headers["Authorization"] = f"Bearer {settings.crawl4ai_api_token}"

    payload = {
        "urls": url,
        "priority": 8,
        "word_count_threshold": 50,
        "exclude_external_links": True,
        "process_iframes": False,
        "remove_overlay_elements": True,
        "magic": True,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(crawl_endpoint, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Crawl4AI returns result in data.result or data.results[0]
            result_data = data.get("result") or (data.get("results") or [{}])[0]

            markdown = result_data.get("markdown") or result_data.get("markdown_v2", {}).get("raw_markdown", "")
            if not markdown or not markdown.strip():
                logger.warning("Crawl4AI returned empty markdown for: %s", url[:100])
                return None

            title = result_data.get("metadata", {}).get("title", "") or url
            links = result_data.get("links", {})

            return ContentResult(
                content=markdown.strip(),
                title=title,
                url=url,
                content_type="webpage",
                extraction_method="crawl4ai",
                metadata={
                    "content_length": len(markdown),
                    "internal_links": links.get("internal", []),
                    "external_links": links.get("external", []),
                },
            )

    except httpx.TimeoutException:
        logger.warning("Crawl4AI timeout for: %s", url[:100])
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("Crawl4AI HTTP %d for: %s", exc.response.status_code, url[:100])
        return None
    except Exception as exc:
        logger.warning("Crawl4AI error for %s: %s", url[:100], exc)
        return None
