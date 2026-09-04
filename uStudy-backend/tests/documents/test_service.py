"""Tests for document upload service."""

import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from starlette.datastructures import Headers

from db.models import Space, SpaceDocument, SpaceMember, SpaceMemberRole, User
from documents.service import delete_document, upload_document
from rag import service as rag_service
from rag.parsing.formats import OLE_MAGIC

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


@pytest.mark.asyncio
async def test_upload_document_stores_canonical_mime(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "documents.service.settings.upload_dir", str(tmp_path / "uploads")
    )
    monkeypatch.setattr("documents.service.verify_space_ownership", AsyncMock())
    task_id = uuid4()
    enqueue = AsyncMock(return_value=SimpleNamespace(id=task_id))
    dispatch = Mock()
    monkeypatch.setattr("documents.service.enqueue_document_processing", enqueue)
    monkeypatch.setattr("documents.service.dispatch_document_processing", dispatch)

    db = AsyncMock()
    added_documents: list = []
    db.add = Mock(side_effect=added_documents.append)

    async def fake_refresh(document):
        document.id = uuid4()

    db.refresh.side_effect = fake_refresh

    upload = UploadFile(
        file=io.BytesIO(OLE_MAGIC + (b"\x00" * 128)),
        filename="legacy.doc",
        headers=Headers({"content-type": "application/msword"}),
    )

    document = await upload_document(
        db=db,
        space_id=uuid4(),
        user_id=uuid4(),
        file=upload,
        user=None,
    )

    assert document.mime_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert added_documents[0].mime_type == document.mime_type
    enqueue.assert_awaited_once()
    enqueue_call = enqueue.await_args
    assert enqueue_call.args[0] is db
    assert enqueue_call.kwargs == {"dispatch": False, "commit": False}
    dispatch.assert_called_once_with(task_id)
    assert added_documents[0].creator_user_id is not None


@pytest.mark.asyncio
async def test_upload_document_detects_markdown_from_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "documents.service.settings.upload_dir", str(tmp_path / "uploads")
    )
    monkeypatch.setattr("documents.service.verify_space_ownership", AsyncMock())
    monkeypatch.setattr(
        "documents.service.enqueue_document_processing",
        AsyncMock(return_value=SimpleNamespace(id=uuid4())),
    )
    monkeypatch.setattr("documents.service.dispatch_document_processing", Mock())

    db = AsyncMock()
    db.add = Mock()

    async def fake_refresh(document):
        document.id = uuid4()

    db.refresh.side_effect = fake_refresh

    upload = UploadFile(
        file=io.BytesIO(b"# Title\n\nBody"),
        filename="notes.md",
        headers=Headers({"content-type": "application/octet-stream"}),
    )

    document = await upload_document(
        db=db,
        space_id=uuid4(),
        user_id=uuid4(),
        file=upload,
        user=None,
    )

    assert document.mime_type == "text/markdown"


@pytest.mark.asyncio
async def test_upload_document_rejects_oversized_file_without_loading_into_memory(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        "documents.service.settings.upload_dir", str(tmp_path / "uploads")
    )
    monkeypatch.setattr("documents.service.settings.document_max_size_bytes", 4)
    monkeypatch.setattr("documents.service.verify_space_ownership", AsyncMock())
    monkeypatch.setattr("documents.service.enqueue_document_processing", AsyncMock())
    monkeypatch.setattr("documents.service.dispatch_document_processing", Mock())

    db = AsyncMock()
    db.add = Mock()

    upload = UploadFile(
        file=io.BytesIO(b"12345"),
        filename="large.txt",
        headers=Headers({"content-type": "text/plain"}),
    )

    with pytest.raises(HTTPException) as excinfo:
        await upload_document(
            db=db,
            space_id=uuid4(),
            user_id=uuid4(),
            file=upload,
            user=None,
        )

    assert excinfo.value.status_code == 400
    assert "最大 1MB" in excinfo.value.detail
    temp_dir = tmp_path / "uploads" / "tmp"
    assert not temp_dir.exists() or not any(temp_dir.iterdir())


def test_pdf_upload_skips_visual_enhancement(monkeypatch):
    monkeypatch.setattr(rag_service.settings, "vlm_processing_enabled", True)

    assert rag_service.should_run_visual_enhancement("application/pdf") is False
    assert rag_service.should_run_visual_enhancement("APPLICATION/PDF") is False
    assert rag_service.should_run_visual_enhancement("image/png") is True


def test_detect_scanned_pdf_for_image_only_pages():
    fitz = pytest.importorskip("fitz")
    pdf = fitz.open()
    for _ in range(3):
        page = pdf.new_page(width=200, height=200)
        page.insert_image(fitz.Rect(0, 0, 200, 200), stream=_ONE_PIXEL_PNG)
    content = pdf.tobytes()
    pdf.close()

    result = rag_service.detect_scanned_pdf(content)

    assert result.is_scanned is True
    assert result.page_count == 3
    assert result.scanned_like_pages == 3


def test_detect_scanned_pdf_ignores_single_image_cover():
    fitz = pytest.importorskip("fitz")
    pdf = fitz.open()
    cover = pdf.new_page(width=200, height=200)
    cover.insert_image(fitz.Rect(0, 0, 200, 200), stream=_ONE_PIXEL_PNG)
    for _ in range(3):
        page = pdf.new_page(width=300, height=300)
        page.insert_text(
            (36, 72),
            "Database Systems Concepts " * 8,
            fontsize=12,
        )
    content = pdf.tobytes()
    pdf.close()

    result = rag_service.detect_scanned_pdf(content)

    assert result.is_scanned is False
    assert result.scanned_like_pages == 1


@pytest.mark.asyncio
async def test_upload_enqueue_failure_does_not_commit_orphan_document(
    db_session, monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "documents.service.settings.upload_dir", str(tmp_path / "uploads")
    )
    monkeypatch.setattr("documents.service.verify_space_ownership", AsyncMock())
    monkeypatch.setattr(
        "documents.service.enqueue_document_processing",
        AsyncMock(side_effect=RuntimeError("queue unavailable")),
    )
    monkeypatch.setattr("documents.service.dispatch_document_processing", Mock())
    owner = User(email=f"upload-atomic-{uuid4().hex}@example.com", nickname="Owner")
    db_session.add(owner)
    await db_session.flush()
    space = Space(user_id=owner.id, name="Atomic Upload", color="#123456")
    db_session.add(space)
    await db_session.commit()
    upload = UploadFile(
        file=io.BytesIO(b"plain text document"),
        filename="notes.txt",
        headers=Headers({"content-type": "text/plain"}),
    )

    with pytest.raises(RuntimeError, match="queue unavailable"):
        await upload_document(
            db=db_session,
            space_id=space.id,
            user_id=owner.id,
            file=upload,
            user=None,
        )
    await db_session.rollback()

    assert (await db_session.scalars(select(SpaceDocument))).all() == []
    documents_dir = tmp_path / "uploads" / "documents"
    assert not documents_dir.exists() or not any(documents_dir.iterdir())


@pytest.mark.asyncio
async def test_course_member_cannot_delete_shared_document(db_session):
    owner = User(email=f"doc-owner-{uuid4().hex}@example.com", nickname="Owner")
    member = User(email=f"doc-member-{uuid4().hex}@example.com", nickname="Member")
    db_session.add_all([owner, member])
    await db_session.flush()
    space = Space(
        user_id=owner.id,
        name="Managed course material",
        color="#123456",
        is_collaborative=True,
    )
    db_session.add(space)
    await db_session.flush()
    db_session.add(
        SpaceMember(
            space_id=space.id,
            user_id=member.id,
            role=SpaceMemberRole.MEMBER,
        )
    )
    document = SpaceDocument(
        space_id=space.id,
        creator_user_id=None,
        doc_type="link",
        title="Shared syllabus",
        url="https://example.com/syllabus",
    )
    db_session.add(document)
    await db_session.commit()

    with pytest.raises(HTTPException) as excinfo:
        await delete_document(db_session, space.id, document.id, member.id)
    assert excinfo.value.status_code == 404
    assert await db_session.get(SpaceDocument, document.id) is not None

    await delete_document(db_session, space.id, document.id, owner.id)
    assert await db_session.get(SpaceDocument, document.id) is None
