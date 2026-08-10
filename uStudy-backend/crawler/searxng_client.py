"""SearXNG search client.

SearXNG is a self-hosted meta-search engine that aggregates results from
Google, Bing, Brave, Baidu, DuckDuckGo, etc.

Deployed on Tokyo server for direct access to international search engines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    snippet: str
    source: str  # "web"


class SearXNGSearchClient:
    """Client for the self-hosted SearXNG instance."""

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        language: str = "auto",
    ) -> list[SearchResult] | None:
        """Search using SearXNG.

        Returns None if SearXNG is disabled or unavailable (caller should
        fall back to DuckDuckGo).
        """
        settings = get_settings()

        if not settings.searxng_enabled or not settings.searxng_base_url:
            return None

        base_url = settings.searxng_base_url.rstrip("/")
        timeout = settings.searxng_timeout_seconds

        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "language": language,
            "pageno": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{base_url}/search", params=params)
                response.raise_for_status()

                data = response.json()
                raw_results = data.get("results", [])

                results: list[SearchResult] = []
                seen_urls: set[str] = set()

                for item in raw_results:
                    if len(results) >= max_results:
                        break
                    url = item.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append(SearchResult(
                        title=item.get("title", ""),
                        url=url,
                        snippet=item.get("content", ""),
                        source="web",
                    ))

                logger.info("SearXNG returned %d results for: %s", len(results), query[:50])
                return results

        except httpx.TimeoutException:
            logger.warning("SearXNG timeout for query: %s", query[:50])
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning("SearXNG HTTP %d for query: %s", exc.response.status_code, query[:50])
            return None
        except Exception as exc:
            logger.warning("SearXNG error: %s", exc)
            return None
