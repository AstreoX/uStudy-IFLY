"""Tests for TextSearchService."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.retrieval.text_search import TextSearchService, extract_excerpt, resolve_images


# ── extract_excerpt ──────────────────────────────────────────────────────────

def test_extract_excerpt_returns_surrounding_context():
    text = "A" * 100 + "TARGET" + "B" * 100
    excerpt = extract_excerpt(text, "TARGET", context_chars=50)
    assert "TARGET" in excerpt
    assert len(excerpt) <= 110  # 50 + len("TARGET") + 50 + some slack


def test_extract_excerpt_handles_missing_keyword():
    text = "Hello world this is content."
    excerpt = extract_excerpt(text, "NOTFOUND", context_chars=50)
    assert excerpt.startswith("Hello")
    assert len(excerpt) <= 200


def test_extract_excerpt_clamps_to_text_boundaries():
    text = "Short text here."
    excerpt = extract_excerpt(text, "Short", context_chars=500)
    assert excerpt == text


# ── resolve_images ───────────────────────────────────────────────────────────

def test_resolve_images_extracts_image_uuids():
    content = "Some text [IMAGE:abc-123] more text [IMAGE:def-456] end"
    uuids = resolve_images(content)
    assert uuids == ["abc-123", "def-456"]


def test_resolve_images_returns_empty_for_no_placeholders():
    content = "Plain text without any image placeholders."
    assert resolve_images(content) == []


# ── TextSearchService.search (mocked DB) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_search_returns_empty_when_no_rows():
    """search() returns [] when the DB query yields no rows."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_result

    service = TextSearchService(mock_db)
    results = await service.search(
        query="neural networks",
        space_id=uuid.uuid4(),
        top_k=5,
    )
    assert results == []
