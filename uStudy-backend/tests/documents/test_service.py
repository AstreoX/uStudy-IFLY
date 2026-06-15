"""Tests for document upload service."""

import io
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi import UploadFile
from starlette.datastructures import Headers

from documents.service import upload_document
from rag.parsing.formats import OLE_MAGIC


@pytest.mark.asyncio
async def test_upload_document_stores_canonical_mime(monkeypatch, tmp_path):
    monkeypatch.setattr("documents.service.settings.upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("documents.service.verify_space_ownership", AsyncMock())
    scheduled: list = []
    monkeypatch.setattr(
        "documents.service.schedule_document_processing",
        lambda document_id: scheduled.append(document_id),
    )

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
    assert scheduled == [document.id]


@pytest.mark.asyncio
async def test_upload_document_detects_markdown_from_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr("documents.service.settings.upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("documents.service.verify_space_ownership", AsyncMock())
    monkeypatch.setattr("documents.service.schedule_document_processing", lambda document_id: None)

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
    monkeypatch.setattr("documents.service.settings.upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("documents.service.settings.document_max_size_bytes", 4)
    monkeypatch.setattr("documents.service.verify_space_ownership", AsyncMock())
    monkeypatch.setattr("documents.service.schedule_document_processing", lambda document_id: None)

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
