"""SQLite integration coverage for atomic Agentic-PDF publication."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import agents.llm
from db.models import (
    DocumentChunk,
    DocumentProcessingTask,
    DocumentText,
    DocumentType,
    PdfIndexAgentCall,
    PdfPageAsset,
    PdfVisualIndex,
    ProcessingStatus,
    Space,
    SpaceDocument,
    User,
)
from rag import pdf_agentic
from rag import service as rag_service
from rag.pdf_agentic import (
    OutlineEntry,
    PageAssetManifest,
    PdfPreflight,
    PdfVisualIndexError,
    PdfVisualIndexErrorCode,
    RenderManifest,
    TocAgentResult,
    expected_asset_count,
    write_outline_artifacts,
)
from rag.service import DocumentProcessingService
from rag.tasks import LeaseLostError


@dataclass
class _FakeLease:
    task_id: uuid.UUID
    document_id: uuid.UUID
    generation: int
    attempt: int
    lease_token: uuid.UUID
    lease_owner: str = "integration-worker"
    heartbeats: list[dict[str, Any]] = field(default_factory=list)

    async def heartbeat(self, **values: Any) -> None:
        self.heartbeats.append(values)

    async def assert_owned(self) -> None:
        return None


class _NoCallLLM:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def complete(self, *args: Any, **kwargs: Any) -> str:
        raise AssertionError("stub TOC agent must not invoke the real LLM")


async def _seed_document_and_task(
    db_session: AsyncSession,
    tmp_path: Path,
    *,
    generation: int,
    lease_expires_at: datetime | None = None,
) -> tuple[SpaceDocument, DocumentProcessingTask, _FakeLease, Path, Path]:
    unique = uuid.uuid4().hex
    user = User(email=f"pdf-service-{unique}@example.com", nickname="PDF Service")
    db_session.add(user)
    await db_session.flush()
    space = Space(user_id=user.id, name=f"PDF Space {unique}", color="#345678")
    db_session.add(space)
    await db_session.flush()

    upload_root = tmp_path / "uploads"
    source_path = upload_root / "documents" / f"{unique}.pdf"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"%PDF-service-integration-source\n" + b"x" * 4096)
    document = SpaceDocument(
        space_id=space.id,
        doc_type=DocumentType.DOCUMENT,
        title="Scanned textbook",
        url=f"/uploads/documents/{unique}.pdf",
        original_filename=f"{unique}.pdf",
        file_size=source_path.stat().st_size,
        mime_type="application/pdf",
        creator_user_id=user.id,
    )
    db_session.add(document)
    await db_session.flush()

    token = uuid.uuid4()
    task = DocumentProcessingTask(
        document_id=document.id,
        status=ProcessingStatus.PROCESSING,
        generation=generation,
        stage="preflight",
        attempt_count=1,
        available_at=datetime.now(timezone.utc),
        lease_owner="integration-worker",
        lease_token=token,
        lease_expires_at=lease_expires_at
        or datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(task)
    await db_session.commit()
    lease = _FakeLease(
        task_id=task.id,
        document_id=document.id,
        generation=generation,
        attempt=1,
        lease_token=token,
    )
    return document, task, lease, upload_root, source_path


def _write_fake_render(
    root: Path,
    *,
    page_count: int,
    native_text: dict[int, str] | None = None,
) -> RenderManifest:
    root.mkdir(parents=True, exist_ok=True)
    native_text = native_text or {}
    native_path = root / "native_text.jsonl"
    native_payload = "".join(
        json.dumps(
            {"physical_page": page, "text": native_text.get(page, "")},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
        for page in range(1, page_count + 1)
    ).encode("utf-8")
    native_path.write_bytes(native_payload)

    assets: list[PageAssetManifest] = []
    derived_bytes = len(native_payload)
    for lod in (1, 2, 4):
        for start in range(1, page_count + 1, lod):
            end = min(start + lod - 1, page_count)
            relative_path = f"pages/{lod}/pages-{start:06d}-{end:06d}.webp"
            payload = f"fake-webp:{lod}:{start}:{end}".encode()
            asset_path = root / relative_path
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(payload)
            assets.append(
                PageAssetManifest(
                    pages_per_image=lod,  # type: ignore[arg-type]
                    physical_page_start=start,
                    physical_page_end=end,
                    relative_path=relative_path,
                    mime_type="image/webp",
                    width=100,
                    height=120,
                    byte_size=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
            )
            derived_bytes += len(payload)
    (root / "manifest.json").write_text("{}\n", encoding="utf-8")
    derived_bytes += (root / "manifest.json").stat().st_size
    return RenderManifest(
        schema_version=1,
        page_count=page_count,
        render_dpi=160,
        render_max_pixels=8_000_000,
        webp_quality=85,
        max_image_bytes=4 * 1024 * 1024,
        lod_max_side=2048,
        native_text_jsonl="native_text.jsonl",
        native_text_page_count=page_count,
        native_text_nonempty_page_count=sum(
            bool(native_text.get(page, "").strip()) for page in range(1, page_count + 1)
        ),
        assets=tuple(assets),
        derived_bytes=derived_bytes,
    )


def _install_pipeline_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    upload_root: Path,
    private_root: Path,
    toc_result: TocAgentResult,
    page_count: int,
    native_text: dict[int, str] | None = None,
) -> list[Path]:
    monkeypatch.setattr(rag_service.settings, "upload_dir", str(upload_root))
    monkeypatch.setattr(rag_service.settings, "pdf_private_dir", str(private_root))
    monkeypatch.setattr(rag_service.settings, "pdf_agentic_enabled", True)
    monkeypatch.setattr(rag_service.settings, "pdf_max_derived_bytes", 10_000_000)
    monkeypatch.setattr(agents.llm, "LLMClient", _NoCallLLM)
    component_paths: list[Path] = []

    def fake_preflight(pdf_path: Path, *, max_pages: int) -> PdfPreflight:
        assert isinstance(pdf_path, Path)
        assert pdf_path.is_file()
        assert max_pages >= page_count
        component_paths.append(pdf_path)
        return PdfPreflight(pdf_path=pdf_path, page_count=page_count)

    def fake_load(root: Path) -> RenderManifest:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.MANIFEST_INVALID,
            f"no reusable manifest at {root.name}",
        )

    def fake_render(
        pdf_path: Path, staging_root: Path, **kwargs: Any
    ) -> RenderManifest:
        assert isinstance(pdf_path, Path)
        assert isinstance(staging_root, Path)
        assert callable(kwargs["should_cancel"])
        component_paths.append(pdf_path)
        return _write_fake_render(
            staging_root,
            page_count=page_count,
            native_text=native_text,
        )

    class FakeTocAgent:
        def __init__(self, **kwargs: Any) -> None:
            assert callable(kwargs["completion"])
            assert callable(kwargs["checkpoint_get"])
            assert callable(kwargs["checkpoint_put"])

        async def run(
            self,
            document_id: str,
            generation: int,
            manifest: RenderManifest,
            asset_root: Path,
        ) -> TocAgentResult:
            assert document_id
            assert generation >= 1
            assert manifest.page_count == page_count
            assert asset_root.name.startswith(".staging-")
            return toc_result

    monkeypatch.setattr(pdf_agentic, "preflight_pdf", fake_preflight)
    monkeypatch.setattr(pdf_agentic, "load_render_manifest", fake_load)
    monkeypatch.setattr(pdf_agentic, "render_pdf_visual_index", fake_render)
    monkeypatch.setattr(pdf_agentic, "TocIndexAgent", FakeTocAgent)
    return component_paths


@pytest.mark.asyncio
async def test_new_pdf_uses_path_pipeline_and_publishes_no_toc_as_degraded_success(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document, _, lease, upload_root, source_path = await _seed_document_and_task(
        db_session, tmp_path, generation=1
    )
    private_root = tmp_path / "private-rag"
    invalid_old_staging = (
        private_root
        / str(document.space_id)
        / str(document.id)
        / ".staging-000001-expired-token"
    )
    invalid_old_staging.mkdir(parents=True)
    (invalid_old_staging / "partial.webp").write_bytes(b"partial")
    component_paths = _install_pipeline_stubs(
        monkeypatch,
        upload_root=upload_root,
        private_root=private_root,
        toc_result=TocAgentResult(status="not_found"),
        page_count=2,
    )

    async def reject_whole_file_read(*args: Any, **kwargs: Any) -> bytes:
        raise AssertionError("Agentic PDF path must not call _read_document_content")

    monkeypatch.setattr(
        DocumentProcessingService,
        "_read_document_content",
        reject_whole_file_read,
    )
    outcome = await DocumentProcessingService(db_session).process_document(
        document.id,
        lease=lease,  # type: ignore[arg-type]
    )

    assert outcome.chunk_count == 0
    assert outcome.warning_code == "pdf_outline_not_found"
    assert component_paths == [source_path.resolve(), source_path.resolve()]
    index = await db_session.scalar(
        select(PdfVisualIndex).where(PdfVisualIndex.document_id == document.id)
    )
    assert index is not None
    assert index.state == "published"
    assert index.is_current is True
    assert index.outline_status == "not_found"
    assert index.page_offset is None
    assets = list(
        (
            await db_session.scalars(
                select(PdfPageAsset).where(PdfPageAsset.index_id == index.id)
            )
        ).all()
    )
    assert len(assets) == expected_asset_count(2)
    assert all(not Path(asset.storage_key).is_absolute() for asset in assets)
    assert all("v000001" in asset.storage_key for asset in assets)
    assert (
        private_root / str(document.space_id) / str(document.id) / "v000001"
    ).is_dir()
    assert not (
        private_root / str(document.space_id) / str(document.id) / ".staging-000001"
    ).exists()
    assert not invalid_old_staging.exists()
    doc_text = await db_session.scalar(
        select(DocumentText).where(DocumentText.document_id == document.id)
    )
    assert doc_text is not None
    assert "No table-of-contents entries" in doc_text.content


@pytest.mark.asyncio
async def test_ready_outline_atomically_supersedes_old_current_and_publishes_chunks(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document, _, lease, upload_root, _ = await _seed_document_and_task(
        db_session, tmp_path, generation=2
    )
    old_index = PdfVisualIndex(
        document_id=document.id,
        space_id=document.space_id,
        generation=1,
        state="published",
        is_current=True,
        source_sha256="0" * 64,
        page_count=6,
        outline_status="not_found",
        outline_entries=[],
        derived_bytes=1,
        renderer_version="agentic-pdf-v1",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(old_index)
    await db_session.flush()
    old_chunk = DocumentChunk(
        document_id=document.id,
        space_id=document.space_id,
        pdf_visual_index_id=old_index.id,
        chunk_kind="native_page",
        physical_page_start=1,
        physical_page_end=1,
        chunk_index=0,
        content="old generation content",
        token_count=3,
        chunk_metadata={"source_type": "pdf"},
    )
    db_session.add(old_chunk)
    db_session.add(
        DocumentText(
            document_id=document.id,
            space_id=document.space_id,
            content="old fallback content",
            word_count=3,
        )
    )
    await db_session.commit()

    entries = (
        OutlineEntry(
            title="Chapter One",
            level=1,
            printed_page_label="1",
            printed_page_number=1,
            source_physical_page=2,
            resolved_pdf_page=4,
        ),
        OutlineEntry(
            title="Appendix",
            level=1,
            printed_page_label="xii",
            printed_page_number=None,
            source_physical_page=2,
            resolved_pdf_page=None,
        ),
    )
    private_root = tmp_path / "private-rag"
    _install_pipeline_stubs(
        monkeypatch,
        upload_root=upload_root,
        private_root=private_root,
        toc_result=TocAgentResult(
            status="ready",
            entries=entries,
            page_offset=3,
            toc_physical_page_start=2,
            toc_physical_page_end=2,
        ),
        page_count=6,
        native_text={1: "Native searchable first page"},
    )

    outcome = await DocumentProcessingService(db_session).process_document(
        document.id,
        lease=lease,  # type: ignore[arg-type]
    )
    assert outcome.chunk_count == 3
    assert outcome.warning_code is None

    indexes = list(
        (
            await db_session.scalars(
                select(PdfVisualIndex)
                .where(PdfVisualIndex.document_id == document.id)
                .order_by(PdfVisualIndex.generation)
            )
        ).all()
    )
    assert [(index.generation, index.state, index.is_current) for index in indexes] == [
        (1, "superseded", False),
        (2, "published", True),
    ]
    current = indexes[1]
    assert current.page_offset == 3
    assert current.toc_pdf_page_start == 2
    assert current.toc_pdf_page_end == 2
    assert current.outline_entries[0]["resolved_pdf_page"] == 4

    new_chunks = list(
        (
            await db_session.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.pdf_visual_index_id == current.id)
                .order_by(DocumentChunk.chunk_index)
            )
        ).all()
    )
    assert [chunk.chunk_kind for chunk in new_chunks] == [
        "native_page",
        "outline_entry",
        "outline_entry",
    ]
    assert new_chunks[0].physical_page_start == 1
    assert new_chunks[1].physical_page_start == 4
    assert new_chunks[1].chunk_metadata["printed_page_number"] == 1
    assert new_chunks[2].physical_page_start is None
    assert await db_session.get(DocumentChunk, old_chunk.id) is not None

    doc_texts = list(
        (
            await db_session.scalars(
                select(DocumentText).where(DocumentText.document_id == document.id)
            )
        ).all()
    )
    assert len(doc_texts) == 1
    assert "page_offset: `3`" in doc_texts[0].content
    assert "PDF physical page `4`" in doc_texts[0].content


@pytest.mark.asyncio
async def test_final_vlm_failure_still_publishes_visual_assets_with_warning(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document, _, lease, upload_root, _ = await _seed_document_and_task(
        db_session, tmp_path, generation=1
    )
    lease.attempt = rag_service.settings.pdf_processing_max_attempts
    private_root = tmp_path / "private-rag"
    _install_pipeline_stubs(
        monkeypatch,
        upload_root=upload_root,
        private_root=private_root,
        toc_result=TocAgentResult(
            status="failed",
            error_code="toc_vlm_failed",
            error_detail="provider unavailable",
        ),
        page_count=1,
    )

    outcome = await DocumentProcessingService(db_session).process_document(
        document.id,
        lease=lease,  # type: ignore[arg-type]
    )

    assert outcome.chunk_count == 0
    assert outcome.warning_code == "pdf_outline_failed"
    index = await db_session.scalar(
        select(PdfVisualIndex).where(PdfVisualIndex.document_id == document.id)
    )
    assert index is not None
    assert index.state == "published"
    assert index.is_current is True
    assert index.outline_status == "failed"
    assert index.page_offset is None
    assets = (
        await db_session.scalars(
            select(PdfPageAsset).where(PdfPageAsset.index_id == index.id)
        )
    ).all()
    assert len(assets) == expected_asset_count(1)


@pytest.mark.asyncio
async def test_real_renderer_and_toc_agent_publish_four_page_pdf_end_to_end(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fitz = pytest.importorskip("fitz")
    pil_image = pytest.importorskip("PIL.Image")
    document, _, lease, upload_root, source_path = await _seed_document_and_task(
        db_session, tmp_path, generation=1
    )
    pdf = fitz.open()
    page = pdf.new_page(width=240, height=320)
    page.insert_text((24, 40), "Contents")
    page.insert_text((24, 72), "Introduction ........ 1")
    for printed_page in range(1, 4):
        page = pdf.new_page(width=240, height=320)
        page.insert_text((24, 40), f"Introduction content page {printed_page}")
        page.insert_text((115, 300), str(printed_page))
    source_path.unlink()
    pdf.save(source_path)
    pdf.close()

    private_root = tmp_path / "private-rag"
    monkeypatch.setattr(rag_service.settings, "upload_dir", str(upload_root))
    monkeypatch.setattr(rag_service.settings, "pdf_private_dir", str(private_root))
    monkeypatch.setattr(rag_service.settings, "pdf_agentic_enabled", True)
    monkeypatch.setattr(rag_service.settings, "pdf_max_pages", 20)
    monkeypatch.setattr(rag_service.settings, "pdf_render_dpi", 72)
    monkeypatch.setattr(rag_service.settings, "pdf_render_max_pixels", 200_000)
    monkeypatch.setattr(rag_service.settings, "pdf_webp_quality", 85)
    monkeypatch.setattr(rag_service.settings, "pdf_max_image_bytes", 500_000)
    monkeypatch.setattr(rag_service.settings, "pdf_lod_max_side", 512)
    monkeypatch.setattr(rag_service.settings, "pdf_max_derived_bytes", 10_000_000)
    monkeypatch.setattr(rag_service.settings, "pdf_min_free_disk_bytes", 0)
    monkeypatch.setattr(rag_service.settings, "pdf_toc_scan_max_pages", 4)
    monkeypatch.setattr(rag_service.settings, "pdf_toc_max_pages", 4)
    monkeypatch.setattr(rag_service.settings, "pdf_toc_agent_max_rounds", 4)
    monkeypatch.setattr(rag_service.settings, "rag_media_max_images", 4)
    monkeypatch.setattr(rag_service.settings, "dashscope_api_key", "test-key")

    @asynccontextmanager
    async def scoped_test_session():
        yield db_session

    monkeypatch.setattr(rag_service, "get_scoped_session", scoped_test_session)
    call_keys: list[str] = []

    async def mock_complete(
        self: Any,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        enable_thinking: bool | None = None,
        usage_context: Any | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        del self, temperature, max_tokens, enable_thinking, usage_context
        assert idempotency_key is not None
        call_keys.append(idempotency_key)
        prompt = messages[1]["content"][0]["text"]
        if "Locate the document's table of contents" in prompt:
            return '{"status":"found","toc_start":1,"toc_end":1,"requests":[]}'
        if "physical page 1" in prompt:
            return (
                '{"entries":[{"title":"Introduction","level":1,'
                '"printed_page_label":"1","printed_page_number":1}],'
                '"continues":false}'
            )
        if "post-TOC content pages" in prompt:
            return (
                '{"anchors":[{"printed_page_number":1,"physical_pdf_page":2},'
                '{"printed_page_number":2,"physical_pdf_page":3}]}'
            )
        raise AssertionError(f"unexpected VLM prompt: {prompt}")

    monkeypatch.setattr(agents.llm.LLMClient, "complete", mock_complete)

    outcome = await DocumentProcessingService(db_session).process_document(
        document.id,
        lease=lease,  # type: ignore[arg-type]
    )

    assert outcome.warning_code is None
    index = await db_session.scalar(
        select(PdfVisualIndex).where(PdfVisualIndex.document_id == document.id)
    )
    assert index is not None
    assert index.state == "published"
    assert index.page_count == 4
    assert index.page_offset == 1
    assert index.outline_entries[0]["resolved_pdf_page"] == 2
    assets = list(
        (
            await db_session.scalars(
                select(PdfPageAsset)
                .where(PdfPageAsset.index_id == index.id)
                .order_by(
                    PdfPageAsset.pages_per_image,
                    PdfPageAsset.physical_page_start,
                )
            )
        ).all()
    )
    assert len(assets) == expected_asset_count(4) == 7
    for asset in assets:
        with pil_image.open(private_root / asset.storage_key) as decoded:
            assert decoded.format == "WEBP"
            decoded.verify()
    final_root = private_root / str(document.space_id) / str(document.id) / "v000001"
    reloaded = pdf_agentic.load_render_manifest(final_root)
    assert reloaded.asset_count == 7
    assert "PDF physical page `2`" in (final_root / "outline.md").read_text(
        encoding="utf-8"
    )
    checkpoints = (
        await db_session.scalars(
            select(PdfIndexAgentCall).where(PdfIndexAgentCall.index_id == index.id)
        )
    ).all()
    assert len(checkpoints) == 3
    assert len(call_keys) == 3
    assert all(key.startswith(f"pdf-index:{document.id}:1:") for key in call_keys)


@pytest.mark.asyncio
@pytest.mark.parametrize("fence_kind", ["wrong_token", "expired"])
async def test_publish_rejects_stale_or_expired_lease_before_switching_current(
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fence_kind: str,
) -> None:
    expired = fence_kind == "expired"
    document, task, lease, _, source_path = await _seed_document_and_task(
        db_session,
        tmp_path,
        generation=2,
        lease_expires_at=(
            datetime.now(timezone.utc) - timedelta(seconds=1)
            if expired
            else datetime.now(timezone.utc) + timedelta(minutes=5)
        ),
    )
    private_root = tmp_path / "private-rag"
    monkeypatch.setattr(rag_service.settings, "pdf_private_dir", str(private_root))
    monkeypatch.setattr(rag_service.settings, "pdf_max_derived_bytes", 10_000_000)
    old_index = PdfVisualIndex(
        document_id=document.id,
        space_id=document.space_id,
        generation=1,
        state="published",
        is_current=True,
        source_sha256="a" * 64,
        page_count=1,
        outline_status="not_found",
        renderer_version="agentic-pdf-v1",
    )
    staged = PdfVisualIndex(
        document_id=document.id,
        space_id=document.space_id,
        generation=2,
        state="staging",
        is_current=False,
        source_sha256="b" * 64,
        page_count=1,
        outline_status="pending",
        renderer_version="agentic-pdf-v1",
    )
    db_session.add_all([old_index, staged])
    await db_session.commit()
    old_index_id = old_index.id
    staged_index_id = staged.id
    task_id = task.id

    final_root = private_root / str(document.space_id) / str(document.id) / "v000002"
    manifest = _write_fake_render(final_root, page_count=1)
    _, outline_path = write_outline_artifacts(
        final_root,
        (),
        toc_physical_page_start=None,
        toc_physical_page_end=None,
        page_offset=None,
    )
    sentinel = final_root / "published-sentinel.bin"
    sentinel.write_bytes(b"must-survive-stale-worker")
    if fence_kind == "wrong_token":
        lease.lease_token = uuid.uuid4()

    with pytest.raises(LeaseLostError):
        await DocumentProcessingService(db_session)._publish_pdf_index(
            document=document,
            lease=lease,  # type: ignore[arg-type]
            visual_index_id=staged_index_id,
            source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
            manifest=manifest,
            toc_result=TocAgentResult(status="not_found"),
            final_root=final_root,
            outline_markdown=outline_path,
        )
    await db_session.rollback()
    db_session.expire_all()
    unchanged_old = await db_session.get(PdfVisualIndex, old_index_id)
    unchanged_staged = await db_session.get(PdfVisualIndex, staged_index_id)
    unchanged_task = await db_session.get(DocumentProcessingTask, task_id)
    assert unchanged_old is not None and unchanged_old.is_current is True
    assert unchanged_old.state == "published"
    assert unchanged_staged is not None and unchanged_staged.is_current is False
    assert unchanged_staged.state == "staging"
    assert unchanged_task is not None
    assert unchanged_task.status == ProcessingStatus.PROCESSING
    assert sentinel.read_bytes() == b"must-survive-stale-worker"
    assert not (
        await db_session.scalars(
            select(PdfPageAsset).where(PdfPageAsset.index_id == staged_index_id)
        )
    ).all()
