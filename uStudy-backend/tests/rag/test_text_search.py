"""Tests for TextSearchService."""

import uuid
from types import SimpleNamespace
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
    sql = str(mock_db.execute.await_args.args[0])
    assert "JOIN pdf_visual_indexes" in sql
    assert "current_pdf.id IS NULL" in sql


@pytest.mark.asyncio
async def test_search_returns_active_pdf_chunk_page_metadata():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    result_id = uuid.uuid4()
    document_id = uuid.uuid4()
    mock_result.fetchall.return_value = [
        SimpleNamespace(
            result_id=result_id,
            document_id=document_id,
            content="Binary trees PDF physical page 12",
            score=0.08,
            document_title="Data Structures",
            document_filename="textbook.pdf",
            chunk_kind="outline_entry",
            physical_page_start=12,
            physical_page_end=12,
            legacy_text=False,
        )
    ]
    mock_db.execute.return_value = mock_result

    result = (
        await TextSearchService(mock_db).search(
            query="Binary trees",
            space_id=uuid.uuid4(),
            top_k=5,
        )
    )[0]

    assert result.chunk_id == result_id
    assert result.document_id == document_id
    assert result.metadata["chunk_kind"] == "outline_entry"
    assert result.metadata["page_number"] == 12
    assert result.metadata["page_end"] == 12
    assert result.retrieval_source == "text"


@pytest.mark.asyncio
async def test_image_lookup_is_scoped_to_request_space():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute.return_value = mock_result
    space_id = uuid.uuid4()

    await TextSearchService(mock_db)._fetch_images(
        {str(uuid.uuid4())}, space_id=space_id
    )

    params = mock_db.execute.await_args.args[1]
    assert params["space_id"] == str(space_id)
    assert "space_id = :space_id" in str(mock_db.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_regex_search_sets_timeout_and_stable_cross_source_order():
    mock_db = AsyncMock()
    mock_db.get_bind = MagicMock(
        return_value=SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    )
    timeout_result = MagicMock()
    query_result = MagicMock()
    query_result.fetchall.return_value = []
    mock_db.execute.side_effect = [timeout_result, query_result]

    results = await TextSearchService(mock_db).search_regex(
        pattern=r"Chapter\s+[0-9]+",
        space_id=uuid.uuid4(),
        max_results=10,
    )

    assert results == []
    assert "statement_timeout" in str(mock_db.execute.await_args_list[0].args[0])
    regex_sql = str(mock_db.execute.await_args_list[1].args[0])
    assert "ROW_NUMBER() OVER" in regex_sql
    assert "ORDER BY source_rank, legacy_text" in regex_sql
