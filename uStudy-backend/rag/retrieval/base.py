"""Shared retrieval types and interfaces."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class SearchResult:
    """Unified search result used by all RAG backends."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    metadata: dict
    document_title: Optional[str]
    document_filename: Optional[str]
    retrieval_score: Optional[float] = None
    rerank_score: Optional[float] = None
    retrieval_source: str = "text"
    images: list[dict] = field(default_factory=list)


class SearchService(Protocol):
    """Protocol for retrieval backends."""

    async def search(
        self,
        query: str,
        space_id: uuid.UUID,
        top_k: int = 10,
        score_threshold: float = 0.0,
        rerank: bool | None = None,
    ) -> list[SearchResult]:
        """Search documents for a query."""

