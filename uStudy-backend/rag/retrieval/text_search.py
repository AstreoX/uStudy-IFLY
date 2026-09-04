"""Plain-text BM25 search service using PostgreSQL tsvector/ts_rank."""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from rag.retrieval.base import SearchResult

logger = logging.getLogger(__name__)

_IMAGE_PLACEHOLDER_RE = re.compile(r"\[IMAGE:([^\]]+)\]")

EXCERPT_CONTEXT_CHARS = 200
REGEX_STATEMENT_TIMEOUT_MS = 1500


class TextSearchTimeoutError(RuntimeError):
    """Raised when PostgreSQL cancels a bounded regex search."""


def extract_excerpt(
    full_text: str, keyword: str, context_chars: int = EXCERPT_CONTEXT_CHARS
) -> str:
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
    """Text search over active PDF page chunks plus legacy document text.

    Agentic PDFs are generation-isolated through ``PdfVisualIndex.is_current``.
    Documents without a published visual index retain the legacy
    ``document_texts`` path, so this migration does not require a backfill.
    """

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
            from rag.retrieval.text_segmentation import (
                build_tsquery,
                segment_for_search,
            )
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
            WITH active_pdf_results AS (
                SELECT
                    dc.id AS result_id,
                    dc.document_id,
                    dc.content,
                    (
                        ts_rank(dc.content_tsv, to_tsquery('simple', :tsquery))
                        * CASE WHEN dc.chunk_kind = 'outline_entry' THEN 1.5 ELSE 1.0 END
                    ) AS score,
                    sd.title AS document_title,
                    sd.original_filename AS document_filename,
                    dc.chunk_kind,
                    dc.physical_page_start,
                    dc.physical_page_end,
                    FALSE AS legacy_text
                FROM document_chunks dc
                JOIN pdf_visual_indexes pvi
                  ON pvi.id = dc.pdf_visual_index_id
                 AND pvi.is_current = TRUE
                 AND pvi.state = 'published'
                JOIN space_documents sd ON sd.id = dc.document_id
                WHERE dc.space_id = :space_id
                  AND dc.content_tsv @@ to_tsquery('simple', :tsquery)
            ),
            legacy_results AS (
                SELECT
                    dt.id AS result_id,
                    dt.document_id,
                    dt.content,
                    ts_rank(dt.content_tsv, to_tsquery('simple', :tsquery)) AS score,
                    sd.title AS document_title,
                    sd.original_filename AS document_filename,
                    NULL::varchar AS chunk_kind,
                    NULL::integer AS physical_page_start,
                    NULL::integer AS physical_page_end,
                    TRUE AS legacy_text
                FROM document_texts dt
                JOIN space_documents sd ON sd.id = dt.document_id
                LEFT JOIN pdf_visual_indexes current_pdf
                  ON current_pdf.document_id = dt.document_id
                 AND current_pdf.is_current = TRUE
                 AND current_pdf.state = 'published'
                WHERE dt.space_id = :space_id
                  AND current_pdf.id IS NULL
                  AND dt.content_tsv @@ to_tsquery('simple', :tsquery)
            )
            SELECT * FROM (
                SELECT * FROM active_pdf_results
                UNION ALL
                SELECT * FROM legacy_results
            ) ranked
            ORDER BY score DESC
            LIMIT :limit
        """)

        try:
            result = await self.db.execute(
                sql,
                {"space_id": str(space_id), "tsquery": tsquery_str, "limit": top_k},
            )
        except SQLAlchemyError as exc:
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

        image_map = await self._fetch_images(all_image_ids, space_id=space_id)

        search_results: list[SearchResult] = []
        for row, img_ids in zip(rows, row_image_ids):
            if score_threshold > 0 and row.score < score_threshold:
                continue

            first_token = tokens[0] if tokens else query
            excerpt = extract_excerpt(row.content, first_token)
            images = [
                image_map[iid]
                for iid in img_ids
                if iid in image_map
                and image_map[iid]["document_id"] == str(row.document_id)
            ]

            search_results.append(
                SearchResult(
                    chunk_id=uuid.UUID(str(row.result_id)),
                    document_id=uuid.UUID(str(row.document_id)),
                    content=excerpt,
                    score=float(row.score),
                    metadata={
                        "full_text_id": str(row.result_id) if row.legacy_text else None,
                        "chunk_kind": row.chunk_kind,
                        "page_number": row.physical_page_start,
                        "page_end": row.physical_page_end,
                    },
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
        """Regex search over active PDF chunks plus legacy full text."""
        sql = text("""
            WITH active_pdf_results AS (
                SELECT dc.id AS result_id, dc.document_id, dc.content,
                       sd.title AS document_title,
                       sd.original_filename AS document_filename,
                       dc.chunk_kind, dc.physical_page_start, dc.physical_page_end,
                       FALSE AS legacy_text
                FROM document_chunks dc
                JOIN pdf_visual_indexes pvi
                  ON pvi.id = dc.pdf_visual_index_id
                 AND pvi.is_current = TRUE
                 AND pvi.state = 'published'
                JOIN space_documents sd ON sd.id = dc.document_id
                WHERE dc.space_id = :space_id AND dc.content ~ :pattern
            ),
            legacy_results AS (
                SELECT dt.id AS result_id, dt.document_id, dt.content,
                       sd.title AS document_title,
                       sd.original_filename AS document_filename,
                       NULL::varchar AS chunk_kind,
                       NULL::integer AS physical_page_start,
                       NULL::integer AS physical_page_end,
                       TRUE AS legacy_text
                FROM document_texts dt
                JOIN space_documents sd ON sd.id = dt.document_id
                LEFT JOIN pdf_visual_indexes current_pdf
                  ON current_pdf.document_id = dt.document_id
                 AND current_pdf.is_current = TRUE
                 AND current_pdf.state = 'published'
                WHERE dt.space_id = :space_id
                  AND current_pdf.id IS NULL
                  AND dt.content ~ :pattern
            )
            SELECT * FROM (
                SELECT combined.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY legacy_text
                           ORDER BY document_id,
                                    physical_page_start NULLS FIRST,
                                    result_id
                       ) AS source_rank
                FROM (
                    SELECT * FROM active_pdf_results
                    UNION ALL
                    SELECT * FROM legacy_results
                ) combined
            ) matches
            ORDER BY source_rank, legacy_text, document_id,
                     physical_page_start NULLS FIRST, result_id
            LIMIT :limit
        """)

        try:
            bind = self.db.get_bind()
            if getattr(getattr(bind, "dialect", None), "name", None) == "postgresql":
                await self.db.execute(
                    text(
                        f"SET LOCAL statement_timeout = "
                        f"'{REGEX_STATEMENT_TIMEOUT_MS}ms'"
                    )
                )
            result = await self.db.execute(
                sql,
                {"space_id": str(space_id), "pattern": pattern, "limit": max_results},
            )
        except SQLAlchemyError as exc:
            error_text = str(exc).lower()
            if "statement timeout" in error_text or "canceling statement" in error_text:
                raise TextSearchTimeoutError("regex search timed out") from exc
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

        image_map = await self._fetch_images(all_image_ids, space_id=space_id)

        search_results: list[SearchResult] = []
        for row, img_ids in zip(rows, row_image_ids):
            excerpt = extract_excerpt(row.content, pattern[:20])
            images = [
                image_map[iid]
                for iid in img_ids
                if iid in image_map
                and image_map[iid]["document_id"] == str(row.document_id)
            ]
            search_results.append(
                SearchResult(
                    chunk_id=uuid.UUID(str(row.result_id)),
                    document_id=uuid.UUID(str(row.document_id)),
                    content=excerpt,
                    score=1.0,
                    metadata={
                        "regex_pattern": pattern,
                        "chunk_kind": row.chunk_kind,
                        "page_number": row.physical_page_start,
                        "page_end": row.physical_page_end,
                    },
                    document_title=row.document_title,
                    document_filename=row.document_filename,
                    retrieval_score=1.0,
                    retrieval_source="regex",
                    images=images,
                )
            )

        return search_results

    async def _fetch_images(
        self, image_ids: set[str], *, space_id: uuid.UUID
    ) -> dict[str, dict]:
        """Fetch DocumentImage rows for the given UUIDs."""
        if not image_ids:
            return {}

        sql = text("""
            SELECT id, document_id, file_path, vlm_description, page_num
            FROM document_images
            WHERE id::text = ANY(:ids)
              AND space_id = :space_id
        """)

        result = await self.db.execute(
            sql,
            {"ids": list(image_ids), "space_id": str(space_id)},
        )
        rows = result.fetchall()

        return {
            str(row.id): {
                "image_id": str(row.id),
                "document_id": str(row.document_id),
                "file_path": row.file_path,
                "vlm_description": row.vlm_description,
                "page_num": row.page_num,
            }
            for row in rows
        }
