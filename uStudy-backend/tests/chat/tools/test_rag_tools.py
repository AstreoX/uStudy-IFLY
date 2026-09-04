"""Tests for updated RAG tool definitions."""

import base64
import hashlib
import importlib.util
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest


def _load_rag_tools_without_global_module_pollution():
    """Load the leaf module with temporary stubs, then restore sys.modules."""

    backend_root = Path(__file__).parents[3]
    module_names = (
        "db",
        "db.database",
        "chat",
        "chat.tools",
        "chat.tools.base",
        "rag",
        "rag.retrieval",
        "rag.retrieval.text_search",
    )
    missing = object()
    originals = {name: sys.modules.get(name, missing) for name in module_names}
    try:
        db_package = types.ModuleType("db")
        db_package.__path__ = []  # type: ignore[attr-defined]
        sys.modules["db"] = db_package
        db_database = types.ModuleType("db.database")
        db_database.get_scoped_session = lambda: None  # type: ignore[attr-defined]
        sys.modules["db.database"] = db_database

        chat_package = types.ModuleType("chat")
        chat_package.__path__ = []  # type: ignore[attr-defined]
        tools_package = types.ModuleType("chat.tools")
        tools_package.__path__ = []  # type: ignore[attr-defined]
        sys.modules["chat"] = chat_package
        sys.modules["chat.tools"] = tools_package
        base_spec = importlib.util.spec_from_file_location(
            "chat.tools.base", backend_root / "chat" / "tools" / "base.py"
        )
        assert base_spec is not None and base_spec.loader is not None
        base_module = importlib.util.module_from_spec(base_spec)
        sys.modules["chat.tools.base"] = base_module
        base_spec.loader.exec_module(base_module)

        rag_package = types.ModuleType("rag")
        rag_package.__path__ = []  # type: ignore[attr-defined]
        retrieval_package = types.ModuleType("rag.retrieval")
        retrieval_package.__path__ = []  # type: ignore[attr-defined]
        text_search = types.ModuleType("rag.retrieval.text_search")
        text_search.TextSearchService = object  # type: ignore[attr-defined]
        text_search.resolve_images = lambda _content: []  # type: ignore[attr-defined]
        sys.modules["rag"] = rag_package
        sys.modules["rag.retrieval"] = retrieval_package
        sys.modules["rag.retrieval.text_search"] = text_search

        spec = importlib.util.spec_from_file_location(
            "rag_tools_under_test", backend_root / "chat" / "tools" / "rag_tools.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in originals.items():
            if original is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


_rag_tools_mod = _load_rag_tools_without_global_module_pollution()

RAG_TOOLS = _rag_tools_mod.RAG_TOOLS


def test_rag_tools_has_agentic_pdf_tools():
    tool_names = {t["function"]["name"] for t in RAG_TOOLS}
    assert tool_names == {
        "search_keywords",
        "search_regex",
        "list_documents",
        "read_document",
        "get_document_outline",
        "view_document_pages",
        "view_document_page",
    }
    assert _rag_tools_mod.RAG_TOOL_NAMES == tool_names


def test_search_keywords_has_required_params():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "search_keywords")
    params = tool["function"]["parameters"]["properties"]
    assert "query" in params
    assert "top_k" in params
    assert "query" in tool["function"]["parameters"]["required"]


def test_search_regex_has_pattern_param():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "search_regex")
    params = tool["function"]["parameters"]["properties"]
    assert "pattern" in params
    assert "pattern" in tool["function"]["parameters"]["required"]


@pytest.mark.parametrize(
    "pattern",
    ["(a+)+$", "(.*)*", ".*a.*b.*c", r"(a)\1", "x" * 257],
)
def test_regex_guard_rejects_high_cost_patterns(pattern):
    assert _rag_tools_mod._regex_validation_error(pattern)


def test_regex_guard_accepts_bounded_useful_pattern():
    assert _rag_tools_mod._regex_validation_error(r"第[一二三四]章\s+树") is None


def test_list_documents_has_no_required_params():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "list_documents")
    required = tool["function"]["parameters"].get("required", [])
    assert required == []


def test_read_document_requires_doc_id():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "read_document")
    assert "document_id" in tool["function"]["parameters"]["required"]


@pytest.mark.asyncio
@pytest.mark.parametrize("length", [-1, 0, 8001])
async def test_read_document_rejects_length_limit_bypass(length):
    result = await _rag_tools_mod.RAGToolExecutor(uuid4()).execute(
        "read_document",
        {"document_id": str(uuid4()), "length_chars": length},
    )
    assert result.success is False
    assert "1 到 8000" in result.message


def test_image_metadata_omits_base64(tmp_path):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"fake-image-bytes")

    result = _rag_tools_mod._encode_image(
        {
            "image_id": "img-1",
            "document_id": "doc-1",
            "file_path": str(image_path),
            "vlm_description": "chart",
            "page_num": 3,
        }
    )

    assert result == {
        "image_id": "img-1",
        "document_id": "doc-1",
        "page_num": 3,
        "vlm_description": "chart",
    }
    assert "base64" not in result


def test_view_document_page_requires_doc_id_and_page():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "view_document_page")
    required = set(tool["function"]["parameters"]["required"])
    assert required == {"document_id", "page_number"}


def test_get_document_outline_has_bounded_pagination_schema():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "get_document_outline")
    properties = tool["function"]["parameters"]["properties"]
    assert set(properties) == {"document_id", "offset", "limit"}
    assert tool["function"]["parameters"]["required"] == ["document_id"]


def test_view_document_pages_uses_explicit_physical_page_and_lod():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "view_document_pages")
    params = tool["function"]["parameters"]
    assert set(params["required"]) == {
        "document_id",
        "physical_page",
        "pages_per_image",
    }
    assert params["properties"]["pages_per_image"]["enum"] == [1, 2, 4]


@pytest.mark.parametrize(
    ("page", "lod", "expected"),
    [(1, 4, 1), (4, 4, 1), (5, 4, 5), (2, 2, 1), (3, 2, 3), (9, 1, 9)],
)
def test_page_alignment_returns_group_containing_target(page, lod, expected):
    assert _rag_tools_mod._aligned_asset_start(page, lod) == expected


def test_private_asset_path_rejects_traversal(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    asset = root / "safe.webp"
    asset.write_bytes(b"webp")

    assert (
        _rag_tools_mod._resolve_private_asset_path(root, "safe.webp") == asset.resolve()
    )
    with pytest.raises(ValueError, match="outside"):
        _rag_tools_mod._resolve_private_asset_path(root, "../outside.webp")


def test_render_pdf_page_returns_png_and_text(tmp_path):
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "sample.pdf"

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Database Systems Concepts")
    pdf.save(pdf_path)
    pdf.close()

    rendered = _rag_tools_mod._render_pdf_page_sync(pdf_path, 1)

    assert rendered["page_count"] == 1
    assert rendered["image_bytes"].startswith(b"\x89PNG")
    assert "Database Systems Concepts" in rendered["page_text_excerpt"]


def test_render_pdf_page_rejects_out_of_range(tmp_path):
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "sample.pdf"

    pdf = fitz.open()
    pdf.new_page()
    pdf.save(pdf_path)
    pdf.close()

    with pytest.raises(ValueError, match="页码越界"):
        _rag_tools_mod._render_pdf_page_sync(pdf_path, 2)


@pytest.mark.asyncio
async def test_view_document_pages_reads_aligned_private_assets_without_serializing_media(
    db_session, monkeypatch, tmp_path
):
    from config import get_settings
    from db.models import (
        DocumentImage,
        DocumentText,
        DocumentType,
        PdfPageAsset,
        PdfVisualIndex,
        Space,
        SpaceDocument,
        User,
    )

    user = User(email=f"rag-tool-{uuid4().hex}@example.com", nickname="RAG Tool")
    db_session.add(user)
    await db_session.flush()
    space = Space(user_id=user.id, name="Agentic PDF", color="#123456")
    db_session.add(space)
    await db_session.flush()
    document = SpaceDocument(
        space_id=space.id,
        doc_type=DocumentType.DOCUMENT,
        title="Textbook",
        url="/uploads/documents/textbook.pdf",
        original_filename="textbook.pdf",
        mime_type="application/pdf",
        creator_user_id=user.id,
    )
    db_session.add(document)
    await db_session.flush()
    visual_index = PdfVisualIndex(
        document_id=document.id,
        space_id=space.id,
        generation=1,
        state="published",
        is_current=True,
        source_sha256="a" * 64,
        page_count=8,
        outline_status="ready",
        page_offset=3,
        outline_entries=[
            {
                "title": "Chapter One",
                "level": 1,
                "printed_page_label": "1",
                "printed_page_number": 1,
                "resolved_pdf_page": 4,
            }
        ],
        derived_bytes=10,
        renderer_version="agentic-pdf-v1",
    )
    db_session.add(visual_index)
    await db_session.flush()

    private_root = tmp_path / "private-rag"
    for start in (1, 5):
        payload = f"webp-{start}".encode()
        key = f"{space.id}/{document.id}/v000001/pages/4/{start}.webp"
        path = private_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        db_session.add(
            PdfPageAsset(
                index_id=visual_index.id,
                document_id=document.id,
                space_id=space.id,
                pages_per_image=4,
                physical_page_start=start,
                physical_page_end=start + 3,
                storage_key=key,
                mime_type="image/webp",
                width=100,
                height=100,
                byte_size=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        )

    other_user = User(email=f"other-{uuid4().hex}@example.com", nickname="Other")
    db_session.add(other_user)
    await db_session.flush()
    other_space = Space(user_id=other_user.id, name="Other Space", color="#654321")
    db_session.add(other_space)
    await db_session.flush()
    other_document = SpaceDocument(
        space_id=other_space.id,
        doc_type=DocumentType.DOCUMENT,
        title="Private other document",
        url="/uploads/documents/other.txt",
        mime_type="text/plain",
        creator_user_id=other_user.id,
    )
    db_session.add(other_document)
    await db_session.flush()
    foreign_image = DocumentImage(
        document_id=other_document.id,
        space_id=other_space.id,
        image_index=0,
        file_path="private-other.png",
        vlm_description="must not leak",
    )
    db_session.add(foreign_image)
    await db_session.flush()
    db_session.add(
        DocumentText(
            document_id=document.id,
            space_id=space.id,
            content=f"local text [IMAGE:{foreign_image.id}]",
            word_count=2,
        )
    )
    await db_session.commit()

    @asynccontextmanager
    async def scoped_session():
        yield db_session

    monkeypatch.setattr(_rag_tools_mod, "get_scoped_session", scoped_session)
    monkeypatch.setattr(get_settings(), "pdf_private_dir", str(private_root))
    result = await _rag_tools_mod.RAGToolExecutor(space.id).execute(
        "view_document_pages",
        {
            "document_id": str(document.id),
            "physical_page": 4,
            "pages_per_image": 4,
            "count": 2,
        },
    )

    assert result.success is True
    assert [
        (item.physical_page_start, item.physical_page_end) for item in result.media
    ] == [
        (1, 4),
        (5, 8),
    ]
    assert base64.b64decode(result.media[0].base64_data) == b"webp-1"
    assert "media" not in result.to_dict()
    assert "base64" not in str(result.to_dict()).lower()

    outline = await _rag_tools_mod.RAGToolExecutor(space.id).execute(
        "get_document_outline",
        {"document_id": str(document.id), "offset": 0, "limit": 10},
    )
    assert outline.success is True
    assert outline.data["page_offset"] == 3
    assert outline.data["printed_page_1_pdf_page"] == 4
    assert outline.data["entries"][0]["resolved_pdf_page"] == 4

    document_read = await _rag_tools_mod.RAGToolExecutor(space.id).execute(
        "read_document",
        {"document_id": str(document.id), "length_chars": 8000},
    )
    assert document_read.success is True
    assert document_read.data["images"] == []

    denied = await _rag_tools_mod.RAGToolExecutor(uuid4()).execute(
        "view_document_pages",
        {
            "document_id": str(document.id),
            "physical_page": 1,
            "pages_per_image": 4,
        },
    )
    assert denied.success is False
    assert denied.data["code"] == "pdf_visual_index_not_ready"
