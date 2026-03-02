"""RAG 文档处理服务"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import (
    DocumentChunk,
    DocumentProcessingTask,
    ProcessingStatus,
    SpaceDocument,
)
from rag.chunking import Chunk, get_chunker
from rag.embedding import EmbeddingClient

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentProcessingService:
    """文档处理服务 - 负责切片和向量化流程"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.embedding_client = EmbeddingClient()

    async def create_processing_task(
        self, document_id: uuid.UUID
    ) -> DocumentProcessingTask:
        """
        为文档创建处理任务

        Args:
            document_id: 文档 ID

        Returns:
            处理任务对象
        """
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
        """获取文档的处理任务"""
        result = await self.db.execute(
            select(DocumentProcessingTask).where(
                DocumentProcessingTask.document_id == document_id
            )
        )
        return result.scalar_one_or_none()

    async def process_document(self, document_id: uuid.UUID) -> None:
        """
        处理文档：切片 + 向量化 + 存储

        Args:
            document_id: 文档 ID
        """
        # 获取文档信息
        result = await self.db.execute(
            select(SpaceDocument).where(SpaceDocument.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            logger.error("文档不存在: %s", document_id)
            return

        # 获取或创建处理任务
        task = await self.get_processing_task(document_id)
        if not task:
            task = await self.create_processing_task(document_id)

        # 更新任务状态为处理中
        await self._update_task_status(
            task.id, ProcessingStatus.PROCESSING, started_at=datetime.utcnow()
        )

        try:
            # 1. 读取文档内容
            logger.info("开始处理文档: %s (%s)", document.title, document.mime_type)
            content = await self._read_document_content(document)

            if not content:
                raise ValueError("文档内容为空")

            # 2. 切片
            logger.info("开始切片...")
            chunker = get_chunker(document.mime_type)
            chunks = chunker.chunk(content, filename=document.original_filename)
            logger.info("切片完成，共 %d 个切片", len(chunks))

            if not chunks:
                raise ValueError("切片结果为空")

            # 2.5 VLM 后处理（OCR + 图片描述）
            if settings.vlm_processing_enabled:
                try:
                    chunks = await chunker.enrich(
                        chunks, content, filename=document.original_filename
                    )
                    logger.info("VLM 后处理完成，当前共 %d 个切片", len(chunks))
                except Exception as e:
                    logger.warning("VLM 后处理失败，继续使用原始切片: %s", e)

            # 3. 生成 embedding
            logger.info("开始生成 embedding...")
            chunk_texts = [chunk.content for chunk in chunks]
            embedding_result = await self.embedding_client.embed_batch(chunk_texts)
            logger.info(
                "Embedding 生成完成，使用 %d tokens", embedding_result.token_count
            )

            # 4. 存储切片和向量
            logger.info("存储切片到数据库...")
            await self._store_chunks(
                document_id=document.id,
                space_id=document.space_id,
                chunks=chunks,
                embeddings=embedding_result.embeddings,
            )

            # 5. 更新任务状态为完成
            await self._update_task_status(
                task.id,
                ProcessingStatus.COMPLETED,
                chunk_count=len(chunks),
                completed_at=datetime.utcnow(),
            )
            logger.info("文档处理完成: %s", document.title)

        except Exception as e:
            logger.error("文档处理失败: %s - %s", document_id, str(e), exc_info=True)
            await self._update_task_status(
                task.id,
                ProcessingStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.utcnow(),
            )
            raise

    async def _read_document_content(self, document: SpaceDocument) -> bytes:
        """读取文档内容"""
        # 从 URL 提取文件路径
        # URL 格式: /uploads/documents/{filename}
        relative_path = document.url.lstrip("/")
        file_path = Path(settings.upload_dir).parent / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"文档文件不存在: {file_path}")

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def _store_chunks(
        self,
        document_id: uuid.UUID,
        space_id: uuid.UUID,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """存储切片和向量到数据库"""
        # 先删除该文档的旧切片（如果有）
        await self.db.execute(
            DocumentChunk.__table__.delete().where(
                DocumentChunk.document_id == document_id
            )
        )

        # 批量插入新切片
        for chunk, embedding in zip(chunks, embeddings):
            # 使用原生 SQL 插入，因为 SQLAlchemy 对 pgvector 的支持需要特殊处理
            await self.db.execute(
                DocumentChunk.__table__.insert().values(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    space_id=space_id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    chunk_metadata=chunk.metadata,
                    embedding=embedding,
                )
            )

        await self.db.commit()

    async def _update_task_status(
        self,
        task_id: uuid.UUID,
        status: ProcessingStatus,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """更新任务状态"""
        values = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if error_message is not None:
            values["error_message"] = error_message
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

    async def delete_document_chunks(self, document_id: uuid.UUID) -> None:
        """删除文档的所有切片"""
        await self.db.execute(
            DocumentChunk.__table__.delete().where(
                DocumentChunk.document_id == document_id
            )
        )
        await self.db.commit()


async def process_document_background(document_id: uuid.UUID, db: AsyncSession) -> None:
    """
    后台处理文档（用于异步任务）

    Args:
        document_id: 文档 ID
        db: 数据库会话
    """
    service = DocumentProcessingService(db)
    await service.process_document(document_id)
