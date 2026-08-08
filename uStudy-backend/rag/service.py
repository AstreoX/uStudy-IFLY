"""RAG document processing service."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Iterable, Optional

import aiofiles
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import (
    DocumentChunk,
    DocumentProcessingTask,
    DocumentType,
    ProcessingStatus,
    SpaceDocument,
)
from rag.chunking import Chunk, get_chunker
from rag.embedding import EmbeddingClient
from rag.parsing import NormalizedDocument, normalize_legacy_document, resolve_document_format
from rag.retrieval.text_segmentation import segment_for_search
from rag.utils import has_visual_content

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentProcessingService:
    """文档处理服务 - 负责格式解析、切片、向量化与增强流程。"""

    def __init__(
        self,
        db: AsyncSession,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self.db = db
        self.embedding_client = embedding_client or EmbeddingClient()

    async def create_processing_task(
        self, document_id: uuid.UUID
    ) -> DocumentProcessingTask:
        """为文档创建处理任务。"""
        task = DocumentProcessingTask(
            document_id=document_id,
            status=ProcessingStatus.PENDING,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_processing_task(
        self, document_id: uuid.UUID
    ) -> Optional[DocumentProcessingTask]:
        """获取文档的处理任务。"""
        result = await self.db.execute(
            select(DocumentProcessingTask).where(
                DocumentProcessingTask.document_id == document_id
            )
        )
        return result.scalar_one_or_none()

    async def process_document(self, document_id: uuid.UUID) -> None:
        """
        处理文档：
        1. 基础阶段：detect -> normalize -> iter_chunks -> embedding -> insert
        2. 增强阶段：OCR/VLM 追加 enriched chunks
        """
        try:
            await self._process_document_inner(document_id)
        finally:
            # 关闭持久化 HTTP 连接
            await self.embedding_client.aclose()

    async def _process_document_inner(self, document_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(SpaceDocument).where(SpaceDocument.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            logger.error("文档不存在: %s", document_id)
            return

        task = await self.get_processing_task(document_id)
        if not task:
            task = await self.create_processing_task(document_id)

        await self._update_task_status(
            task.id,
            ProcessingStatus.PROCESSING,
            started_at=datetime.utcnow(),
            error_message=None,
        )

        # Link documents have no local file — handle separately
        if document.doc_type == DocumentType.LINK:
            await self._process_link_document(document, task)
            return

        normalized_document: NormalizedDocument | None = None
        chunker = None
        base_chunk_count = 0

        try:
            logger.info("开始处理文档: %s (%s)", document.title, document.mime_type)
            content = await self._read_document_content(document)
            if not content:
                raise ValueError("文档内容为空")

            normalized_document = await self._resolve_and_normalize_document(
                document,
                content,
            )
            document.mime_type = normalized_document.resolved_format.mime_type

            chunker = get_chunker(normalized_document.resolved_format.mime_type)

            await self._delete_document_chunks_no_commit(document.id)

            base_chunk_count = await self._process_base_chunks(
                document=document,
                normalized_document=normalized_document,
                chunker=chunker,
                task_id=task.id,
            )
            if base_chunk_count == 0:
                raise ValueError("切片结果为空")

            await self.db.commit()
            await self._update_task_status(
                task.id,
                ProcessingStatus.COMPLETED,
                chunk_count=base_chunk_count,
                completed_at=datetime.utcnow(),
            )
            logger.info("文档基础处理完成: %s (%d chunks)", document.title, base_chunk_count)

        except Exception as exc:
            await self.db.rollback()
            logger.error("文档处理失败: %s - %s", document_id, str(exc), exc_info=True)
            await self._update_task_status(
                task.id,
                ProcessingStatus.FAILED,
                error_message=str(exc),
                completed_at=datetime.utcnow(),
            )
            raise

        if (
            normalized_document is not None
            and chunker is not None
            and settings.vlm_processing_enabled
        ):
            # 快速预检测：跳过纯文本文档的 VLM 增强阶段
            if has_visual_content(normalized_document.content, document.mime_type):
                await self._run_enrichment_stage(
                    document=document,
                    normalized_document=normalized_document,
                    chunker=chunker,
                )
            else:
                logger.info("文档无视觉内容，跳过 VLM 增强: %s", document.title)

    async def _process_link_document(
        self,
        document: SpaceDocument,
        task: DocumentProcessingTask,
    ) -> None:
        """Process a LINK-type document: fetch URL content, chunk, embed, store."""
        from rag.url_fetcher import URLContentFetcher, URLFetchError

        try:
            fetcher = URLContentFetcher()
            result = await fetcher.fetch(document.url)

            logger.info(
                "URL 内容获取成功: %s (%s, %d chars)",
                document.url,
                result.content_type,
                len(result.content),
            )

            # Update document title if it was generic
            if result.title and document.title in (document.url, ""):
                document.title = result.title

            # Choose chunker based on content type
            mime_hint = "text/markdown" if result.content_type == "webpage" else "text/plain"
            chunker = get_chunker(mime_hint)
            content_bytes = result.content.encode("utf-8")

            await self._delete_document_chunks_no_commit(document.id)

            chunk_count = 0
            total_embedding_tokens = 0
            batch_size = max(1, self.embedding_client.batch_size)
            concurrent_limit = max(1, self.embedding_client.max_concurrent)

            pending_batches: list[list[Chunk]] = []

            async for chunk_batch in self._iter_chunk_batches(
                chunker=chunker,
                content=content_bytes,
                filename=None,
                batch_size=batch_size,
            ):
                if not chunk_batch:
                    continue

                # Annotate with link-specific metadata
                for chunk in chunk_batch:
                    chunk.metadata["source_type"] = result.content_type
                    chunk.metadata["source_url"] = result.source_url
                    chunk.metadata["stage"] = "base"
                    if result.metadata:
                        chunk.metadata.update(result.metadata)

                pending_batches.append(chunk_batch)

                if len(pending_batches) >= concurrent_limit:
                    embedded = await self._embed_and_insert_group(
                        pending_batches, document,
                        task_id=task.id, current_total=chunk_count,
                    )
                    chunk_count += embedded[0]
                    total_embedding_tokens += embedded[1]
                    pending_batches = []

            # 处理剩余批次
            if pending_batches:
                embedded = await self._embed_and_insert_group(
                    pending_batches, document,
                    task_id=task.id, current_total=chunk_count,
                )
                chunk_count += embedded[0]
                total_embedding_tokens += embedded[1]

            if chunk_count == 0:
                raise ValueError("切片结果为空")

            await self.db.commit()
            await self._update_task_status(
                task.id,
                ProcessingStatus.COMPLETED,
                chunk_count=chunk_count,
                completed_at=datetime.utcnow(),
            )
            logger.info(
                "链接文档处理完成: %s (%d chunks, %d embedding tokens)",
                document.title,
                chunk_count,
                total_embedding_tokens,
            )

        except URLFetchError as exc:
            await self.db.rollback()
            logger.error("URL 内容获取失败: %s - %s", document.url, str(exc))
            await self._update_task_status(
                task.id,
                ProcessingStatus.FAILED,
                error_message=str(exc),
                completed_at=datetime.utcnow(),
            )
            raise
        except Exception as exc:
            await self.db.rollback()
            logger.error("链接文档处理失败: %s - %s", document.id, str(exc), exc_info=True)
            await self._update_task_status(
                task.id,
                ProcessingStatus.FAILED,
                error_message=str(exc),
                completed_at=datetime.utcnow(),
            )
            raise

    async def _resolve_and_normalize_document(
        self,
        document: SpaceDocument,
        content: bytes,
    ) -> NormalizedDocument:
        """Resolve actual format from bytes and normalize legacy Office formats."""
        resolved = await asyncio.to_thread(
            resolve_document_format,
            content,
            document.original_filename,
            document.mime_type,
        )
        normalized = await asyncio.to_thread(
            normalize_legacy_document,
            content,
            resolved,
            document.original_filename,
        )
        return normalized

    async def _process_base_chunks(
        self,
        *,
        document: SpaceDocument,
        normalized_document: NormalizedDocument,
        chunker,
        task_id: uuid.UUID | None = None,
    ) -> int:
        """Process and insert base chunks with concurrent embedding.

        Collects chunk batches into groups, then embeds each group concurrently
        using asyncio.gather with semaphore-based throttling.
        """
        total_chunks = 0
        total_embedding_tokens = 0
        batch_size = max(1, self.embedding_client.batch_size)
        concurrent_limit = max(1, self.embedding_client.max_concurrent)

        # 收集一组 batch，然后并发 embedding + 写入
        pending_batches: list[list[Chunk]] = []

        async for chunk_batch in self._iter_chunk_batches(
            chunker=chunker,
            content=normalized_document.content,
            filename=normalized_document.filename,
            batch_size=batch_size,
        ):
            if not chunk_batch:
                continue

            self._annotate_chunks(
                chunk_batch,
                normalized_document=normalized_document,
                stage="base",
            )
            pending_batches.append(chunk_batch)

            if len(pending_batches) >= concurrent_limit:
                embedded = await self._embed_and_insert_group(
                    pending_batches, document,
                    task_id=task_id, current_total=total_chunks,
                )
                total_chunks += embedded[0]
                total_embedding_tokens += embedded[1]
                pending_batches = []

        # 处理剩余批次
        if pending_batches:
            embedded = await self._embed_and_insert_group(
                pending_batches, document,
                task_id=task_id, current_total=total_chunks,
            )
            total_chunks += embedded[0]
            total_embedding_tokens += embedded[1]

        logger.info(
            "基础切片与向量化完成: document=%s chunks=%d embedding_tokens=%d",
            document.id,
            total_chunks,
            total_embedding_tokens,
        )
        return total_chunks

    async def _embed_and_insert_group(
        self,
        batch_group: list[list[Chunk]],
        document: SpaceDocument,
        *,
        task_id: uuid.UUID | None = None,
        current_total: int = 0,
    ) -> tuple[int, int]:
        """Embed a group of chunk batches concurrently and insert into DB.

        Updates processed_chunks after each batch insert for real-time progress.

        Returns:
            (chunk_count, embedding_token_count)
        """
        # 并发发送所有 embedding 请求
        embed_tasks = [
            self.embedding_client.embed_batch([c.content for c in batch])
            for batch in batch_group
        ]
        embedding_results = await asyncio.gather(
            *embed_tasks, return_exceptions=True
        )

        # 检查是否有失败的批次
        errors = [r for r in embedding_results if isinstance(r, BaseException)]
        if errors:
            raise errors[0]

        # 顺序写入 DB，每个 batch 后更新进度
        chunk_count = 0
        token_count = 0
        for chunks, emb_result in zip(batch_group, embedding_results):
            await self._insert_chunk_batch(
                document_id=document.id,
                space_id=document.space_id,
                chunks=chunks,
                embeddings=emb_result.embeddings,
            )
            chunk_count += len(chunks)
            token_count += emb_result.token_count

            if task_id:
                await self._update_processed_chunks(
                    task_id, current_total + chunk_count
                )

        return chunk_count, token_count

    async def _run_enrichment_stage(
        self,
        *,
        document: SpaceDocument,
        normalized_document: NormalizedDocument,
        chunker,
    ) -> None:
        """Append enriched OCR/VLM chunks without affecting completed status."""
        try:
            base_chunks = await self._load_chunks(document.id)
            if not base_chunks:
                return

            enriched_result = await chunker.enrich(
                base_chunks,
                normalized_document.content,
                filename=normalized_document.filename,
            )
            new_chunks = self._extract_enriched_chunks(
                base_chunks=base_chunks,
                enriched_chunks=enriched_result,
                normalized_document=normalized_document,
            )
            if not new_chunks:
                return

            embedding_result = await self.embedding_client.embed_batch(
                [chunk.content for chunk in new_chunks]
            )
            await self._insert_chunk_batch(
                document_id=document.id,
                space_id=document.space_id,
                chunks=new_chunks,
                embeddings=embedding_result.embeddings,
            )
            await self.db.commit()
            logger.info(
                "文档增强处理完成: document=%s added_chunks=%d",
                document.id,
                len(new_chunks),
            )
        except Exception as exc:
            await self.db.rollback()
            logger.warning("文档增强处理失败，保留基础可检索结果: %s", exc)

    def _extract_enriched_chunks(
        self,
        *,
        base_chunks: list[Chunk],
        enriched_chunks: list[Chunk],
        normalized_document: NormalizedDocument,
    ) -> list[Chunk]:
        """Select only VLM/OCR chunks and reindex them for append-only storage."""
        candidates = [
            chunk
            for chunk in enriched_chunks
            if chunk.metadata.get("vlm_type")
        ]
        if not candidates:
            return []

        next_index = max((chunk.index for chunk in base_chunks), default=-1) + 1
        prepared: list[Chunk] = []
        for offset, chunk in enumerate(candidates):
            prepared_chunk = Chunk(
                content=chunk.content,
                index=next_index + offset,
                token_count=chunk.token_count,
                metadata=dict(chunk.metadata),
            )
            prepared.append(prepared_chunk)

        self._annotate_chunks(
            prepared,
            normalized_document=normalized_document,
            stage="enriched",
        )
        return prepared

    def _annotate_chunks(
        self,
        chunks: Iterable[Chunk],
        *,
        normalized_document: NormalizedDocument,
        stage: str,
    ) -> None:
        """Attach shared metadata used by retrieval and debugging."""
        resolved = normalized_document.resolved_format
        for chunk in chunks:
            chunk.metadata.setdefault("source_type", resolved.canonical_type)
            chunk.metadata["canonical_type"] = resolved.canonical_type
            chunk.metadata["parser_backend"] = resolved.parser_backend
            chunk.metadata["stage"] = stage
            if normalized_document.filename:
                chunk.metadata.setdefault("filename", normalized_document.filename)

    async def _iter_chunk_batches(
        self,
        *,
        chunker,
        content: bytes,
        filename: str | None,
        batch_size: int,
    ) -> AsyncIterator[list[Chunk]]:
        """Run sync chunk generation in a worker thread and stream back batches."""
        item_queue: queue.Queue[object] = queue.Queue(maxsize=4)
        sentinel = object()
        errors: list[Exception] = []

        def producer() -> None:
            batch: list[Chunk] = []
            try:
                for chunk in chunker.iter_chunks(content, filename=filename):
                    batch.append(chunk)
                    if len(batch) >= batch_size:
                        item_queue.put(batch)
                        batch = []
                if batch:
                    item_queue.put(batch)
            except Exception as exc:  # pragma: no cover - forwarded to async caller
                errors.append(exc)
            finally:
                item_queue.put(sentinel)

        thread = threading.Thread(
            target=producer,
            name=f"chunker-{chunker.__class__.__name__}",
            daemon=True,
        )
        thread.start()

        while True:
            item = await asyncio.to_thread(item_queue.get)
            if item is sentinel:
                break
            yield item  # type: ignore[misc]

        thread.join()
        if errors:
            raise errors[0]

    async def _read_document_content(self, document: SpaceDocument) -> bytes:
        """读取文档内容。"""
        relative_path = document.url.lstrip("/")
        file_path = Path(settings.upload_dir).parent / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"文档文件不存在: {file_path}")

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def _insert_chunk_batch(
        self,
        *,
        document_id: uuid.UUID,
        space_id: uuid.UUID,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """使用 raw SQL 批量写入 chunk 与 embedding。

        注意：asyncpg 的 executemany 不支持 SQLAlchemy func 对象作为参数值，
        因此 to_tsvector 必须写在 SQL 文本中，而非作为 Python 对象传递。
        """
        if not chunks:
            return

        from sqlalchemy import text

        stmt = text("""
            INSERT INTO document_chunks
                (id, document_id, space_id, chunk_index, content,
                 token_count, chunk_metadata, embedding, content_tsv)
            VALUES
                (:id, :document_id, :space_id, :chunk_index, :content,
                 :token_count, :chunk_metadata, :embedding,
                 to_tsvector('simple', :search_text))
        """)

        rows = [
            {
                "id": str(uuid.uuid4()),
                "document_id": str(document_id),
                "space_id": str(space_id),
                "chunk_index": chunk.index,
                "content": chunk.content,
                "token_count": chunk.token_count,
                "chunk_metadata": json.dumps(chunk.metadata),
                "embedding": str(embedding),
                "search_text": segment_for_search(chunk.content),
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]
        for row in rows:
            await self.db.execute(stmt, row)

    async def _load_chunks(self, document_id: uuid.UUID) -> list[Chunk]:
        """Load already stored chunks back into chunk objects."""
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        records = result.scalars().all()
        return [
            Chunk(
                content=record.content,
                index=record.chunk_index,
                token_count=record.token_count,
                metadata=dict(record.chunk_metadata or {}),
            )
            for record in records
        ]

    async def _delete_document_chunks_no_commit(self, document_id: uuid.UUID) -> None:
        """Delete document chunks without committing the transaction."""
        await self.db.execute(
            DocumentChunk.__table__.delete().where(
                DocumentChunk.document_id == document_id
            )
        )

    async def _update_task_status(
        self,
        task_id: uuid.UUID,
        status: ProcessingStatus,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """更新任务状态。"""
        values = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if error_message is not None:
            values["error_message"] = error_message
        elif status in {ProcessingStatus.PROCESSING, ProcessingStatus.COMPLETED}:
            values["error_message"] = None
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at

        await self.db.execute(
            update(DocumentProcessingTask)
            .where(DocumentProcessingTask.id == task_id)
            .values(**values)
        )
        await self.db.commit()

    async def _update_processed_chunks(
        self, task_id: uuid.UUID, processed_chunks: int
    ) -> None:
        """更新已处理切片数（轻量级，不 commit 主事务）。"""
        await self.db.execute(
            update(DocumentProcessingTask)
            .where(DocumentProcessingTask.id == task_id)
            .values(processed_chunks=processed_chunks)
        )
        await self.db.commit()

    async def delete_document_chunks(self, document_id: uuid.UUID) -> None:
        """删除文档的所有切片。"""
        await self._delete_document_chunks_no_commit(document_id)
        await self.db.commit()


async def process_document_background(document_id: uuid.UUID, db: AsyncSession) -> None:
    """后台处理文档（用于异步任务）。"""
    service = DocumentProcessingService(db)
    await service.process_document(document_id)
