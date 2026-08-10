"""Content extraction router with smart fallback chain.

Fallback chain:
  URL → trafilatura (fast, static pages)
        ↓ fails or content too short
      Crawl4AI (JS rendering via Docker)
        ↓ fails or unavailable
      Jina Reader (external API backup)
"""

from __future__ import annotations

import logging

from crawler.base import ContentResult
from crawler import trafilatura_extractor, crawl4ai_extractor, jina_extractor
from config import get_settings

logger = logging.getLogger(__name__)


class ContentRouter:
    """Smart content extraction with fallback chain."""

    async def extract(self, url: str, *, max_length: int | None = None) -> ContentResult | None:
        """Extract content from URL using the fallback chain.

        Args:
            url: Target URL (must already be SSRF-validated by caller).
            max_length: Optional character limit for content truncation.

        Returns:
            ContentResult on success, None if all extractors fail.
        """
        settings = get_settings()

        # Step 1: trafilatura (fast, handles most static pages)
        result = await trafilatura_extractor.extract(
            url, timeout=settings.url_fetch_timeout_seconds,
        )
        if result:
            logger.info("Content extracted via trafilatura: %s (%d chars)", url[:80], len(result.content))
            if max_length:
                result = _truncate(result, max_length)
            return result

        # Step 2: Crawl4AI (JS rendering)
        result = await crawl4ai_extractor.extract(url)
        if result:
            logger.info("Content extracted via Crawl4AI: %s (%d chars)", url[:80], len(result.content))
            if max_length:
                result = _truncate(result, max_length)
            return result

        # Step 3: Jina Reader (external API fallback)
        result = await jina_extractor.extract(url)
        if result:
            logger.info("Content extracted via Jina Reader: %s (%d chars)", url[:80], len(result.content))
            if max_length:
                result = _truncate(result, max_length)
            return result

        logger.warning("All extractors failed for: %s", url[:100])
        return None


def _truncate(result: ContentResult, max_length: int) -> ContentResult:
    """Truncate content at sentence boundary if too long."""
    if len(result.content) <= max_length:
        return result

    text = result.content[:max_length]
    # Try to cut at sentence boundary (Chinese or English)
    last_period = text.rfind("。")
    last_dot = text.rfind(". ")
    last_newline = text.rfind("\n")
    cut_point = max(last_period, last_dot, last_newline)

    if cut_point > max_length * 0.7:
        text = result.content[: cut_point + 1] + "..."
    else:
        text = text + "..."

    return ContentResult(
        content=text,
        title=result.title,
        url=result.url,
        content_type=result.content_type,
        extraction_method=result.extraction_method,
        metadata={**result.metadata, "truncated": True, "original_length": len(result.content)},
    )
