"""Tests for DocumentText and DocumentImage ORM models."""

from db.models import DocumentChunk, DocumentText, DocumentImage


def test_document_chunk_matches_plaintext_rag_schema():
    """DocumentChunk must not map the removed pgvector embedding column."""
    columns = {col.name for col in DocumentChunk.__table__.columns}
    assert "embedding" not in columns


def test_document_text_has_required_fields():
    """DocumentText model must have all required fields."""
    model = DocumentText
    columns = {col.name for col in model.__table__.columns}
    assert "id" in columns
    assert "document_id" in columns
    assert "space_id" in columns
    assert "content" in columns
    assert "content_tsv" in columns
    assert "word_count" in columns
    assert "created_at" in columns


def test_document_image_has_required_fields():
    """DocumentImage model must have all required fields."""
    model = DocumentImage
    columns = {col.name for col in model.__table__.columns}
    assert "id" in columns
    assert "document_id" in columns
    assert "space_id" in columns
    assert "page_num" in columns
    assert "image_index" in columns
    assert "file_path" in columns
    assert "vlm_description" in columns
