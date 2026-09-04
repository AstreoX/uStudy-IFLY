"""Tests for updated SearchResult dataclass."""
import uuid
from rag.retrieval.base import SearchResult


def test_search_result_has_images_field():
    """SearchResult must have an images field defaulting to empty list."""
    result = SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="test content",
        score=0.9,
        metadata={},
        document_title="Test Doc",
        document_filename="test.pdf",
    )
    assert hasattr(result, "images")
    assert result.images == []


def test_search_result_images_can_hold_dicts():
    """images field should accept list of dicts."""
    img = {"image_id": str(uuid.uuid4()), "file_path": "/uploads/img.png", "vlm_description": "A chart"}
    result = SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="test",
        score=0.5,
        metadata={},
        document_title=None,
        document_filename=None,
        images=[img],
    )
    assert len(result.images) == 1
    assert result.images[0]["file_path"] == "/uploads/img.png"
