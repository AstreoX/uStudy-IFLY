"""Chunk post-processing for gradual migration to Haystack-style indexing."""

from __future__ import annotations

import copy
import logging
import re
from typing import Iterable

from rag.chunking.base import BaseChunker, Chunk
from rag.haystack_support import haystack_available

logger = logging.getLogger(__name__)


class ChunkPreprocessor:
    """Normalize chunk metadata and optionally apply Haystack preprocessing."""

    def __init__(self, chunker: BaseChunker) -> None:
        self.chunker = chunker

    def preprocess_chunks(
        self,
        chunks: Iterable[Chunk],
        *,
        source_id: str,
        default_chunk_type: str = "passage",
    ) -> list[Chunk]:
        prepared = [self._normalize_chunk(chunk, source_id, default_chunk_type) for chunk in chunks]
        if not prepared:
            return []
        if not haystack_available():
            return prepared
        try:
            return self._split_with_haystack(prepared)
        except Exception as exc:
            logger.warning("Haystack preprocessor unavailable, using normalized chunks only: %s", exc)
            return prepared

    def _normalize_chunk(
        self,
        chunk: Chunk,
        source_id: str,
        default_chunk_type: str,
    ) -> Chunk:
        metadata = copy.deepcopy(chunk.metadata or {})
        metadata["source_id"] = source_id
        metadata.setdefault("chunk_type", default_chunk_type)

        page_number = metadata.get("page_number")
        if page_number is None:
            page_number = metadata.get("page_start") or metadata.get("slide_num")
        if page_number is not None:
            metadata["page_number"] = page_number

        headings = metadata.get("headings")
        if metadata.get("section_title") is None:
            if isinstance(headings, list) and headings:
                metadata["section_title"] = headings[-1]
            elif isinstance(headings, str) and headings.strip():
                metadata["section_title"] = headings.strip()
            else:
                extracted = self._extract_inline_heading(chunk.content)
                if extracted:
                    metadata["section_title"] = extracted

        return Chunk(
            content=chunk.content.strip(),
            index=chunk.index,
            token_count=chunk.token_count,
            metadata=metadata,
        )

    @staticmethod
    def _extract_inline_heading(content: str) -> str | None:
        first_line = next((line for line in content.strip().splitlines() if line.strip()), "")
        match = re.match(r"^\s{0,3}(#{1,6})\s+(.+)$", first_line)
        if match:
            return match.group(2).strip()
        return None

    def _split_with_haystack(self, chunks: list[Chunk]) -> list[Chunk]:
        from haystack import Document
        from haystack.components.preprocessors import DocumentPreprocessor

        documents = [
            Document(
                id=f"{chunk.metadata.get('source_id')}::{chunk.index}",
                content=chunk.content,
                meta=dict(chunk.metadata),
            )
            for chunk in chunks
        ]
        preprocessor = DocumentPreprocessor(
            split_by="word",
            split_length=max(50, self.chunker.target_size // 2),
            split_overlap=max(0, self.chunker.overlap // 4),
            respect_sentence_boundary=True,
            clean_whitespace=True,
            clean_empty_lines=True,
        )
        processed = preprocessor.run(documents=documents).get("documents", [])

        output: list[Chunk] = []
        for index, doc in enumerate(processed):
            content = (getattr(doc, "content", "") or "").strip()
            if not content:
                continue
            meta = getattr(doc, "meta", {}) or {}
            output.append(
                Chunk(
                    content=content,
                    index=index,
                    token_count=self.chunker.count_tokens(content),
                    metadata=dict(meta),
                )
            )
        return output or chunks
