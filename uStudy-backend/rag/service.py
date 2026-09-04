"""Document processing and atomic Agentic-PDF index publication."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import shutil
import threading
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_scoped_session
from db.models import (
    DocumentChunk,
    DocumentImage,
    DocumentProcessingTask,
    DocumentText,
    DocumentType,
    PdfIndexAgentCall,
    PdfPageAsset,
    PdfVisualIndex,
    ProcessingStatus,
    SpaceDocument,
)
from rag.chunking import get_chunker
from rag.parsing import (
    NormalizedDocument,
    normalize_legacy_document,
    resolve_document_format,
)
from rag.retrieval.text_segmentation import segment_for_search
from rag.utils import has_visual_content
from usage.metering import UsageContext
from usage.models import UsageType

if TYPE_CHECKING:
    from rag.pdf_agentic import RenderManifest, TocAgentResult
    from rag.tasks import ProcessingLease

logger = logging.getLogger(__name__)
settings = get_settings()
PDF_MIME_TYPE = "application/pdf"
PDF_SCAN_TEXT_THRESHOLD = 20
PDF_SCAN_SAMPLE_PAGES = 10
PDF_RENDERER_VERSION = "agentic-pdf-v1"


@dataclass(frozen=True)
class ProcessingOutcome:
    chunk_count: int
    warning_code: str | None = None


class RetryableOutlineError(RuntimeError):
    retryable = True
    error_code = "pdf_outline_temporary_failure"


def should_run_visual_enhancement(mime_type: str | None) -> bool:
    """PDF visuals are handled by the dedicated Agentic pipeline."""

    return bool(
        settings.vlm_processing_enabled and (mime_type or "").lower() != PDF_MIME_TYPE
    )


@dataclass(frozen=True)
class PDFScanDetection:
    """Compatibility metadata; it no longer controls PDF routing."""

    is_scanned: bool
    page_count: int
    sampled_pages: int
    scanned_like_pages: int
    textful_pages: int


def detect_scanned_pdf(content: bytes) -> PDFScanDetection:
    """Detect scan-like pages for diagnostics without changing the route."""

    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF (fitz) 未安装，无法检测 PDF 是否为扫描件")
        return PDFScanDetection(False, 0, 0, 0, 0)

    try:
        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - PyMuPDF exposes heterogeneous errors
        logger.warning("PDF 打开失败，跳过扫描件检测: %s", exc)
        return PDFScanDetection(False, 0, 0, 0, 0)

    try:
        page_count = len(doc)
        if page_count == 0:
            return PDFScanDetection(False, 0, 0, 0, 0)
        sample_count = min(page_count, PDF_SCAN_SAMPLE_PAGES)
        if sample_count == page_count:
            sample_indexes = list(range(page_count))
        elif sample_count == 1:
            sample_indexes = [0]
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
        ratio = scanned_like_pages / sampled_pages if sampled_pages else 0
        return PDFScanDetection(
            is_scanned=scanned_like_pages > 0 and (ratio >= 0.5 or textful_pages == 0),
            page_count=page_count,
            sampled_pages=sampled_pages,
            scanned_like_pages=scanned_like_pages,
            textful_pages=textful_pages,
        )
    finally:
        doc.close()


def _source_file_path(document: SpaceDocument) -> Path:
    uploads_root = Path(settings.upload_dir).resolve()
    url = str(document.url or "")
    if url.startswith("/uploads/"):
        candidate = (uploads_root / url[len("/uploads/") :]).resolve()
    else:
        candidate = (Path(settings.upload_dir).parent / url.lstrip("/")).resolve()
    if not candidate.is_relative_to(uploads_root):
        raise ValueError("文档文件路径无效")
    if not candidate.is_file():
        raise FileNotFoundError("文档源文件不存在")
    return candidate


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class DocumentProcessingService:
    """Process legacy documents and publish versioned PDF visual indexes."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def process_document(
        self,
        document_id: uuid.UUID,
        *,
        lease: ProcessingLease | None = None,
    ) -> ProcessingOutcome:
        document = await self.db.get(SpaceDocument, document_id)
        if document is None:
            raise ValueError("文档不存在")

        if document.doc_type == DocumentType.LINK:
            return await self._process_link_document(document, lease)

        is_pdf = (document.mime_type or "").lower() == PDF_MIME_TYPE or str(
            document.original_filename or document.url or ""
        ).lower().endswith(".pdf")
        if is_pdf and settings.pdf_agentic_enabled:
            if lease is None:
                raise RuntimeError("Agentic PDF processing requires a durable lease")
            return await self._process_agentic_pdf(document, lease)
        return await self._process_standard_document(document, lease)

    async def _process_link_document(
        self,
        document: SpaceDocument,
        lease: ProcessingLease | None,
    ) -> ProcessingOutcome:
        from rag.url_fetcher import URLContentFetcher

        if lease is not None:
            await lease.heartbeat(stage="extracting")
        result = await URLContentFetcher().fetch(document.url)
        full_text = result.content
        if not full_text.strip():
            raise ValueError("链接内容为空")
        if result.title and document.title in (document.url, ""):
            document.title = result.title
        await self._delete_document_text(document.id)
        await self._delete_legacy_chunks(document.id)
        await self._write_document_text(document, full_text)
        await self.db.commit()
        return ProcessingOutcome(chunk_count=1)

    async def _process_standard_document(
        self,
        document: SpaceDocument,
        lease: ProcessingLease | None,
    ) -> ProcessingOutcome:
        if lease is not None:
            await lease.heartbeat(stage="extracting")
        content = await self._read_document_content(document)
        if not content:
            raise ValueError("文档内容为空")
        normalized = await self._resolve_and_normalize_document(document, content)
        document.mime_type = normalized.resolved_format.mime_type
        chunker = get_chunker(normalized.resolved_format.mime_type)
        chunks = list(chunker.chunk(normalized.content, normalized.filename))
        full_text = "\n\n".join(
            chunk.content for chunk in chunks if chunk.content.strip()
        )
        if not full_text.strip():
            raise ValueError("提取的文本内容为空")
        await self._delete_document_text(document.id)
        await self._delete_legacy_chunks(document.id)
        doc_text = await self._write_document_text(document, full_text)
        await self.db.commit()
        if should_run_visual_enhancement(document.mime_type) and has_visual_content(
            normalized.content, document.mime_type
        ):
            await self._extract_and_store_images(
                document, content, normalized.resolved_format.mime_type, doc_text
            )
            await self.db.commit()
        return ProcessingOutcome(chunk_count=1)

    async def _process_agentic_pdf(
        self,
        document: SpaceDocument,
        lease: ProcessingLease,
    ) -> ProcessingOutcome:
        from agents.llm import LLMClient
        from rag.pdf_agentic import (
            PdfVisualIndexError,
            TocAgentResult,
            TocIndexAgent,
            load_render_manifest,
            preflight_pdf,
            render_pdf_visual_index,
            write_outline_artifacts,
        )

        source_path = _source_file_path(document)
        source_sha256 = await asyncio.to_thread(_sha256_file, source_path)
        preflight = await asyncio.to_thread(
            preflight_pdf, source_path, max_pages=settings.pdf_max_pages
        )
        await lease.heartbeat(stage="preflight", page_count=preflight.page_count)
        visual_index = await self._get_or_create_visual_index(
            document=document,
            lease=lease,
            source_sha256=source_sha256,
            page_count=preflight.page_count,
        )
        if visual_index.state == "published" and visual_index.is_current:
            count = await self._count_index_chunks(visual_index.id)
            return ProcessingOutcome(
                chunk_count=count,
                warning_code=_outline_warning(visual_index.outline_status),
            )

        private_root = Path(settings.pdf_private_dir).resolve()
        document_root = private_root / str(document.space_id) / str(document.id)
        staging_root = document_root / (
            f".staging-{lease.generation:06d}-{lease.lease_token.hex}"
        )
        final_root = document_root / f"v{lease.generation:06d}"
        document_root.mkdir(parents=True, exist_ok=True)

        manifest: RenderManifest | None = None
        working_root: Path | None = None
        invalid_staging: list[Path] = []
        reusable_staging = sorted(
            document_root.glob(f".staging-{lease.generation:06d}-*"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        # Include the original pre-token staging name for safe recovery from a
        # deployment that was interrupted while upgrading this pipeline.
        legacy_staging = document_root / f".staging-{lease.generation:06d}"
        for candidate in (final_root, *reusable_staging, legacy_staging):
            try:
                manifest = await asyncio.to_thread(load_render_manifest, candidate)
                working_root = candidate
                break
            except (FileNotFoundError, ValueError, PdfVisualIndexError):
                if candidate.name.startswith(".staging-") and candidate.exists():
                    invalid_staging.append(candidate)
                continue

        for invalid in invalid_staging:
            resolved_invalid = invalid.resolve()
            if resolved_invalid.is_relative_to(document_root.resolve()):
                await asyncio.to_thread(shutil.rmtree, resolved_invalid)

        if manifest is None or working_root is None:
            if final_root.exists():
                resolved_final = final_root.resolve()
                if resolved_final.is_relative_to(document_root.resolve()):
                    await asyncio.to_thread(shutil.rmtree, resolved_final)
            if staging_root.exists():
                resolved_staging = staging_root.resolve()
                if resolved_staging.is_relative_to(document_root.resolve()):
                    await asyncio.to_thread(shutil.rmtree, resolved_staging)
            progress = {"done": 0, "total": preflight.page_count}
            cancel_event = threading.Event()

            def on_progress(done: int, total: int) -> None:
                progress["done"] = done
                progress["total"] = total

            render_call = asyncio.to_thread(
                render_pdf_visual_index,
                source_path,
                staging_root,
                max_pages=settings.pdf_max_pages,
                render_dpi=settings.pdf_render_dpi,
                render_max_pixels=settings.pdf_render_max_pixels,
                webp_quality=settings.pdf_webp_quality,
                max_image_bytes=settings.pdf_max_image_bytes,
                lod_max_side=settings.pdf_lod_max_side,
                max_derived_bytes=settings.pdf_max_derived_bytes,
                min_free_disk_bytes=settings.pdf_min_free_disk_bytes,
                on_progress=on_progress,
                should_cancel=cancel_event.is_set,
            )
            manifest = await self._run_with_heartbeat(
                lease,
                stage="rendering",
                operation=render_call,
                progress=progress,
                cancel_event=cancel_event,
            )
            working_root = staging_root

        await lease.heartbeat(
            stage="toc_locating",
            page_count=manifest.page_count,
            processed_pages=manifest.page_count,
            asset_count=manifest.asset_count,
        )

        usage_context = UsageContext(
            user_id=document.creator_user_id,
            usage_type=UsageType.AGENT_LLM,
            source_module="rag",
            source_operation="pdf_toc_indexing",
            billable=bool(document.creator_user_id),
            space_id=document.space_id,
            metadata={
                "document_id": str(document.id),
                "generation": lease.generation,
                "visual_index_id": str(visual_index.id),
            },
        )
        llm: LLMClient | None = None

        async def completion(messages: list[dict[str, Any]], call_key: str) -> str:
            nonlocal llm
            if llm is None:
                # Lazy construction lets the bounded Agent convert missing or
                # temporarily unavailable VLM configuration into its degraded
                # result instead of losing the already-rendered page assets.
                llm = LLMClient(
                    model_override=settings.vlm_model,
                    timeout_seconds=90,
                    usage_context=usage_context,
                )
            return await llm.complete(
                messages,  # type: ignore[arg-type]
                temperature=0.1,
                max_tokens=4096,
                enable_thinking=False,
                idempotency_key=call_key,
            )

        async def checkpoint_get(call_key: str) -> str | None:
            return await self._get_agent_checkpoint(visual_index.id, call_key)

        async def checkpoint_put(call_key: str, response: str) -> None:
            await self._put_agent_checkpoint(
                visual_index.id, call_key, response, model=settings.vlm_model
            )

        async def cancelled() -> bool:
            from rag.tasks import LeaseLostError

            try:
                await lease.assert_owned()
                return False
            except LeaseLostError:
                return True

        agent = TocIndexAgent(
            completion=completion,
            checkpoint_get=checkpoint_get,
            checkpoint_put=checkpoint_put,
            model=settings.vlm_model,
            usage_context=usage_context,
            toc_scan_max_pages=settings.pdf_toc_scan_max_pages,
            toc_max_pages=settings.pdf_toc_max_pages,
            toc_agent_max_rounds=settings.pdf_toc_agent_max_rounds,
            max_images_per_call=settings.rag_media_max_images,
            should_cancel=cancelled,
        )
        toc_result = await agent.run(
            str(document.id), lease.generation, manifest, working_root
        )
        if (
            toc_result.status == "failed"
            and lease.attempt < settings.pdf_processing_max_attempts
        ):
            raise RetryableOutlineError(
                toc_result.error_detail or "目录视觉识别暂时失败"
            )
        if toc_result.status == "failed":
            toc_result = TocAgentResult(
                status="failed",
                entries=(),
                page_offset=None,
                error_code=toc_result.error_code or "toc_vlm_failed",
            )

        await lease.heartbeat(stage="publishing")
        _, outline_markdown = await asyncio.to_thread(
            write_outline_artifacts,
            working_root,
            toc_result.entries,
            toc_physical_page_start=toc_result.toc_physical_page_start,
            toc_physical_page_end=toc_result.toc_physical_page_end,
            page_offset=toc_result.page_offset,
        )
        if await asyncio.to_thread(_sha256_file, source_path) != source_sha256:
            raise PdfVisualIndexError(
                "pdf_source_changed",
                "PDF 源文件在处理期间发生变化",
                retryable=False,
            )

        try:
            chunk_count = await self._publish_pdf_index(
                document=document,
                lease=lease,
                visual_index_id=visual_index.id,
                source_sha256=source_sha256,
                manifest=manifest,
                toc_result=toc_result,
                working_root=working_root,
                final_root=final_root,
                outline_markdown=outline_markdown,
            )
        except Exception:
            await self.db.rollback()
            raise
        return ProcessingOutcome(
            chunk_count=chunk_count,
            warning_code=_outline_warning(toc_result.status),
        )

    async def _run_with_heartbeat(
        self,
        lease: ProcessingLease,
        *,
        stage: str,
        operation: Any,
        progress: dict[str, int],
        cancel_event: threading.Event,
    ) -> Any:
        heartbeat_error: BaseException | None = None
        stopped = asyncio.Event()

        async def pump() -> None:
            nonlocal heartbeat_error
            interval = max(5, settings.pdf_processing_lease_seconds // 3)
            while not stopped.is_set():
                try:
                    await asyncio.wait_for(stopped.wait(), timeout=interval)
                    return
                except asyncio.TimeoutError:
                    pass
                try:
                    await lease.heartbeat(
                        stage=stage,
                        page_count=progress.get("total"),
                        processed_pages=progress.get("done"),
                    )
                except Exception as exc:  # noqa: BLE001 - any heartbeat failure fences the worker
                    heartbeat_error = exc
                    cancel_event.set()
                    return

        await lease.heartbeat(
            stage=stage,
            page_count=progress.get("total"),
            processed_pages=progress.get("done"),
        )
        pump_task = asyncio.create_task(pump(), name=f"pdf_lease_{lease.task_id}")
        try:
            result = await operation
        finally:
            stopped.set()
            pump_task.cancel()
            with suppress(asyncio.CancelledError):
                await pump_task
        if heartbeat_error is not None:
            raise heartbeat_error
        await lease.heartbeat(
            stage=stage,
            page_count=progress.get("total"),
            processed_pages=progress.get("done"),
        )
        return result

    async def _get_or_create_visual_index(
        self,
        *,
        document: SpaceDocument,
        lease: ProcessingLease,
        source_sha256: str,
        page_count: int,
    ) -> PdfVisualIndex:
        visual_index = await self.db.scalar(
            select(PdfVisualIndex).where(
                PdfVisualIndex.document_id == document.id,
                PdfVisualIndex.generation == lease.generation,
            )
        )
        if visual_index is None:
            visual_index = PdfVisualIndex(
                document_id=document.id,
                space_id=document.space_id,
                generation=lease.generation,
                state="staging",
                is_current=False,
                source_sha256=source_sha256,
                page_count=page_count,
                outline_status="pending",
                outline_entries=[],
                derived_bytes=0,
                renderer_version=PDF_RENDERER_VERSION,
            )
            self.db.add(visual_index)
            await self.db.commit()
            await self.db.refresh(visual_index)
        elif visual_index.source_sha256 != source_sha256:
            raise ValueError("处理期间 PDF 源文件发生变化")
        return visual_index

    async def _get_agent_checkpoint(
        self, visual_index_id: uuid.UUID, call_key: str
    ) -> str | None:
        async with get_scoped_session() as db:
            call = await db.scalar(
                select(PdfIndexAgentCall).where(
                    PdfIndexAgentCall.index_id == visual_index_id,
                    PdfIndexAgentCall.call_key == call_key,
                    PdfIndexAgentCall.status == "completed",
                )
            )
            return call.response_text if call is not None else None

    async def _put_agent_checkpoint(
        self,
        visual_index_id: uuid.UUID,
        call_key: str,
        response: str,
        *,
        model: str,
    ) -> None:
        parts = call_key.split(":", 6)
        operation = parts[3] if len(parts) > 3 else "unknown"
        try:
            round_index = int(parts[4])
        except (IndexError, ValueError):
            round_index = 0
        input_sha256 = (
            parts[5]
            if len(parts) > 5
            else hashlib.sha256(call_key.encode("utf-8")).hexdigest()
        )
        async with get_scoped_session() as db:
            existing = await db.scalar(
                select(PdfIndexAgentCall).where(PdfIndexAgentCall.call_key == call_key)
            )
            if existing is None:
                db.add(
                    PdfIndexAgentCall(
                        index_id=visual_index_id,
                        call_key=call_key,
                        operation=operation,
                        round_index=round_index,
                        input_sha256=input_sha256,
                        model=model,
                        status="completed",
                        response_text=response,
                    )
                )
            else:
                existing.status = "completed"
                existing.response_text = response
                existing.error = None
            try:
                await db.commit()
            except IntegrityError:
                # A reclaimed worker may finish the same stable call just as
                # its replacement does.  First durable valid response wins.
                await db.rollback()
                winner = await db.scalar(
                    select(PdfIndexAgentCall).where(
                        PdfIndexAgentCall.call_key == call_key
                    )
                )
                if winner is None:
                    raise

    async def _publish_pdf_index(
        self,
        *,
        document: SpaceDocument,
        lease: ProcessingLease,
        visual_index_id: uuid.UUID,
        source_sha256: str,
        manifest: RenderManifest,
        toc_result: TocAgentResult,
        working_root: Path | None = None,
        final_root: Path,
        outline_markdown: Path,
    ) -> int:
        from rag.pdf_agentic import PdfVisualIndexError, iter_native_page_text
        from rag.tasks import LeaseLostError

        task_stmt = select(DocumentProcessingTask).where(
            DocumentProcessingTask.id == lease.task_id,
            DocumentProcessingTask.document_id == document.id,
            DocumentProcessingTask.generation == lease.generation,
            DocumentProcessingTask.lease_token == lease.lease_token,
            DocumentProcessingTask.status == ProcessingStatus.PROCESSING,
            DocumentProcessingTask.lease_expires_at > datetime.now(timezone.utc),
        )
        if self.db.get_bind().dialect.name == "postgresql":
            task_stmt = task_stmt.with_for_update()
        if await self.db.scalar(task_stmt) is None:
            raise LeaseLostError("lease lost before PDF index publication")

        visual_index = await self.db.get(PdfVisualIndex, visual_index_id)
        if visual_index is None or visual_index.generation != lease.generation:
            raise LeaseLostError("PDF visual index generation is no longer current")

        source_root = (working_root or final_root).resolve()
        resolved_final = final_root.resolve()
        private_root = Path(settings.pdf_private_dir).resolve()
        expected_document_root = (
            private_root / str(document.space_id) / str(document.id)
        ).resolve()
        expected_final = (expected_document_root / f"v{lease.generation:06d}").resolve()
        if not source_root.is_relative_to(
            private_root
        ) or not resolved_final.is_relative_to(private_root):
            raise ValueError("PDF 索引发布路径无效")
        if (
            not source_root.is_relative_to(expected_document_root)
            or resolved_final != expected_final
        ):
            raise ValueError("PDF 索引发布范围无效")
        if source_root != resolved_final:
            if resolved_final.exists():
                await asyncio.to_thread(shutil.rmtree, resolved_final)
            await asyncio.to_thread(os.replace, source_root, resolved_final)
        final_root = resolved_final
        outline_markdown = final_root / outline_markdown.name

        current_indexes = list(
            (
                await self.db.scalars(
                    select(PdfVisualIndex).where(
                        PdfVisualIndex.document_id == document.id,
                        PdfVisualIndex.is_current.is_(True),
                        PdfVisualIndex.id != visual_index.id,
                    )
                )
            ).all()
        )
        for current in current_indexes:
            current.is_current = False
            current.state = "superseded"
        await self.db.flush()

        await self.db.execute(
            delete(PdfPageAsset).where(PdfPageAsset.index_id == visual_index.id)
        )
        await self.db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.pdf_visual_index_id == visual_index.id
            )
        )
        final_relative = final_root.resolve().relative_to(private_root).as_posix()
        for asset in manifest.assets:
            self.db.add(
                PdfPageAsset(
                    index_id=visual_index.id,
                    document_id=document.id,
                    space_id=document.space_id,
                    pages_per_image=asset.pages_per_image,
                    physical_page_start=asset.physical_page_start,
                    physical_page_end=asset.physical_page_end,
                    storage_key=f"{final_relative}/{asset.relative_path}",
                    mime_type=asset.mime_type,
                    width=asset.width,
                    height=asset.height,
                    byte_size=asset.byte_size,
                    sha256=asset.sha256,
                )
            )

        chunks: list[DocumentChunk] = []
        chunk_index = 0
        native_path = final_root / manifest.native_text_jsonl
        for page_text in iter_native_page_text(native_path):
            content = page_text.text.strip()
            if not content:
                continue
            chunks.append(
                DocumentChunk(
                    document_id=document.id,
                    space_id=document.space_id,
                    pdf_visual_index_id=visual_index.id,
                    chunk_kind="native_page",
                    physical_page_start=page_text.physical_page,
                    physical_page_end=page_text.physical_page,
                    chunk_index=chunk_index,
                    content=content,
                    token_count=max(1, len(segment_for_search(content).split())),
                    chunk_metadata={
                        "source_type": "pdf",
                        "page_number": page_text.physical_page,
                    },
                )
            )
            chunk_index += 1
        for entry in toc_result.entries:
            printed = entry.printed_page_label or "未标注"
            resolved = (
                str(entry.resolved_pdf_page)
                if entry.resolved_pdf_page is not None
                else "未解析"
            )
            content = f"{entry.title}；印刷页 {printed}；PDF 物理页 {resolved}"
            chunks.append(
                DocumentChunk(
                    document_id=document.id,
                    space_id=document.space_id,
                    pdf_visual_index_id=visual_index.id,
                    chunk_kind="outline_entry",
                    physical_page_start=entry.resolved_pdf_page,
                    physical_page_end=entry.resolved_pdf_page,
                    chunk_index=chunk_index,
                    content=content,
                    token_count=max(1, len(segment_for_search(content).split())),
                    chunk_metadata={
                        "source_type": "pdf_outline",
                        "level": entry.level,
                        "printed_page_label": entry.printed_page_label,
                        "printed_page_number": entry.printed_page_number,
                        "resolved_pdf_page": entry.resolved_pdf_page,
                        "source_physical_page": entry.source_physical_page,
                    },
                )
            )
            chunk_index += 1
        self.db.add_all(chunks)
        await self.db.flush()
        if self.db.get_bind().dialect.name == "postgresql" and chunks:
            await self.db.execute(
                text(
                    "UPDATE document_chunks SET content_tsv = "
                    "to_tsvector('simple', :tokens) WHERE id = :id"
                ),
                [
                    {
                        "id": str(chunk.id),
                        "tokens": segment_for_search(chunk.content),
                    }
                    for chunk in chunks
                ],
            )

        outline_text = await asyncio.to_thread(
            outline_markdown.read_text, encoding="utf-8"
        )
        await self._delete_document_text(document.id)
        await self._write_document_text(document, outline_text)
        outline_bytes = outline_markdown.stat().st_size
        outline_json = final_root / "outline.json"
        if outline_json.exists():
            outline_bytes += outline_json.stat().st_size
        derived_bytes = manifest.derived_bytes + outline_bytes
        if derived_bytes > settings.pdf_max_derived_bytes:
            raise PdfVisualIndexError(
                "pdf_derived_size_exceeded",
                "PDF 派生索引超过大小限制",
                retryable=False,
            )

        visual_index.state = "published"
        visual_index.is_current = True
        visual_index.source_sha256 = source_sha256
        visual_index.page_count = manifest.page_count
        visual_index.outline_status = toc_result.status
        visual_index.toc_pdf_page_start = toc_result.toc_physical_page_start
        visual_index.toc_pdf_page_end = toc_result.toc_physical_page_end
        visual_index.page_offset = toc_result.page_offset
        visual_index.outline_entries = [entry.to_dict() for entry in toc_result.entries]
        visual_index.outline_markdown_path = (
            outline_markdown.resolve().relative_to(private_root).as_posix()
        )
        visual_index.derived_bytes = derived_bytes
        visual_index.renderer_version = PDF_RENDERER_VERSION
        visual_index.published_at = datetime.now(timezone.utc)
        await self.db.commit()
        return len(chunks)

    async def _count_index_chunks(self, index_id: uuid.UUID) -> int:
        from sqlalchemy import func

        return int(
            await self.db.scalar(
                select(func.count(DocumentChunk.id)).where(
                    DocumentChunk.pdf_visual_index_id == index_id
                )
            )
            or 0
        )

    async def _resolve_and_normalize_document(
        self, document: SpaceDocument, content: bytes
    ) -> NormalizedDocument:
        resolved = await asyncio.to_thread(
            resolve_document_format,
            content,
            document.original_filename,
            document.mime_type,
        )
        return await asyncio.to_thread(
            normalize_legacy_document,
            content,
            resolved,
            document.original_filename,
        )

    async def _read_document_content(self, document: SpaceDocument) -> bytes:
        file_path = _source_file_path(document)
        async with aiofiles.open(file_path, "rb") as handle:
            return await handle.read()

    async def _write_document_text(
        self, document: SpaceDocument, full_text: str
    ) -> DocumentText:
        doc_text = DocumentText(
            document_id=document.id,
            space_id=document.space_id,
            content=full_text,
            word_count=len(full_text.split()),
        )
        self.db.add(doc_text)
        await self.db.flush()
        if self.db.get_bind().dialect.name == "postgresql":
            tokens = segment_for_search(full_text)
            token_str = " ".join(tokens.split()[:500]) if tokens else ""
            await self.db.execute(
                text(
                    "UPDATE document_texts SET content_tsv = "
                    "to_tsvector('simple', :tokens) WHERE id = :id"
                ),
                {"tokens": token_str, "id": str(doc_text.id)},
            )
        return doc_text

    async def _delete_document_text(self, document_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(DocumentText).where(DocumentText.document_id == document_id)
        )

    async def _delete_legacy_chunks(self, document_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.pdf_visual_index_id.is_(None),
            )
        )

    async def _extract_and_store_images(
        self,
        document: SpaceDocument,
        content: bytes,
        mime_type: str,
        doc_text: DocumentText,
    ) -> None:
        from rag.image_extractor import ImageExtractor
        from rag.vlm_processor import VLMProcessor

        raw_images = ImageExtractor().extract(content, mime_type)
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
        upload_dir = (
            Path(settings.upload_dir)
            / "images"
            / str(document.space_id)
            / str(document.id)
        )
        upload_dir.mkdir(parents=True, exist_ok=True)
        updated_content = doc_text.content
        for image in raw_images:
            image_id = uuid.uuid4()
            file_path = upload_dir / f"{image_id}.{image.ext}"
            async with aiofiles.open(file_path, "wb") as handle:
                await handle.write(image.image_bytes)
            description: str | None = None
            try:
                description = await vlm.describe_image(image.image_bytes, context="")
            except Exception as exc:  # noqa: BLE001 - image enhancement is best-effort
                logger.warning("VLM 描述失败，跳过: %s", exc)
            self.db.add(
                DocumentImage(
                    id=image_id,
                    document_id=document.id,
                    space_id=document.space_id,
                    document_text_id=doc_text.id,
                    page_num=image.page_num,
                    image_index=image.image_index,
                    file_path=str(file_path),
                    vlm_description=description,
                )
            )
            updated_content += f"\n\n[IMAGE:{image_id}]"
            if description:
                updated_content += f"\n{description}\n"
        doc_text.content = updated_content
        doc_text.word_count = len(updated_content.split())
        if self.db.get_bind().dialect.name == "postgresql":
            await self.db.execute(
                text(
                    "UPDATE document_texts SET content = :content, "
                    "content_tsv = to_tsvector('simple', :tokens), word_count = :wc "
                    "WHERE id = :id"
                ),
                {
                    "content": updated_content,
                    "tokens": " ".join(
                        segment_for_search(updated_content).split()[:500]
                    ),
                    "wc": doc_text.word_count,
                    "id": str(doc_text.id),
                },
            )

    async def delete_document_chunks(
        self, document_id: uuid.UUID, *, commit: bool = True
    ) -> None:
        await self._delete_document_text(document_id)
        await self.db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        if commit:
            await self.db.commit()


def _outline_warning(status: str) -> str | None:
    if status == "not_found":
        return "pdf_outline_not_found"
    if status == "failed":
        return "pdf_outline_failed"
    return None


async def process_document_background(document_id: uuid.UUID, db: AsyncSession) -> None:
    """Legacy entry point for non-PDF callers; PDFs require the durable runner."""

    await DocumentProcessingService(db).process_document(document_id)
