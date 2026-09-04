"""Tests for updated RAG tool definitions."""
import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest


def _load_rag_tools():
    """Load rag_tools.py directly, bypassing the chat.tools package __init__
    (which pulls in redis and other heavy deps not available in unit-test env).
    """
    # Stub minimal dependencies
    if "db" not in sys.modules:
        sys.modules["db"] = types.ModuleType("db")
    if "db.database" not in sys.modules:
        m = types.ModuleType("db.database")
        m.get_scoped_session = lambda: None  # type: ignore[attr-defined]
        sys.modules["db.database"] = m

    if "chat" not in sys.modules:
        sys.modules["chat"] = types.ModuleType("chat")
    if "chat.tools" not in sys.modules:
        sys.modules["chat.tools"] = types.ModuleType("chat.tools")
    if "chat.tools.base" not in sys.modules:

        @dataclass
        class _ToolResult:
            success: bool
            data: object
            message: str
            image_base64: str | None = None

        m = types.ModuleType("chat.tools.base")
        m.ToolResult = _ToolResult  # type: ignore[attr-defined]
        sys.modules["chat.tools.base"] = m

    if "rag" not in sys.modules:
        sys.modules["rag"] = types.ModuleType("rag")
    if "rag.retrieval" not in sys.modules:
        sys.modules["rag.retrieval"] = types.ModuleType("rag.retrieval")
    if "rag.retrieval.text_search" not in sys.modules:
        m = types.ModuleType("rag.retrieval.text_search")
        m.TextSearchService = object  # type: ignore[attr-defined]
        m.resolve_images = lambda x: []  # type: ignore[attr-defined]
        sys.modules["rag.retrieval.text_search"] = m

    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "chat" / "tools" / "rag_tools.py"
    )
    spec = importlib.util.spec_from_file_location("chat.tools.rag_tools", module_path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_rag_tools_mod = _load_rag_tools()
RAG_TOOLS = _rag_tools_mod.RAG_TOOLS


def test_rag_tools_has_five_tools():
    tool_names = {t["function"]["name"] for t in RAG_TOOLS}
    assert tool_names == {
        "search_keywords",
        "search_regex",
        "list_documents",
        "read_document",
        "view_document_page",
    }


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


def test_list_documents_has_no_required_params():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "list_documents")
    required = tool["function"]["parameters"].get("required", [])
    assert required == []


def test_read_document_requires_doc_id():
    tool = next(t for t in RAG_TOOLS if t["function"]["name"] == "read_document")
    assert "document_id" in tool["function"]["parameters"]["required"]


def test_image_metadata_omits_base64(tmp_path):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"fake-image-bytes")

    result = _rag_tools_mod._encode_image({
        "image_id": "img-1",
        "document_id": "doc-1",
        "file_path": str(image_path),
        "vlm_description": "chart",
        "page_num": 3,
    })

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
