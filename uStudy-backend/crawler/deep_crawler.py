"""Deep crawler — multi-page BFS crawling within a domain.

Uses Crawl4AI link discovery + content extraction to crawl
documentation sites, tutorial series, etc.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from urllib.parse import urljoin, urlparse

from crawler.ssrf import is_safe_url as _is_safe_url
from crawler.base import ContentResult
from crawler.router import ContentRouter
from config import get_settings

logger = logging.getLogger(__name__)


class DeepCrawler:
    """BFS-based multi-page crawler with safety limits."""

    def __init__(self) -> None:
        self._router = ContentRouter()

    async def crawl(
        self,
        start_url: str,
        *,
        max_pages: int = 10,
        max_depth: int = 2,
        url_pattern: str | None = None,
        timeout: int | None = None,
    ) -> list[ContentResult]:
        """Crawl pages starting from start_url via BFS.

        Args:
            start_url: Entry point URL.
            max_pages: Maximum number of pages to crawl (hard limit: 20).
            max_depth: Maximum link-following depth (hard limit: 3).
            url_pattern: Optional regex to filter discovered URLs.
            timeout: Overall timeout in seconds.

        Returns:
            List of ContentResult for successfully extracted pages.
        """
        settings = get_settings()

        if not settings.deep_crawl_enabled:
            return []

        # Enforce hard limits
        max_pages = min(max_pages, settings.deep_crawl_max_pages, 20)
        max_depth = min(max_depth, settings.deep_crawl_max_depth, 3)
        if timeout is None:
            timeout = settings.deep_crawl_timeout_seconds

        url_re = re.compile(url_pattern) if url_pattern else None
        parsed_start = urlparse(start_url)
        base_domain = parsed_start.netloc

        visited: set[str] = set()
        results: list[ContentResult] = []
        queue: deque[tuple[str, int]] = deque()  # (url, depth)
        queue.append((start_url, 0))

        try:
            async with asyncio.timeout(timeout):
                while queue and len(results) < max_pages:
                    url, depth = queue.popleft()

                    # Normalize and deduplicate
                    normalized = _normalize_url(url)
                    if normalized in visited:
                        continue
                    visited.add(normalized)

                    # SSRF check every URL
                    is_safe, error = await asyncio.to_thread(_is_safe_url, url)
                    if not is_safe:
                        logger.warning("SSRF blocked during deep crawl: %s — %s", url[:80], error)
                        continue

                    # Extract content
                    result = await self._router.extract(url)
                    if result:
                        results.append(result)
                        logger.info(
                            "Deep crawl [%d/%d] depth=%d: %s (%d chars)",
                            len(results), max_pages, depth, url[:80], len(result.content),
                        )

                        # Discover links for next depth level
                        if depth < max_depth:
                            links = result.metadata.get("internal_links", [])
                            for link_info in links:
                                link_url = link_info if isinstance(link_info, str) else link_info.get("href", "")
                                if not link_url:
                                    continue
                                abs_url = urljoin(url, link_url)
                                abs_normalized = _normalize_url(abs_url)

                                # Same domain only
                                if urlparse(abs_url).netloc != base_domain:
                                    continue
                                # URL pattern filter
                                if url_re and not url_re.search(abs_url):
                                    continue
                                if abs_normalized not in visited:
                                    queue.append((abs_url, depth + 1))

        except TimeoutError:
            logger.warning(
                "Deep crawl timeout after %ds, collected %d/%d pages from %s",
                timeout, len(results), max_pages, start_url[:80],
            )

        return results

    async def discover_urls(
        self,
        start_url: str,
        *,
        max_pages: int = 10,
        max_depth: int = 2,
        url_pattern: str | None = None,
        timeout: int | None = None,
    ) -> list[str]:
        """Discover URLs without extracting full content.

        Lighter version of crawl() that only returns discovered URLs.
        Useful for Phase 5 batch import where URLs are processed separately.
        """
        settings = get_settings()

        if not settings.deep_crawl_enabled:
            return []

        max_pages = min(max_pages, settings.deep_crawl_max_pages, 20)
        max_depth = min(max_depth, settings.deep_crawl_max_depth, 3)
        if timeout is None:
            timeout = min(settings.deep_crawl_timeout_seconds, 120)

        url_re = re.compile(url_pattern) if url_pattern else None
        parsed_start = urlparse(start_url)
        base_domain = parsed_start.netloc

        visited: set[str] = set()
        discovered: list[str] = [start_url]
        queue: deque[tuple[str, int]] = deque()
        queue.append((start_url, 0))

        try:
            async with asyncio.timeout(timeout):
                while queue and len(discovered) < max_pages:
                    url, depth = queue.popleft()
                    normalized = _normalize_url(url)
                    if normalized in visited:
                        continue
                    visited.add(normalized)

                    if depth >= max_depth:
                        continue

                    # SSRF check
                    is_safe, _ = await asyncio.to_thread(_is_safe_url, url)
                    if not is_safe:
                        continue

                    # Extract content to discover links
                    result = await self._router.extract(url)
                    if not result:
                        continue

                    links = result.metadata.get("internal_links", [])
                    for link_info in links:
                        link_url = link_info if isinstance(link_info, str) else link_info.get("href", "")
                        if not link_url:
                            continue
                        abs_url = urljoin(url, link_url)
                        abs_normalized = _normalize_url(abs_url)

                        if urlparse(abs_url).netloc != base_domain:
                            continue
                        if url_re and not url_re.search(abs_url):
                            continue
                        if abs_normalized not in visited and abs_url not in discovered:
                            discovered.append(abs_url)
                            queue.append((abs_url, depth + 1))

        except TimeoutError:
            logger.warning("URL discovery timeout, found %d URLs", len(discovered))

        return discovered[:max_pages]


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication (strip fragment, trailing slash)."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}{'?' + parsed.query if parsed.query else ''}"
