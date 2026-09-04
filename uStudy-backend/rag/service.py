"""RAG document processing service (plaintext - no embedding)."""

from __future__ import annotations

import asyncio
import io
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import (
    DocumentImage,
    DocumentProcessingTask,
    DocumentText,
    DocumentType,
    ProcessingStatus,
    SpaceDocument,
)
from rag.chunking import get_chunker
from rag.parsing import NormalizedDocument, normalize_legacy_document, resolve_document_format
from rag.retrieval.text_segmentation import segment_for_search
from rag.utils import has_visual_content
from usage.metering import UsageContext
from usage.models import UsageType

logger = logging.getLogger(__name__)
settings = get_settings()
PDF_MIME_TYPE = "application/pdf"
PDF_SCAN_TEXT_THRESHOLD = 20
PDF_SCAN_SAMPLE_PAGES = 10


def should_run_visual_enhancement(mime_type: str | None) -> bool:
    """Return whether upload-time VLM image enhancement should run."""
    return bool(settings.vlm_processing_enabled and (mime_type or "").lower() != PDF_MIME_TYPE)


@dataclass(frozen=True)
class PDFScanDetection:
    """Lightweight result for deciding whether a PDF should be handled page-by-page."""

    is_scanned: bool
    page_count: int
    sampled_pages: int
    scanned_like_pages: int
    textful_pages: int


def detect_scanned_pdf(content: bytes) -> PDFScanDetection:
    """
    Detect image-only / scanned PDFs before text processing.

    A scanned-like page is "very little extractable text + embedded image".  The
    whole document is treated as scanned only when that pattern dominates the
    sampled pages, or when there are no textful pages at all.  This avoids
    classifying ordinary PDFs with a single image cover as scanned.
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF (fitz) 未安装，无法检测 PDF 是否为扫描件")
        return PDFScanDetection(False, 0, 0, 0, 0)

    try:
        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
    except Exception as exc:
        logger.warning("PDF 打开失败，跳过扫描件检测: %s", exc)
        return PDFScanDetection(False, 0, 0, 0, 0)

    try:
        page_count = len(doc)
        if page_count == 0:
            return PDFScanDetection(False, 0, 0, 0, 0)

        sample_count = min(page_count, PDF_SCAN_SAMPLE_PAGES)
        if sample_count == page_count:
            sample_indexes = list(range(page_count))
        else:
            step = (page_count - 1) / (sample_count - 1)
            sample_indexes = sorted({round(i * step) for i in range(sample_count)})

        scanned_like_pages = 0
        textful_pages = 0
        for page_index in sample_indexes:
            page = doc[page_index]
            text_len = len(page.get_text("text").strip())
            has_images = bool(page.get_images(full=False))

            if text_len >= PDF_SCAN_TEXT_THRESHOLD:
                textful_pages += 1
            if text_len < PDF_SCAN_TEXT_THRESHOLD and has_images:
                scanned_like_pages += 1

        sampled_pages = len(sample_indexes)
        scanned_ratio = scanned_like_pages / sampled_pages if sampled_pages else 0
        is_scanned = scanned_like_pages > 0 and (
            scanned_ratio >= 0.5 or textful_pages == 0
        )
        return PDFScanDetection(
            is_scanned=is_scanned,
            page_count=page_count,
            sampled_pages=sampled_pages,
            scanned_like_pages=scanned_like_pages,
            textful_pages=textful_pages,
        )
    finally:
        doc.close()


class DocumentProcessingService:
    """文档处理服务 - 负责格式解析、切片与全文存储流程。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
        """处理文档：解析全文并写入 document_texts 表。"""
        await self._process_document_inner(document_id)

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
            task.id, ProcessingStatus.PROCESSING, started_at=datetime.utcnow(), error_message=None
        )

        if document.doc_type == DocumentType.LINK:
            await self._process_link_document(document, task)
            return

        try:
            content = await self._read_document_content(document)
            if not content:
                raise ValueError("文档内容为空")

            normalized = await self._resolve_and_normalize_document(document, content)
            document.mime_type = normalized.resolved_format.mime_type

            if document.mime_type == PDF_MIME_TYPE:
                scan = await asyncio.to_thread(detect_scanned_pdf, normalized.content)
                if scan.is_scanned:
                    await self._delete_document_text(document.id)
                    await self._write_document_text(
                        document,
                        self._build_scanned_pdf_placeholder(document, scan),
                    )
                    await self.db.commit()

                    logger.info(
                        "扫描件 PDF 已跳过文本/OCR 处理: %s (pages=%d, scanned_like=%d/%d)",
                        document.title,
                        scan.page_count,
                        scan.scanned_like_pages,
                        scan.sampled_pages,
                    )
                    await self._update_task_status(
                        task.id,
                        ProcessingStatus.COMPLETED,
                        chunk_count=0,
                        completed_at=datetime.utcnow(),
                    )
                    return

            chunker = get_chunker(normalized.resolved_format.mime_type)
            chunks = list(chunker.chunk(normalized.content, normalized.filename))
            full_text = "\n\n".join(chunk.content for chunk in chunks if chunk.content.strip())
            if not full_text.strip():
                raise ValueError("提取的文本内容为空")

            await self._delete_document_text(document.id)
            doc_text = await self._write_document_text(document, full_text)
            await self.db.commit()

            logger.info("文档全文写入完成: %s (%d chars)", document.title, len(full_text))

            if should_run_visual_enhancement(document.mime_type) and has_visual_content(
                normalized.content,
                document.mime_type,
            ):
                await self._extract_and_store_images(document, content, normalized.resolved_format.mime_type, doc_text)
                await self.db.commit()

            await self._update_task_status(
                task.id,
                ProcessingStatus.COMPLETED,
                chunk_count=1,
                completed_at=datetime.utcnow(),
            )

        except Exception as exc:
            await self.db.rollback()
            logger.error("文档处理失败: %s - %s", document_id, exc, exc_info=True)
            await self._update_task_status(
                task.id,
                ProcessingStatus.FAILED,
                error_message=str(exc),
                completed_at=datetime.utcnow(),
            )
            raise

    async def _process_link_document(
        self,
        document: SpaceDocument,
        task: DocumentProcessingTask,
    ) -> None:
        """Process LINK-type document: fetch URL content, write full text."""
        from rag.url_fetcher import URLContentFetcher, URLFetchError

        try:
            fetcher = URLContentFetcher()
            result = await fetcher.fetch(document.url)
            full_text = result.content
            if not full_text.strip():
                raise ValueError("链接内容为空")

            if result.title and document.title in (document.url, ""):
                document.title = result.title

            await self._delete_document_text(document.id)
            await self._write_document_text(document, full_text)
            await self.db.commit()

            await self._update_task_status(
                task.id, ProcessingStatus.COMPLETED, chunk_count=1, completed_at=datetime.utcnow()
            )
            logger.info("链接文档处理完成: %s (%d chars)", document.title, len(full_text))

        except URLFetchError as exc:
            await self.db.rollback()
            await self._update_task_status(
                task.id, ProcessingStatus.FAILED, error_message=str(exc), completed_at=datetime.utcnow()
            )
            raise
        except Exception as exc:
            await self.db.rollback()
            await self._update_task_status(
                task.id, ProcessingStatus.FAILED, error_message=str(exc), completed_at=datetime.utcnow()
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

    async def _read_document_content(self, document: SpaceDocument) -> bytes:
        """读取文档内容。"""
        relative_path = document.url.lstrip("/")
        file_path = Path(settings.upload_dir).parent / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"文档文件不存在: {file_path}")

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

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

    async def _write_document_text(self, document: SpaceDocument, full_text: str) -> DocumentText:
        """Write full text to document_texts and update tsvector."""
        from sqlalchemy import text as sa_text
        word_count = len(full_text.split())
        doc_text = DocumentText(
            document_id=document.id,
            space_id=document.space_id,
            content=full_text,
            word_count=word_count,
        )
        self.db.add(doc_text)
        await self.db.flush()

        tokens = segment_for_search(full_text)
        token_str = " ".join(tokens.split()[:500]) if tokens else ""
        await self.db.execute(
            sa_text(
                "UPDATE document_texts SET content_tsv = to_tsvector('simple', :tokens) WHERE id = :id"
            ),
            {"tokens": token_str, "id": str(doc_text.id)},
        )
        return doc_text

    def _build_scanned_pdf_placeholder(
        self,
        document: SpaceDocument,
        scan: PDFScanDetection,
    ) -> str:
        filename = document.original_filename or document.title
        return (
            f"《{filename}》是扫描件 PDF，共 {scan.page_count} 页。"
            "系统已跳过自动 OCR、文本切片和图片描述处理。"
            "如需阅读内容，请先使用 list_documents 获取 document_id，"
            "再使用 view_document_page 按页查看 PDF 页面图片，"
            "根据页面内容决定下一步继续查看哪一页。"
        )

    async def _delete_document_text(self, document_id: uuid.UUID) -> None:
        """Remove existing document_texts entry (images cascade)."""
        from sqlalchemy import delete as sa_delete
        await self.db.execute(
            sa_delete(DocumentText).where(DocumentText.document_id == document_id)
        )

    async def _extract_and_store_images(
        self,
        document: SpaceDocument,
        content: bytes,
        mime_type: str,
        doc_text: DocumentText,
    ) -> None:
        """Extract images, run VLM, store files + DB rows, update content placeholders."""
        from rag.image_extractor import ImageExtractor
        from rag.vlm_processor import VLMProcessor
        from sqlalchemy import text as sa_text

        extractor = ImageExtractor()
        raw_images = extractor.extract(content, mime_type)
        if not raw_images:
            return

        vlm = VLMProcessor(
            usage_context=UsageContext(
                user_id=document.creator_user_id,
                usage_type=UsageType.AGENT_LLM,
                source_module="rag",
                source_operation="document_image_vlm",
                billable=bool(document.creator_user_id),
                space_id=document.space_id,
                metadata={"document_id": str(document.id)},
            )
        )
        upload_dir = Path(settings.upload_dir) / "images" / str(document.space_id) / str(document.id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        updated_content = doc_text.content

        for img in raw_images:
            img_id = uuid.uuid4()
            file_path = upload_dir / f"{img_id}.{img.ext}"

            async with aiofiles.open(file_path, "wb") as f:
                await f.write(img.image_bytes)

            description: Optional[str] = None
            try:
                description = await vlm.describe_image(img.image_bytes, context="")
            except Exception as exc:
                logger.warning("VLM 描述失败，跳过: %s", exc)

            db_image = DocumentImage(
                id=img_id,
                document_id=document.id,
                space_id=document.space_id,
                document_text_id=doc_text.id,
                page_num=img.page_num,
                image_index=img.image_index,
                file_path=str(file_path),
                vlm_description=description,
            )
            self.db.add(db_image)

            placeholder = f"[IMAGE:{img_id}]"
            desc_text = f"\n{description}\n" if description else ""
            updated_content += f"\n\n{placeholder}{desc_text}"

        doc_text.content = updated_content
        doc_text.word_count = len(updated_content.split())

        tokens = segment_for_search(updated_content)
        token_str = " ".join(tokens.split()[:500]) if tokens else ""
        await self.db.execute(
            sa_text(
                "UPDATE document_texts SET content = :content, content_tsv = to_tsvector('simple', :tokens), word_count = :wc WHERE id = :id"
            ),
            {
                "content": updated_content,
                "tokens": token_str,
                "wc": doc_text.word_count,
                "id": str(doc_text.id),
            },
        )

    async def delete_document_chunks(self, document_id: uuid.UUID) -> None:
        """删除文档的全文存储记录。"""
        await self._delete_document_text(document_id)
        await self.db.commit()


async def process_document_background(document_id: uuid.UUID, db: AsyncSession) -> None:
    """后台处理文档（用于异步任务）。"""
    service = DocumentProcessingService(db)
    await service.process_document(document_id)
