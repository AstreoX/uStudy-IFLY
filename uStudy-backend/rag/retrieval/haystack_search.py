"""Haystack-backed search with graceful fallback."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from rag.embedding import EmbeddingClient
from rag.haystack_support import (
    document_to_meta,
    get_haystack_document_store,
    haystack_available,
    make_space_filter,
)
from rag.retrieval.base import SearchResult
from rag.retrieval.reranker import rerank_results
from rag.retrieval.text_search import TextSearchService

logger = logging.getLogger(__name__)


class HaystackSearchService:
    """Use Haystack retrievers/rankers when possible, else fall back safely."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.embedding_client = EmbeddingClient()

    async def search(
        self,
        query: str,
        space_id: uuid.UUID,
        top_k: int = 10,
        score_threshold: float = 0.0,
        rerank: bool | None = None,
    ) -> list[SearchResult]:
        rerank = self.settings.rag_enable_rerank if rerank is None else rerank
        rerank = bool(rerank) and self.settings.rag_enable_rerank

        try:
            candidates = await self._retrieve_candidates(
                query=query,
                space_id=space_id,
                top_k=max(top_k, self.settings.rag_rerank_top_k),
                score_threshold=score_threshold,
            )
            if not candidates:
                return []

            if rerank:
                ranked = await rerank_results(
                    query,
                    candidates,
                    top_k=top_k,
                    model_name=self.settings.rag_rerank_model,
                )
            else:
                ranked = candidates[:top_k]

            return [result for result in ranked if result.score >= score_threshold]
        finally:
            await self.embedding_client.aclose()

    async def _retrieve_candidates(
        self,
        *,
        query: str,
        space_id: uuid.UUID,
        top_k: int,
        score_threshold: float,
    ) -> list[SearchResult]:
        if (
            not self.settings.haystack_use_pgvector_retrievers
            or not self.settings.haystack_mirror_enabled
            or not haystack_available()
        ):
            return await self._fallback_candidates(query, space_id, top_k, score_threshold)

        try:
            candidates = await self._retrieve_from_haystack(query, space_id, top_k)
            if candidates:
                return candidates
            logger.info("Haystack mirror returned no candidates, falling back to plain-text search")
        except Exception as exc:
            logger.warning("Haystack retrieval failed, falling back to plain-text search: %s", exc)
        return await self._fallback_candidates(query, space_id, top_k, score_threshold)

    async def _retrieve_from_haystack(
        self,
        query: str,
        space_id: uuid.UUID,
        top_k: int,
    ) -> list[SearchResult]:
        store = get_haystack_document_store()
        if store is None:
            return []

        query_embedding = await self.embedding_client.embed_query(query)
        filters = make_space_filter(str(space_id))
        dense_top_k = max(self.settings.rag_dense_top_k, top_k)
        sparse_top_k = max(self.settings.rag_sparse_top_k, top_k)

        dense_task = asyncio.to_thread(
            self._run_dense_retriever,
            store,
            query_embedding,
            filters,
            dense_top_k,
        )
        sparse_task = asyncio.to_thread(
            self._run_sparse_retriever,
            store,
            query,
            filters,
            sparse_top_k,
        )
        dense_docs, sparse_docs = await asyncio.gather(dense_task, sparse_task, return_exceptions=True)

        if isinstance(dense_docs, Exception):
            logger.warning("Haystack dense retrieval failed: %s", dense_docs)
            dense_docs = []
        if isinstance(sparse_docs, Exception):
            logger.warning("Haystack sparse retrieval failed: %s", sparse_docs)
            sparse_docs = []

        merged: dict[str, SearchResult] = {}
        for source_name, docs in (("dense", dense_docs), ("sparse", sparse_docs)):
            for rank, doc in enumerate(docs, start=1):
                meta = document_to_meta(doc)
                chunk_id = meta.get("chunk_id") or getattr(doc, "id", None)
                document_id = meta.get("document_id")
                if not chunk_id or not document_id:
                    continue
                existing = merged.get(str(chunk_id))
                score = float(getattr(doc, "score", 0.0) or 0.0)
                retrieval_score = self._normalize_haystack_score(score, rank)
                if existing is None or retrieval_score > (existing.retrieval_score or 0.0):
                    merged[str(chunk_id)] = SearchResult(
                        chunk_id=uuid.UUID(str(chunk_id)),
                        document_id=uuid.UUID(str(document_id)),
                        content=getattr(doc, "content", "") or "",
                        score=retrieval_score,
                        metadata={k: v for k, v in meta.items() if k not in {"chunk_id", "document_id"}},
                        document_title=meta.get("document_title"),
                        document_filename=meta.get("document_filename"),
                        retrieval_score=retrieval_score,
                        rerank_score=None,
                        retrieval_source=source_name,
                    )
                elif existing.retrieval_source != source_name:
                    existing.retrieval_source = "merged"

        results = sorted(
            merged.values(),
            key=lambda item: item.retrieval_score or item.score,
            reverse=True,
        )
        return results[: max(top_k, self.settings.rag_rerank_top_k)]

    @staticmethod
    def _run_dense_retriever(
        store: Any,
        query_embedding: list[float],
        filters: dict[str, Any],
        top_k: int,
    ) -> list[Any]:
        from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever

        retriever = PgvectorEmbeddingRetriever(document_store=store)
        return retriever.run(
            query_embedding=query_embedding,
            filters=filters,
            top_k=top_k,
        ).get("documents", [])

    @staticmethod
    def _run_sparse_retriever(
        store: Any,
        query: str,
        filters: dict[str, Any],
        top_k: int,
    ) -> list[Any]:
        from haystack_integrations.components.retrievers.pgvector import PgvectorKeywordRetriever

        retriever = PgvectorKeywordRetriever(document_store=store)
        return retriever.run(
            query=query,
            filters=filters,
            top_k=top_k,
        ).get("documents", [])

    async def _fallback_candidates(
        self,
        query: str,
        space_id: uuid.UUID,
        top_k: int,
        score_threshold: float,
    ) -> list[SearchResult]:
        search_service = TextSearchService(self.db)
        return await search_service.search(
            query=query,
            space_id=space_id,
            top_k=top_k,
            score_threshold=score_threshold,
        )

    @staticmethod
    def _normalize_haystack_score(raw_score: float, rank: int) -> float:
        """Convert various retriever score scales into a stable [0, 1] score."""
        if raw_score <= 0:
            return 1.0 / (20 + rank)
        if raw_score <= 1.0:
            return raw_score
        return min(1.0, raw_score / (raw_score + 10.0))
