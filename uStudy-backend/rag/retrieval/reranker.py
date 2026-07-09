"""Reranking helpers for document retrieval."""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from typing import Any

from rag.haystack_support import haystack_available
from rag.retrieval.base import SearchResult
from rag.retrieval.text_segmentation import segment_for_search

logger = logging.getLogger(__name__)


def _tokenize_for_overlap(text: str) -> list[str]:
    segmented = segment_for_search(text or "")
    return [token.lower() for token in segmented.split() if len(token.strip()) > 1]


def _coverage_score(query_tokens: list[str], content_tokens: list[str]) -> float:
    if not query_tokens or not content_tokens:
        return 0.0
    query_counts = Counter(query_tokens)
    content_counts = Counter(content_tokens)
    matched = sum(min(content_counts[token], count) for token, count in query_counts.items())
    total = sum(query_counts.values())
    return matched / total if total else 0.0


def _order_bonus(query: str, content: str) -> float:
    normalized_query = re.sub(r"\s+", " ", query.strip().lower())
    normalized_content = re.sub(r"\s+", " ", content.strip().lower())
    if not normalized_query or not normalized_content:
        return 0.0
    if normalized_query in normalized_content:
        return 0.15
    return 0.0


def heuristic_rerank(
    query: str,
    results: list[SearchResult],
    *,
    top_k: int,
) -> list[SearchResult]:
    """Cheap fallback reranker used when Haystack rankers are unavailable."""
    query_tokens = _tokenize_for_overlap(query)
    scored: list[SearchResult] = []
    for result in results:
        content_tokens = _tokenize_for_overlap(result.content)
        coverage = _coverage_score(query_tokens, content_tokens)
        density = min(len(set(content_tokens) & set(query_tokens)) / 6.0, 1.0)
        base_score = result.retrieval_score if result.retrieval_score is not None else result.score
        rerank_score = min(
            1.0,
            max(
                0.0,
                0.55 * max(base_score, 0.0) + 0.3 * coverage + 0.1 * density + _order_bonus(query, result.content),
            ),
        )
        result.rerank_score = rerank_score
        result.score = rerank_score
        scored.append(result)

    scored.sort(key=lambda item: (item.score, item.retrieval_score or 0.0), reverse=True)
    return scored[:top_k]


async def rerank_results(
    query: str,
    results: list[SearchResult],
    *,
    top_k: int,
    model_name: str,
) -> list[SearchResult]:
    """Rerank results with Haystack when available, otherwise use heuristics."""
    if not results:
        return []

    if not haystack_available():
        return heuristic_rerank(query, results, top_k=top_k)

    try:
        from haystack import Document
        from haystack.components.rankers import SentenceTransformersSimilarityRanker

        docs: list[Document] = []
        by_id = {}
        for result in results:
            doc = Document(
                id=str(result.chunk_id),
                content=result.content,
                meta={
                    "chunk_id": str(result.chunk_id),
                    "document_id": str(result.document_id),
                    "document_title": result.document_title,
                    "document_filename": result.document_filename,
                    "retrieval_score": result.retrieval_score,
                    "retrieval_source": result.retrieval_source,
                    **(result.metadata or {}),
                },
            )
            docs.append(doc)
            by_id[str(result.chunk_id)] = result

        # Run CPU-bound ranker in a thread to avoid blocking the event loop.
        # warm_up() loads the model (slow on first call), run() does inference.
        def _run_ranker():
            ranker = SentenceTransformersSimilarityRanker(model=model_name)
            ranker.warm_up()
            return ranker.run(query=query, documents=docs, top_k=top_k).get("documents", [])

        ranked = await asyncio.to_thread(_run_ranker)

        reranked: list[SearchResult] = []
        for doc in ranked:
            source = by_id.get(str(getattr(doc, "id", "")))
            if source is None:
                continue
            haystack_score = getattr(doc, "score", None)
            source.rerank_score = float(haystack_score) if haystack_score is not None else source.retrieval_score
            source.score = source.rerank_score or source.score
            reranked.append(source)

        if reranked:
            return reranked
    except Exception as exc:
        logger.warning("Haystack reranker unavailable, falling back to heuristic rerank: %s", exc)

    return heuristic_rerank(query, results, top_k=top_k)
