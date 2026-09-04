"""Retrieval module — plain-text BM25 search backend."""

from rag.retrieval.base import SearchResult
from rag.retrieval.factory import get_search_service
from rag.retrieval.text_search import TextSearchService

__all__ = [
    "get_search_service",
    "TextSearchService",
    "SearchResult",
]
