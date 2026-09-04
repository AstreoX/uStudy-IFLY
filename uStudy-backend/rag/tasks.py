"""Durable document-processing task runner.

The web request only persists/dispatches work.  Claims, leases and fencing are
stored in PostgreSQL so a different worker can safely resume an interrupted
run without allowing an expired worker to publish stale results.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.database import get_scoped_session
from db.models import (
    DocumentChunk,
    DocumentProcessingTask,
    PdfPageAsset,
    PdfVisualIndex,
    ProcessingStatus,
    SpaceDocument,
)

logger = logging.getLogger(__name__)
settings = get_settings()

PDF_MIME_TYPE = "application/pdf"
PDF_CLAIM_CAPACITY_LOCK = 0x5052465F524147  # stable signed bigint: "PRF_RAG"
RETRY_DELAYS_SECONDS = (60, 300, 900)
_background_tasks: set[asyncio.Task[Any]] = set()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LeaseLostError(RuntimeError):
    """Raised when the current worker no longer owns a processing generation."""


@dataclass(frozen=True)
class ProcessingLease:
    task_id: uuid.UUID
    document_id: uuid.UUID
    generation: int
    attempt: int
    lease_token: uuid.UUID
    lease_owner: str

    async def heartbeat(
        self,
        *,
        stage: str | None = None,
        page_count: int | None = None,
        processed_pages: int | None = None,
        asset_count: int | None = None,
    ) -> None:
        """Renew this lease and optionally persist monotonic progress."""

        values: dict[str, Any] = {
            "lease_expires_at": utcnow()
            + timedelta(seconds=settings.pdf_processing_lease_seconds),
        }
        if stage is not None:
            values["stage"] = stage
        if page_count is not None:
            values["page_count"] = page_count
        if processed_pages is not None:
            values["processed_pages"] = processed_pages
        if asset_count is not None:
            values["asset_count"] = asset_count

        async with get_scoped_session() as db:
            result = await db.execute(
                update(DocumentProcessingTask)
                .where(
                    DocumentProcessingTask.id == self.task_id,
                    DocumentProcessingTask.document_id == self.document_id,
                    DocumentProcessingTask.generation == self.generation,
                    DocumentProcessingTask.lease_token == self.lease_token,
                    DocumentProcessingTask.status == ProcessingStatus.PROCESSING,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                await db.rollback()
                raise LeaseLostError(
                    f"document processing lease lost: task={self.task_id} "
                    f"generation={self.generation}"
                )
            await db.commit()

    async def assert_owned(self) -> None:
        await self.heartbeat()


def _lease_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"


def _is_pdf(document: SpaceDocument) -> bool:
    if (document.mime_type or "").lower() == PDF_MIME_TYPE:
        return True
    return (
        str(document.original_filename or document.url or "").lower().endswith(".pdf")
    )


def _is_retryable_failure(exc: BaseException) -> bool:
    explicit = getattr(exc, "retryable", None)
    if explicit is not None:
        return bool(explicit)
    return isinstance(
        exc,
        (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
            OperationalError,
        ),
    )


async def enqueue_document_processing(
    db: AsyncSession,
    document_id: uuid.UUID,
    *,
    dispatch: bool = True,
    commit: bool = True,
) -> DocumentProcessingTask:
    """Create a new user-requested generation and make it durable before return."""

    if dispatch and not commit:
        raise ValueError("dispatch requires a committed durable task")

    stmt = select(DocumentProcessingTask).where(
        DocumentProcessingTask.document_id == document_id
    )
    if db.get_bind().dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    task = await db.scalar(stmt)
    now = utcnow()

    if task is None:
        task = DocumentProcessingTask(
            document_id=document_id,
            status=ProcessingStatus.PENDING,
            generation=1,
            stage="queued",
            available_at=now,
        )
        db.add(task)
    else:
        previous_generation = int(task.generation or 0)
        await db.execute(
            update(PdfVisualIndex)
            .where(
                PdfVisualIndex.document_id == document_id,
                PdfVisualIndex.generation == previous_generation,
                PdfVisualIndex.is_current.is_(False),
                PdfVisualIndex.state == "staging",
            )
            .values(state="failed")
        )
        task.generation = previous_generation + 1
        task.status = ProcessingStatus.PENDING
        task.stage = "queued"
        task.page_count = None
        task.processed_pages = 0
        task.asset_count = 0
        task.chunk_count = None
        task.processed_chunks = 0
        task.attempt_count = 0
        task.available_at = now
        task.lease_owner = None
        task.lease_token = None
        task.lease_expires_at = None
        task.error_message = None
        task.error_code = None
        task.warning_code = None
        task.started_at = None
        task.completed_at = None

    if commit:
        await db.commit()
        await db.refresh(task)
    else:
        await db.flush()
    if dispatch:
        dispatch_document_processing(task.id)
    return task


async def enqueue_document_processing_in_new_session(
    document_id: uuid.UUID,
) -> DocumentProcessingTask:
    async with get_scoped_session() as db:
        return await enqueue_document_processing(db, document_id)


def schedule_document_processing(document_id: uuid.UUID) -> None:
    """Compatibility wrapper for callers that cannot await the durable enqueue."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("无法调度文档处理任务：没有运行中的事件循环")
        return
    task = loop.create_task(
        enqueue_document_processing_in_new_session(document_id),
        name=f"enqueue_document_{document_id}",
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def dispatch_document_processing(task_id: uuid.UUID) -> None:
    """Best-effort immediate dispatch; the recovery scanner is authoritative."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.info("任务 %s 已入库，将由恢复扫描器领取", task_id)
        return
    task = loop.create_task(
        process_document_task(task_id), name=f"document_processing_{task_id}"
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _claim_task(task_id: uuid.UUID) -> ProcessingLease | None:
    now = utcnow()
    async with get_scoped_session() as db:
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            # Serialise the capacity check across every API process/instance.
            await db.execute(
                text("SELECT pg_advisory_xact_lock(:key)"),
                {"key": PDF_CLAIM_CAPACITY_LOCK},
            )

        stmt = select(DocumentProcessingTask).where(
            DocumentProcessingTask.id == task_id,
            DocumentProcessingTask.attempt_count < settings.pdf_processing_max_attempts,
            or_(
                (
                    (DocumentProcessingTask.status == ProcessingStatus.PENDING)
                    & or_(
                        DocumentProcessingTask.available_at.is_(None),
                        DocumentProcessingTask.available_at <= now,
                    )
                ),
                (
                    (DocumentProcessingTask.status == ProcessingStatus.PROCESSING)
                    & (DocumentProcessingTask.lease_expires_at < now)
                ),
            ),
        )
        if dialect == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        else:
            stmt = stmt.with_for_update()
        task = await db.scalar(stmt)
        if task is None:
            return None

        document = await db.get(SpaceDocument, task.document_id)
        if document is None:
            await db.delete(task)
            await db.commit()
            return None

        if _is_pdf(document):
            active_pdf_jobs = await db.scalar(
                select(func.count(DocumentProcessingTask.id))
                .join(
                    SpaceDocument,
                    SpaceDocument.id == DocumentProcessingTask.document_id,
                )
                .where(
                    DocumentProcessingTask.id != task.id,
                    DocumentProcessingTask.status == ProcessingStatus.PROCESSING,
                    DocumentProcessingTask.lease_expires_at > now,
                    or_(
                        func.lower(SpaceDocument.mime_type) == PDF_MIME_TYPE,
                        func.lower(SpaceDocument.original_filename).like("%.pdf"),
                    ),
                )
            )
            if int(active_pdf_jobs or 0) >= settings.pdf_processing_max_concurrent_jobs:
                return None

        token = uuid.uuid4()
        owner = _lease_owner()
        task.status = ProcessingStatus.PROCESSING
        task.stage = task.stage if task.stage not in {None, "queued"} else "preflight"
        task.attempt_count = int(task.attempt_count or 0) + 1
        task.lease_owner = owner
        task.lease_token = token
        task.lease_expires_at = now + timedelta(
            seconds=settings.pdf_processing_lease_seconds
        )
        task.started_at = task.started_at or now
        task.error_message = None
        task.error_code = None
        await db.commit()
        return ProcessingLease(
            task_id=task.id,
            document_id=task.document_id,
            generation=task.generation,
            attempt=task.attempt_count,
            lease_token=token,
            lease_owner=owner,
        )


async def _mark_completed(
    lease: ProcessingLease,
    *,
    chunk_count: int,
    warning_code: str | None = None,
) -> None:
    async with get_scoped_session() as db:
        result = await db.execute(
            update(DocumentProcessingTask)
            .where(
                DocumentProcessingTask.id == lease.task_id,
                DocumentProcessingTask.generation == lease.generation,
                DocumentProcessingTask.lease_token == lease.lease_token,
                DocumentProcessingTask.status == ProcessingStatus.PROCESSING,
            )
            .values(
                status=ProcessingStatus.COMPLETED,
                stage="completed",
                chunk_count=chunk_count,
                processed_chunks=chunk_count,
                warning_code=warning_code,
                lease_owner=None,
                lease_token=None,
                lease_expires_at=None,
                completed_at=utcnow(),
            )
        )
        if result.rowcount != 1:
            await db.rollback()
            raise LeaseLostError("lease lost before completion")
        await db.commit()


async def _mark_failed(
    lease: ProcessingLease,
    exc: BaseException,
    *,
    retryable: bool,
    error_code: str | None,
) -> None:
    now = utcnow()
    max_attempts = settings.pdf_processing_max_attempts
    should_retry = retryable and lease.attempt < max_attempts
    values: dict[str, Any] = {
        "error_message": str(exc)[:5000],
        "error_code": error_code or type(exc).__name__.upper(),
        "lease_owner": None,
        "lease_token": None,
        "lease_expires_at": None,
    }
    if should_retry:
        delay_index = min(lease.attempt - 1, len(RETRY_DELAYS_SECONDS) - 1)
        values.update(
            status=ProcessingStatus.PENDING,
            stage="retry_wait",
            available_at=now + timedelta(seconds=RETRY_DELAYS_SECONDS[delay_index]),
        )
    else:
        values.update(
            status=ProcessingStatus.FAILED,
            stage="failed",
            completed_at=now,
        )

    async with get_scoped_session() as db:
        result = await db.execute(
            update(DocumentProcessingTask)
            .where(
                DocumentProcessingTask.id == lease.task_id,
                DocumentProcessingTask.generation == lease.generation,
                DocumentProcessingTask.lease_token == lease.lease_token,
                DocumentProcessingTask.status == ProcessingStatus.PROCESSING,
            )
            .values(**values)
        )
        if result.rowcount == 1:
            if not should_retry:
                await db.execute(
                    update(PdfVisualIndex)
                    .where(
                        PdfVisualIndex.document_id == lease.document_id,
                        PdfVisualIndex.generation == lease.generation,
                        PdfVisualIndex.is_current.is_(False),
                    )
                    .values(state="failed")
                )
            await db.commit()
        else:
            await db.rollback()


async def process_document_task(task_id: uuid.UUID) -> None:
    lease = await _claim_task(task_id)
    if lease is None:
        return

    try:
        from rag.service import DocumentProcessingService

        async with get_scoped_session() as db:
            outcome = await DocumentProcessingService(db).process_document(
                lease.document_id,
                lease=lease,
            )
        await _mark_completed(
            lease,
            chunk_count=int(getattr(outcome, "chunk_count", 0)),
            warning_code=getattr(outcome, "warning_code", None),
        )
    except LeaseLostError:
        logger.info(
            "停止已失去租约的文档任务: task=%s generation=%s",
            lease.task_id,
            lease.generation,
        )
    except Exception as exc:
        retryable = _is_retryable_failure(exc)
        error_code = getattr(exc, "error_code", None)
        logger.exception(
            "文档处理失败: task=%s generation=%s attempt=%s",
            lease.task_id,
            lease.generation,
            lease.attempt,
        )
        await _mark_failed(
            lease,
            exc,
            retryable=retryable,
            error_code=error_code,
        )


async def recover_document_processing_tasks() -> None:
    """Dispatch due and lease-expired jobs; the claim transaction deduplicates."""

    now = utcnow()
    async with get_scoped_session() as db:
        exhausted_stmt = select(DocumentProcessingTask).where(
            DocumentProcessingTask.attempt_count
            >= settings.pdf_processing_max_attempts,
            DocumentProcessingTask.status.in_(
                (ProcessingStatus.PENDING, ProcessingStatus.PROCESSING)
            ),
            or_(
                (
                    (DocumentProcessingTask.status == ProcessingStatus.PENDING)
                    & or_(
                        DocumentProcessingTask.available_at.is_(None),
                        DocumentProcessingTask.available_at <= now,
                    )
                ),
                (
                    (DocumentProcessingTask.status == ProcessingStatus.PROCESSING)
                    & or_(
                        DocumentProcessingTask.lease_expires_at.is_(None),
                        DocumentProcessingTask.lease_expires_at < now,
                    )
                ),
            ),
        )
        if db.get_bind().dialect.name == "postgresql":
            # Serialize terminal recovery with user-triggered reprocess. Without
            # this lock an ORM snapshot of generation N can overwrite the new
            # generation N+1 state after enqueue commits.
            exhausted_stmt = exhausted_stmt.with_for_update(skip_locked=True)
        exhausted = list((await db.scalars(exhausted_stmt)).all())
        for task in exhausted:
            published = await db.scalar(
                select(PdfVisualIndex).where(
                    PdfVisualIndex.document_id == task.document_id,
                    PdfVisualIndex.generation == task.generation,
                    PdfVisualIndex.is_current.is_(True),
                    PdfVisualIndex.state == "published",
                )
            )
            if published is not None:
                chunk_count = int(
                    await db.scalar(
                        select(func.count(DocumentChunk.id)).where(
                            DocumentChunk.pdf_visual_index_id == published.id
                        )
                    )
                    or 0
                )
                asset_count = int(
                    await db.scalar(
                        select(func.count(PdfPageAsset.id)).where(
                            PdfPageAsset.index_id == published.id
                        )
                    )
                    or 0
                )
                task.status = ProcessingStatus.COMPLETED
                task.stage = "completed"
                task.page_count = published.page_count
                task.processed_pages = published.page_count
                task.asset_count = asset_count
                task.chunk_count = chunk_count
                task.processed_chunks = chunk_count
                task.warning_code = (
                    "pdf_outline_not_found"
                    if published.outline_status == "not_found"
                    else (
                        "pdf_outline_failed"
                        if published.outline_status == "failed"
                        else None
                    )
                )
                task.error_code = None
                task.error_message = None
            else:
                task.status = ProcessingStatus.FAILED
                task.stage = "failed"
                task.error_code = task.error_code or "MAX_ATTEMPTS_EXHAUSTED"
                task.error_message = task.error_message or "文档处理最终尝试中断"
            task.lease_owner = None
            task.lease_token = None
            task.lease_expires_at = None
            task.completed_at = now
            if published is None:
                await db.execute(
                    update(PdfVisualIndex)
                    .where(
                        PdfVisualIndex.document_id == task.document_id,
                        PdfVisualIndex.generation == task.generation,
                        PdfVisualIndex.is_current.is_(False),
                        PdfVisualIndex.state == "staging",
                    )
                    .values(state="failed")
                )
        if exhausted:
            await db.commit()

        task_ids = list(
            (
                await db.scalars(
                    select(DocumentProcessingTask.id)
                    .where(
                        DocumentProcessingTask.attempt_count
                        < settings.pdf_processing_max_attempts,
                        or_(
                            (
                                (
                                    DocumentProcessingTask.status
                                    == ProcessingStatus.PENDING
                                )
                                & or_(
                                    DocumentProcessingTask.available_at.is_(None),
                                    DocumentProcessingTask.available_at <= now,
                                )
                            ),
                            (
                                (
                                    DocumentProcessingTask.status
                                    == ProcessingStatus.PROCESSING
                                )
                                & (DocumentProcessingTask.lease_expires_at < now)
                            ),
                        ),
                    )
                    .order_by(DocumentProcessingTask.available_at)
                    .limit(20)
                )
            ).all()
        )
    for task_id in task_ids:
        dispatch_document_processing(task_id)


async def cleanup_pdf_staging_directories() -> int:
    """Remove expired staging, obsolete generations and unreferenced final dirs."""

    private_root = Path(settings.pdf_private_dir).resolve()
    if not private_root.exists():
        return 0
    cutoff = utcnow().timestamp() - settings.pdf_staging_retention_seconds
    removed = 0
    for path in private_root.rglob(".staging-*"):
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(private_root) or not resolved.is_dir():
                continue
            if resolved.stat().st_mtime >= cutoff:
                continue
            import shutil

            await asyncio.to_thread(shutil.rmtree, resolved)
            removed += 1
        except FileNotFoundError:
            continue
        except Exception:
            logger.warning("清理 PDF staging 目录失败: %s", path, exc_info=True)

    cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
    async with get_scoped_session() as db:
        abandoned_staging = list(
            (
                await db.scalars(
                    select(PdfVisualIndex)
                    .outerjoin(
                        DocumentProcessingTask,
                        DocumentProcessingTask.document_id
                        == PdfVisualIndex.document_id,
                    )
                    .where(
                        PdfVisualIndex.is_current.is_(False),
                        PdfVisualIndex.state == "staging",
                        PdfVisualIndex.created_at < cutoff_dt,
                        or_(
                            DocumentProcessingTask.id.is_(None),
                            DocumentProcessingTask.generation
                            != PdfVisualIndex.generation,
                            DocumentProcessingTask.status.in_(
                                (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED)
                            ),
                        ),
                    )
                )
            ).all()
        )
        for index in abandoned_staging:
            index.state = "failed"
        if abandoned_staging:
            await db.flush()

        obsolete = list(
            (
                await db.scalars(
                    select(PdfVisualIndex).where(
                        PdfVisualIndex.is_current.is_(False),
                        PdfVisualIndex.state.in_(("superseded", "failed")),
                        PdfVisualIndex.created_at < cutoff_dt,
                    )
                )
            ).all()
        )
        all_rows = list((await db.scalars(select(PdfVisualIndex))).all())
        referenced = {
            (
                str(row.space_id),
                str(row.document_id),
                f"v{int(row.generation):06d}",
            )
            for row in all_rows
        }
        for index in obsolete:
            version_dir = (
                private_root
                / str(index.space_id)
                / str(index.document_id)
                / f"v{int(index.generation):06d}"
            ).resolve()
            if version_dir.is_relative_to(private_root) and version_dir.exists():
                try:
                    import shutil

                    await asyncio.to_thread(shutil.rmtree, version_dir)
                except Exception:
                    logger.warning(
                        "清理过期 PDF generation 失败: %s", version_dir, exc_info=True
                    )
                    continue
            await db.delete(index)
            referenced.discard(
                (
                    str(index.space_id),
                    str(index.document_id),
                    f"v{int(index.generation):06d}",
                )
            )
            removed += 1
        await db.commit()

    # A crash between filesystem rename and DB publication can leave an
    # immutable-looking version directory with no database row.
    for version_dir in private_root.glob("*/*/v[0-9]*"):
        try:
            resolved = version_dir.resolve()
            if not resolved.is_relative_to(private_root) or not resolved.is_dir():
                continue
            key = (
                version_dir.parent.parent.name,
                version_dir.parent.name,
                version_dir.name,
            )
            if key in referenced or resolved.stat().st_mtime >= cutoff:
                continue
            import shutil

            await asyncio.to_thread(shutil.rmtree, resolved)
            removed += 1
        except FileNotFoundError:
            continue
        except Exception:
            logger.warning(
                "清理孤儿 PDF generation 失败: %s", version_dir, exc_info=True
            )
    return removed
