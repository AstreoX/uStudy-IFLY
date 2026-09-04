"""Schema-level tests for the durable PDF Agentic RAG index."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from db.models import (
    DocumentChunk,
    DocumentProcessingTask,
    DocumentType,
    PdfIndexAgentCall,
    PdfPageAsset,
    PdfVisualIndex,
    ProcessingStatus,
    Space,
    SpaceDocument,
    User,
)
from rag.tasks import enqueue_document_processing


def test_pdf_agentic_settings_have_safe_defaults():
    settings = Settings(_env_file=None)

    assert settings.pdf_agentic_enabled is True
    assert settings.pdf_private_dir == "private-rag"
    assert settings.pdf_max_pages == 1500
    assert settings.pdf_render_dpi == 160
    assert settings.pdf_render_max_pixels == 8_000_000
    assert settings.pdf_webp_quality == 85
    assert settings.pdf_max_image_bytes == 4 * 1024 * 1024
    assert settings.pdf_lod_max_side == 2048
    assert settings.pdf_max_derived_bytes == 2 * 1024 * 1024 * 1024
    assert settings.pdf_min_free_disk_bytes == 5 * 1024 * 1024 * 1024
    assert settings.pdf_toc_scan_max_pages == 96
    assert settings.pdf_toc_max_pages == 64
    assert settings.pdf_toc_agent_max_rounds == 16
    assert settings.pdf_processing_lease_seconds == 300
    assert settings.pdf_processing_max_attempts == 4
    assert settings.pdf_processing_max_concurrent_jobs == 1
    assert settings.pdf_staging_retention_seconds == 86400
    assert settings.rag_media_max_images == 4
    assert settings.rag_media_max_bytes == 8 * 1024 * 1024


def test_processing_task_has_generation_progress_and_lease_columns():
    columns = set(DocumentProcessingTask.__table__.columns.keys())

    assert {
        "generation",
        "stage",
        "page_count",
        "processed_pages",
        "asset_count",
        "attempt_count",
        "available_at",
        "lease_owner",
        "lease_token",
        "lease_expires_at",
        "error_code",
        "warning_code",
        "updated_at",
    } <= columns


def test_pdf_visual_models_expose_required_columns_and_constraints():
    visual_columns = set(PdfVisualIndex.__table__.columns.keys())
    asset_columns = set(PdfPageAsset.__table__.columns.keys())
    call_columns = set(PdfIndexAgentCall.__table__.columns.keys())
    chunk_columns = set(DocumentChunk.__table__.columns.keys())

    assert {
        "document_id",
        "space_id",
        "generation",
        "state",
        "is_current",
        "source_sha256",
        "page_count",
        "outline_status",
        "toc_pdf_page_start",
        "toc_pdf_page_end",
        "page_offset",
        "outline_entries",
        "outline_markdown_path",
        "derived_bytes",
        "renderer_version",
        "created_at",
        "published_at",
    } <= visual_columns
    assert {
        "index_id",
        "document_id",
        "space_id",
        "pages_per_image",
        "physical_page_start",
        "physical_page_end",
        "storage_key",
        "mime_type",
        "width",
        "height",
        "byte_size",
        "sha256",
    } <= asset_columns
    assert {
        "index_id",
        "call_key",
        "operation",
        "round_index",
        "input_sha256",
        "model",
        "status",
        "response_data",
        "response_text",
        "error",
    } <= call_columns
    assert {
        "pdf_visual_index_id",
        "chunk_kind",
        "physical_page_start",
        "physical_page_end",
    } <= chunk_columns

    constraint_names = {
        constraint.name for constraint in PdfPageAsset.__table__.constraints
    }
    assert "uq_pdf_page_assets_index_lod_start" in constraint_names
    assert "ck_pdf_page_assets_pages_per_image" in constraint_names

    current_index = next(
        index
        for index in PdfVisualIndex.__table__.indexes
        if index.name == "uq_pdf_visual_indexes_current_document"
    )
    assert current_index.unique is True
    assert str(current_index.dialect_options["postgresql"]["where"]) == "is_current"


async def _create_document(db_session: AsyncSession) -> tuple[Space, SpaceDocument]:
    user = User(email="pdf-agentic@example.com", nickname="PDF Agentic")
    db_session.add(user)
    await db_session.flush()
    space = Space(user_id=user.id, name="PDF Space", color="#123456")
    db_session.add(space)
    await db_session.flush()
    document = SpaceDocument(
        space_id=space.id,
        doc_type=DocumentType.DOCUMENT,
        title="Scanned textbook",
        url="/uploads/textbook.pdf",
        original_filename="textbook.pdf",
        mime_type="application/pdf",
    )
    db_session.add(document)
    await db_session.flush()
    return space, document


@pytest.mark.asyncio
async def test_only_one_visual_index_can_be_current_per_document(
    db_session: AsyncSession,
):
    space, document = await _create_document(db_session)
    db_session.add(
        PdfVisualIndex(
            document_id=document.id,
            space_id=space.id,
            generation=1,
            state="published",
            is_current=True,
            source_sha256="a" * 64,
            page_count=10,
            outline_status="not_found",
            renderer_version="v1",
        )
    )
    await db_session.commit()

    db_session.add(
        PdfVisualIndex(
            document_id=document.id,
            space_id=space.id,
            generation=2,
            state="published",
            is_current=True,
            source_sha256="a" * 64,
            page_count=10,
            outline_status="ready",
            renderer_version="v1",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_page_asset_lod_constraint_and_agent_checkpoint(
    db_session: AsyncSession,
):
    space, document = await _create_document(db_session)
    visual_index = PdfVisualIndex(
        document_id=document.id,
        space_id=space.id,
        generation=1,
        source_sha256="b" * 64,
        page_count=5,
        renderer_version="v1",
    )
    db_session.add(visual_index)
    await db_session.flush()

    asset = PdfPageAsset(
        index_id=visual_index.id,
        document_id=document.id,
        space_id=space.id,
        pages_per_image=4,
        physical_page_start=1,
        physical_page_end=4,
        storage_key="documents/doc/generations/1/lod4/0001.webp",
        mime_type="image/webp",
        width=2048,
        height=2048,
        byte_size=1024,
        sha256="c" * 64,
    )
    checkpoint = PdfIndexAgentCall(
        index_id=visual_index.id,
        call_key="pdf-index:doc:1:locate:0:hash:model",
        operation="locate",
        round_index=0,
        input_sha256="d" * 64,
        model="mock-vlm",
        status="succeeded",
        response_data={"toc_start": 3},
    )
    db_session.add_all([asset, checkpoint])
    await db_session.commit()

    stored_asset = await db_session.scalar(select(PdfPageAsset))
    stored_call = await db_session.scalar(select(PdfIndexAgentCall))
    assert stored_asset is not None and stored_asset.pages_per_image == 4
    assert stored_call is not None and stored_call.response_data == {"toc_start": 3}

    db_session.add(
        PdfPageAsset(
            index_id=visual_index.id,
            document_id=document.id,
            space_id=space.id,
            pages_per_image=3,
            physical_page_start=5,
            physical_page_end=5,
            storage_key="documents/doc/generations/1/lod3/0005.webp",
            mime_type="image/webp",
            width=512,
            height=512,
            byte_size=512,
            sha256="e" * 64,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_durable_enqueue_reuses_task_and_advances_generation(
    db_session: AsyncSession,
):
    space, document = await _create_document(db_session)

    task = await enqueue_document_processing(db_session, document.id, dispatch=False)
    assert task.generation == 1
    assert task.stage == "queued"
    assert task.status == ProcessingStatus.PENDING
    assert task.processed_pages == 0
    assert task.asset_count == 0
    assert task.attempt_count == 0
    assert task.available_at is not None

    task.status = ProcessingStatus.PROCESSING
    task.stage = "rendering"
    task.processed_pages = 3
    task.asset_count = 5
    task.attempt_count = 2
    staged_index = PdfVisualIndex(
        document_id=document.id,
        space_id=space.id,
        generation=1,
        state="staging",
        is_current=False,
        source_sha256="f" * 64,
        page_count=3,
        outline_status="pending",
        renderer_version="v1",
    )
    db_session.add(staged_index)
    await db_session.commit()

    reprocessed = await enqueue_document_processing(
        db_session, document.id, dispatch=False
    )
    assert reprocessed.id == task.id
    assert reprocessed.generation == 2
    assert reprocessed.status == ProcessingStatus.PENDING
    assert reprocessed.stage == "queued"
    assert reprocessed.processed_pages == 0
    assert reprocessed.asset_count == 0
    assert reprocessed.attempt_count == 0
    await db_session.refresh(staged_index)
    assert staged_index.state == "failed"
