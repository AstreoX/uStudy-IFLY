"""Factory for selecting the active retrieval backend."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from rag.retrieval.text_search import TextSearchService


def get_search_service(db: AsyncSession) -> TextSearchService:
    """Return the plain-text search backend."""
    return TextSearchService(db)
