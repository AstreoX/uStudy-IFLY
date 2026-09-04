"""Plain-text BM25 search service using PostgreSQL tsvector/ts_rank."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from rag.retrieval.base import SearchResult

logger = logging.getLogger(__name__)

_IMAGE_PLACEHOLDER_RE = re.compile(r"\[IMAGE:([^\]]+)\]")

EXCERPT_CONTEXT_CHARS = 200


def extract_excerpt(full_text: str, keyword: str, context_chars: int = EXCERPT_CONTEXT_CHARS) -> str:
    """Return ±context_chars characters around the first occurrence of keyword in full_text."""
    idx = full_text.lower().find(keyword.lower())
    if idx == -1:
        return full_text[: context_chars * 2]
    start = max(0, idx - context_chars)
    end = min(len(full_text), idx + len(keyword) + context_chars)
    excerpt = full_text[start:end]
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(full_text):
        excerpt = excerpt + "…"
    return excerpt


def resolve_images(content: str) -> list[str]:
    """Extract image UUIDs from [IMAGE:uuid] placeholders in content."""
    return _IMAGE_PLACEHOLDER_RE.findall(content)


class TextSearchService:
    """BM25 full-text search over document_texts using PostgreSQL tsvector/ts_rank."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        query: str,
        space_id: uuid.UUID,
        top_k: int = 10,
        score_threshold: float = 0.0,
        rerank: bool | None = None,
    ) -> list[SearchResult]:
        """BM25 full-text search. Returns excerpts with images auto-attached."""
        if not query.strip():
            return []

        try:
            from rag.retrieval.text_segmentation import build_tsquery, segment_for_search
        except ImportError:
            logger.error("text_segmentation module not available")
            return []

        # segment_for_search(text) -> str (space-separated tokens)
        segmented = segment_for_search(query)
        tokens = [t for t in segmented.split() if t]
        if not tokens:
            return []

        # build_tsquery(query) -> str (tsquery format, OR-connected)
        tsquery_str = build_tsquery(query)
        if not tsquery_str:
            return []

        sql = text("""
            SELECT
                dt.id              AS text_id,
                dt.document_id,
                dt.content,
                ts_rank(dt.content_tsv, to_tsquery('simple', :tsquery)) AS score,
                sd.title           AS document_title,
                sd.original_filename AS document_filename
            FROM document_texts dt
            JOIN space_documents sd ON sd.id = dt.document_id
            WHERE
                dt.space_id = :space_id
                AND dt.content_tsv @@ to_tsquery('simple', :tsquery)
            ORDER BY score DESC
            LIMIT :limit
        """)

        try:
            result = await self.db.execute(
                sql,
                {"space_id": str(space_id), "tsquery": tsquery_str, "limit": top_k},
            )
        except Exception as exc:
            logger.warning("BM25 search failed for query '%s': %s", query, exc)
            return []
        rows = result.fetchall()

        if not rows:
            return []

        all_image_ids: set[str] = set()
        row_image_ids: list[list[str]] = []
        for row in rows:
            ids = resolve_images(row.content)
            row_image_ids.append(ids)
            all_image_ids.update(ids)

        image_map = await self._fetch_images(all_image_ids)

        search_results: list[SearchResult] = []
        for row, img_ids in zip(rows, row_image_ids):
            if score_threshold > 0 and row.score < score_threshold:
                continue

            first_token = tokens[0] if tokens else query
            excerpt = extract_excerpt(row.content, first_token)
            images = [image_map[iid] for iid in img_ids if iid in image_map]

            search_results.append(
                SearchResult(
                    chunk_id=uuid.UUID(str(row.text_id)),
                    document_id=uuid.UUID(str(row.document_id)),
                    content=excerpt,
                    score=float(row.score),
                    metadata={"full_text_id": str(row.text_id)},
                    document_title=row.document_title,
                    document_filename=row.document_filename,
                    retrieval_score=float(row.score),
                    retrieval_source="text",
                    images=images,
                )
            )

        return search_results

    async def search_regex(
        self,
        pattern: str,
        space_id: uuid.UUID,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """Regex/pattern search over document_texts.content."""
        sql = text("""
            SELECT
                dt.id              AS text_id,
                dt.document_id,
                dt.content,
                sd.title           AS document_title,
                sd.original_filename AS document_filename
            FROM document_texts dt
            JOIN space_documents sd ON sd.id = dt.document_id
            WHERE
                dt.space_id = :space_id
                AND dt.content ~ :pattern
            LIMIT :limit
        """)

        try:
            result = await self.db.execute(
                sql,
                {"space_id": str(space_id), "pattern": pattern, "limit": max_results},
            )
        except Exception as exc:
            logger.warning("Regex search failed for pattern '%s': %s", pattern, exc)
            return []

        rows = result.fetchall()
        if not rows:
            return []

        all_image_ids: set[str] = set()
        row_image_ids: list[list[str]] = []
        for row in rows:
            ids = resolve_images(row.content)
            row_image_ids.append(ids)
            all_image_ids.update(ids)

        image_map = await self._fetch_images(all_image_ids)

        search_results: list[SearchResult] = []
        for row, img_ids in zip(rows, row_image_ids):
            excerpt = extract_excerpt(row.content, pattern[:20])
            images = [image_map[iid] for iid in img_ids if iid in image_map]
            search_results.append(
                SearchResult(
                    chunk_id=uuid.UUID(str(row.text_id)),
                    document_id=uuid.UUID(str(row.document_id)),
                    content=excerpt,
                    score=1.0,
                    metadata={"regex_pattern": pattern},
                    document_title=row.document_title,
                    document_filename=row.document_filename,
                    retrieval_score=1.0,
                    retrieval_source="regex",
                    images=images,
                )
            )

        return search_results

    async def _fetch_images(self, image_ids: set[str]) -> dict[str, dict]:
        """Fetch DocumentImage rows for the given UUIDs."""
        if not image_ids:
            return {}

        sql = text("""
            SELECT id, file_path, vlm_description, page_num
            FROM document_images
            WHERE id::text = ANY(:ids)
        """)

        result = await self.db.execute(sql, {"ids": list(image_ids)})
        rows = result.fetchall()

        return {
            str(row.id): {
                "image_id": str(row.id),
                "file_path": row.file_path,
                "vlm_description": row.vlm_description,
                "page_num": row.page_num,
            }
            for row in rows
        }
