"""Crawler module - Enhanced web content extraction and search.

Provides a unified content extraction pipeline with fallback chain:
  trafilatura (static) → Crawl4AI (JS render) → Jina Reader (API backup)

And enhanced search:
  SearXNG (aggregated) → DuckDuckGo (backup)
"""
