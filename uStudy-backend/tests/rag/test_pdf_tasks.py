"""Tests for durable PDF/document processing leases and recovery."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    DocumentProcessingTask,
    DocumentType,
    PdfVisualIndex,
    ProcessingStatus,
    Space,
    SpaceDocument,
    User,
)
from rag import tasks as pdf_tasks


def test_retry_classifier_defaults_permanent_and_honors_explicit_transient():
    class ExplicitTransient(RuntimeError):
        retryable = True

    assert pdf_tasks._is_retryable_failure(ValueError("bad input")) is False
    assert pdf_tasks._is_retryable_failure(FileNotFoundError("missing")) is False
    assert pdf_tasks._is_retryable_failure(ExplicitTransient("retry")) is True


def _patch_scoped_session(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    @asynccontextmanager
    async def _scoped_session():
        yield db_session

    monkeypatch.setattr(pdf_tasks, "get_scoped_session", _scoped_session)


async def _create_task(
    db_session: AsyncSession,
    *,
    status: ProcessingStatus = ProcessingStatus.PENDING,
    generation: int = 1,
    attempt_count: int = 0,
    available_at: datetime | None = None,
    lease_token: uuid.UUID | None = None,
    lease_expires_at: datetime | None = None,
) -> DocumentProcessingTask:
    unique = uuid.uuid4().hex
    user = User(email=f"pdf-task-{unique}@example.com", nickname="PDF Task")
    db_session.add(user)
    await db_session.flush()
    space = Space(user_id=user.id, name=f"Space {unique}", color="#123456")
    db_session.add(space)
    await db_session.flush()
    document = SpaceDocument(
        space_id=space.id,
        doc_type=DocumentType.DOCUMENT,
        title=f"Textbook {unique}",
        url=f"/uploads/documents/{unique}.pdf",
        original_filename=f"{unique}.pdf",
        mime_type="application/pdf",
    )
    db_session.add(document)
    await db_session.flush()
    task = DocumentProcessingTask(
        document_id=document.id,
        status=status,
        generation=generation,
        stage="rendering" if status == ProcessingStatus.PROCESSING else "queued",
        attempt_count=attempt_count,
        available_at=available_at or datetime.now(timezone.utc),
        lease_owner="test-worker" if lease_token else None,
        lease_token=lease_token,
        lease_expires_at=lease_expires_at,
    )
    db_session.add(task)
    await db_session.commit()
    return task


@pytest.mark.asyncio
async def test_mark_completed_requires_matching_generation_and_lease_token(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_scoped_session(monkeypatch, db_session)
    valid_token = uuid.uuid4()
    task = await _create_task(
        db_session,
        status=ProcessingStatus.PROCESSING,
        generation=3,
        attempt_count=1,
        lease_token=valid_token,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    task_id = task.id
    document_id = task.document_id

    stale_lease = pdf_tasks.ProcessingLease(
        task_id=task_id,
        document_id=document_id,
        generation=2,
        attempt=1,
        lease_token=valid_token,
        lease_owner="stale-worker",
    )
    with pytest.raises(pdf_tasks.LeaseLostError):
        await pdf_tasks._mark_completed(stale_lease, chunk_count=7)

    wrong_token_lease = pdf_tasks.ProcessingLease(
        task_id=task_id,
        document_id=document_id,
        generation=3,
        attempt=1,
        lease_token=uuid.uuid4(),
        lease_owner="wrong-worker",
    )
    with pytest.raises(pdf_tasks.LeaseLostError):
        await pdf_tasks._mark_completed(wrong_token_lease, chunk_count=7)

    db_session.expire_all()
    unchanged = await db_session.get(DocumentProcessingTask, task_id)
    assert unchanged is not None
    assert unchanged.status == ProcessingStatus.PROCESSING
    assert unchanged.stage == "rendering"
    assert unchanged.lease_token == valid_token

    active_lease = pdf_tasks.ProcessingLease(
        task_id=task_id,
        document_id=document_id,
        generation=3,
        attempt=1,
        lease_token=valid_token,
        lease_owner="test-worker",
    )
    await pdf_tasks._mark_completed(
        active_lease, chunk_count=7, warning_code="OUTLINE_NOT_FOUND"
    )

    db_session.expire_all()
    completed = await db_session.get(DocumentProcessingTask, task_id)
    assert completed is not None
    assert completed.status == ProcessingStatus.COMPLETED
    assert completed.stage == "completed"
    assert completed.chunk_count == 7
    assert completed.processed_chunks == 7
    assert completed.warning_code == "OUTLINE_NOT_FOUND"
    assert completed.lease_owner is None
    assert completed.lease_token is None
    assert completed.lease_expires_at is None
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_mark_failed_schedules_retry_with_backoff_and_clears_lease(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_scoped_session(monkeypatch, db_session)
    valid_token = uuid.uuid4()
    before = datetime.now(timezone.utc)
    task = await _create_task(
        db_session,
        status=ProcessingStatus.PROCESSING,
        attempt_count=1,
        lease_token=valid_token,
        lease_expires_at=before + timedelta(minutes=5),
    )
    task_id = task.id
    lease = pdf_tasks.ProcessingLease(
        task_id=task_id,
        document_id=task.document_id,
        generation=task.generation,
        attempt=1,
        lease_token=valid_token,
        lease_owner="test-worker",
    )

    await pdf_tasks._mark_failed(
        lease,
        RuntimeError("temporary VLM failure"),
        retryable=True,
        error_code="VLM_TIMEOUT",
    )

    db_session.expire_all()
    retry = await db_session.get(DocumentProcessingTask, task_id)
    assert retry is not None
    assert retry.status == ProcessingStatus.PENDING
    assert retry.stage == "retry_wait"
    assert retry.error_code == "VLM_TIMEOUT"
    assert retry.error_message == "temporary VLM failure"
    assert retry.lease_owner is None
    assert retry.lease_token is None
    assert retry.lease_expires_at is None
    assert retry.completed_at is None
    assert retry.available_at is not None
    retry_at = retry.available_at
    if retry_at.tzinfo is None:  # SQLite does not preserve timezone metadata.
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    assert before + timedelta(seconds=55) <= retry_at
    assert retry_at <= datetime.now(timezone.utc) + timedelta(seconds=65)


@pytest.mark.asyncio
async def test_recovery_dispatches_only_due_or_expired_tasks(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_scoped_session(monkeypatch, db_session)
    now = datetime.now(timezone.utc)
    due = await _create_task(
        db_session,
        available_at=now - timedelta(seconds=1),
    )
    future = await _create_task(
        db_session,
        available_at=now + timedelta(hours=1),
    )
    expired = await _create_task(
        db_session,
        status=ProcessingStatus.PROCESSING,
        attempt_count=1,
        lease_token=uuid.uuid4(),
        lease_expires_at=now - timedelta(seconds=1),
    )
    active = await _create_task(
        db_session,
        status=ProcessingStatus.PROCESSING,
        attempt_count=1,
        lease_token=uuid.uuid4(),
        lease_expires_at=now + timedelta(hours=1),
    )
    completed = await _create_task(
        db_session,
        status=ProcessingStatus.COMPLETED,
        available_at=now - timedelta(hours=1),
    )
    exhausted = await _create_task(
        db_session,
        attempt_count=pdf_tasks.settings.pdf_processing_max_attempts,
        available_at=now - timedelta(hours=1),
    )
    exhausted_running = await _create_task(
        db_session,
        status=ProcessingStatus.PROCESSING,
        attempt_count=pdf_tasks.settings.pdf_processing_max_attempts,
        lease_token=uuid.uuid4(),
        lease_expires_at=now - timedelta(seconds=1),
    )
    published_crash = await _create_task(
        db_session,
        status=ProcessingStatus.PROCESSING,
        generation=2,
        attempt_count=pdf_tasks.settings.pdf_processing_max_attempts,
        lease_token=uuid.uuid4(),
        lease_expires_at=now - timedelta(seconds=1),
    )
    published_document = await db_session.get(
        SpaceDocument, published_crash.document_id
    )
    assert published_document is not None
    db_session.add(
        PdfVisualIndex(
            document_id=published_document.id,
            space_id=published_document.space_id,
            generation=2,
            state="published",
            is_current=True,
            source_sha256="f" * 64,
            page_count=4,
            outline_status="not_found",
            renderer_version="v1",
        )
    )
    await db_session.commit()
    dispatched: list[uuid.UUID] = []
    monkeypatch.setattr(pdf_tasks, "dispatch_document_processing", dispatched.append)

    await pdf_tasks.recover_document_processing_tasks()

    assert set(dispatched) == {due.id, expired.id}
    assert future.id not in dispatched
    assert active.id not in dispatched
    assert completed.id not in dispatched
    assert exhausted.id not in dispatched
    assert exhausted_running.id not in dispatched
    assert published_crash.id not in dispatched
    await db_session.refresh(exhausted)
    assert exhausted.status == ProcessingStatus.FAILED
    assert exhausted.stage == "failed"
    assert exhausted.error_code == "MAX_ATTEMPTS_EXHAUSTED"
    await db_session.refresh(exhausted_running)
    assert exhausted_running.status == ProcessingStatus.FAILED
    assert exhausted_running.lease_token is None
    await db_session.refresh(published_crash)
    assert published_crash.status == ProcessingStatus.COMPLETED
    assert published_crash.page_count == 4
    assert published_crash.warning_code == "pdf_outline_not_found"


@pytest.mark.asyncio
async def test_staging_cleanup_only_removes_expired_directories_under_private_root(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_scoped_session(monkeypatch, db_session)
    private_root = tmp_path / "private-rag"
    unique = uuid.uuid4().hex
    user = User(email=f"cleanup-{unique}@example.com", nickname="Cleanup")
    db_session.add(user)
    await db_session.flush()
    space = Space(user_id=user.id, name="Cleanup Space", color="#654321")
    db_session.add(space)
    await db_session.flush()
    document = SpaceDocument(
        space_id=space.id,
        doc_type=DocumentType.DOCUMENT,
        title="Cleanup PDF",
        url="/uploads/documents/cleanup.pdf",
        original_filename="cleanup.pdf",
        mime_type="application/pdf",
    )
    db_session.add(document)
    await db_session.flush()

    old_timestamp = datetime.now(timezone.utc).timestamp() - 3600
    old_datetime = datetime.fromtimestamp(old_timestamp, tz=timezone.utc)
    current_index = PdfVisualIndex(
        document_id=document.id,
        space_id=space.id,
        generation=1,
        state="published",
        is_current=True,
        source_sha256="a" * 64,
        page_count=10,
        outline_status="ready",
        renderer_version="v1",
        created_at=old_datetime,
    )
    obsolete_index = PdfVisualIndex(
        document_id=document.id,
        space_id=space.id,
        generation=2,
        state="superseded",
        is_current=False,
        source_sha256="a" * 64,
        page_count=10,
        outline_status="ready",
        renderer_version="v1",
        created_at=old_datetime,
    )
    db_session.add_all([current_index, obsolete_index])
    await db_session.commit()
    obsolete_index_id = obsolete_index.id

    document_dir = private_root / str(space.id) / str(document.id)
    old_staging = document_dir / ".staging-old"
    recent_staging = document_dir / ".staging-recent"
    published = document_dir / "v000001"
    obsolete = document_dir / "v000002"
    orphan = document_dir / "v000999"
    recent_orphan = document_dir / "v001000"
    staging_named_file = document_dir / ".staging-file"
    outside_staging = tmp_path / "outside" / ".staging-external"
    for directory in (
        old_staging,
        recent_staging,
        published,
        obsolete,
        orphan,
        recent_orphan,
        outside_staging,
    ):
        directory.mkdir(parents=True)
        (directory / "asset.webp").write_bytes(b"asset")
    staging_named_file.write_bytes(b"not a directory")

    for old_directory in (
        old_staging,
        published,
        obsolete,
        orphan,
        outside_staging,
    ):
        os.utime(old_directory, (old_timestamp, old_timestamp))

    # When supported, include a path that lexically lives below the private
    # root but resolves outside it. The cleaner must not follow it.
    external_link = document_dir / ".staging-link"
    try:
        external_link.symlink_to(outside_staging, target_is_directory=True)
    except OSError:
        external_link = None

    monkeypatch.setattr(pdf_tasks.settings, "pdf_private_dir", str(private_root))
    monkeypatch.setattr(pdf_tasks.settings, "pdf_staging_retention_seconds", 60)

    removed = await pdf_tasks.cleanup_pdf_staging_directories()

    assert removed == 3
    assert not old_staging.exists()
    assert recent_staging.exists()
    assert published.exists()
    assert not obsolete.exists()
    assert not orphan.exists()
    assert recent_orphan.exists()
    assert staging_named_file.exists()
    assert outside_staging.exists()
    if external_link is not None:
        assert external_link.exists()

    assert await db_session.get(PdfVisualIndex, current_index.id) is not None
    assert await db_session.get(PdfVisualIndex, obsolete_index_id) is None
    remaining_generations = set(
        (
            await db_session.scalars(
                select(PdfVisualIndex.generation).where(
                    PdfVisualIndex.document_id == document.id
                )
            )
        ).all()
    )
    assert remaining_generations == {1}
