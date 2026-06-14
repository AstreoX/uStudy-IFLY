"""Tests for document format resolution and legacy normalization."""

import io
import zipfile
from unittest.mock import patch

import pytest

from rag.parsing import (
    DocumentFormatError,
    LegacyDocumentNormalizationError,
    normalize_legacy_document,
    resolve_document_format,
)
from rag.parsing.formats import OLE_MAGIC


def _build_zip(entries: dict[str, str | bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("filename", "claimed_mime", "entries", "expected_type"),
    [
        (
            "report.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            {
                "[Content_Types].xml": "<Types/>",
                "word/document.xml": "<w:document/>",
            },
            "docx",
        ),
        (
            "sheet.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            {
                "[Content_Types].xml": "<Types/>",
                "xl/workbook.xml": "<workbook/>",
            },
            "xlsx",
        ),
        (
            "deck.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            {
                "[Content_Types].xml": "<Types/>",
                "ppt/presentation.xml": "<presentation/>",
            },
            "pptx",
        ),
        (
            "book.epub",
            "application/epub+zip",
            {
                "mimetype": "application/epub+zip",
                "META-INF/container.xml": "<container/>",
                "OEBPS/ch1.xhtml": "<html><body>chapter</body></html>",
            },
            "epub",
        ),
    ],
)
def test_resolve_zip_documents(
    filename: str,
    claimed_mime: str,
    entries: dict[str, str | bytes],
    expected_type: str,
):
    resolved = resolve_document_format(_build_zip(entries), filename, claimed_mime)
    assert resolved.canonical_type == expected_type
    assert resolved.needs_normalization is False


@pytest.mark.parametrize(
    ("filename", "claimed_mime", "expected_type"),
    [
        ("legacy.doc", "application/msword", "docx"),
        ("legacy.xls", "application/vnd.ms-excel", "xlsx"),
        ("legacy.ppt", "application/vnd.ms-powerpoint", "pptx"),
    ],
)
def test_resolve_legacy_ole_documents(
    filename: str,
    claimed_mime: str,
    expected_type: str,
):
    resolved = resolve_document_format(OLE_MAGIC + (b"\x00" * 128), filename, claimed_mime)
    assert resolved.canonical_type == expected_type
    assert resolved.needs_normalization is True


@pytest.mark.parametrize(
    ("filename", "claimed_mime", "payload", "expected_type"),
    [
        ("notes.txt", "text/plain", "plain text", "text"),
        ("README.md", "application/octet-stream", "# title\n\nbody", "markdown"),
        ("page.html", "text/html", "<html><body>Hello</body></html>", "html"),
        ("table.csv", "text/csv", "a,b\n1,2\n", "csv"),
        ("", "text/plain", "fallback text", "text"),
    ],
)
def test_resolve_text_documents(
    filename: str,
    claimed_mime: str,
    payload: str,
    expected_type: str,
):
    resolved = resolve_document_format(payload.encode("utf-8"), filename, claimed_mime)
    assert resolved.canonical_type == expected_type


def test_resolve_gbk_text_document():
    payload = "这是一个测试文档".encode("gbk")
    resolved = resolve_document_format(payload, "lesson.txt", "text/plain")
    assert resolved.canonical_type == "text"


def test_resolve_unknown_binary_raises():
    with pytest.raises(DocumentFormatError):
        resolve_document_format(b"\x01\x02\x03\x04\x05", "mystery.xyz", "application/xyz")


def test_normalize_legacy_doc_falls_back_to_pdf():
    resolved = resolve_document_format(OLE_MAGIC + (b"\x00" * 128), "legacy.doc", "application/msword")

    with patch(
        "rag.parsing.formats._convert_with_libreoffice",
        side_effect=[
            LegacyDocumentNormalizationError("docx convert failed"),
            b"%PDF-1.4 fake pdf",
        ],
    ):
        normalized = normalize_legacy_document(
            OLE_MAGIC + (b"\x00" * 128),
            resolved,
            "legacy.doc",
        )

    assert normalized.resolved_format.canonical_type == "pdf"
    assert normalized.filename.endswith(".pdf")


def test_normalize_legacy_xls_requires_structured_conversion():
    resolved = resolve_document_format(OLE_MAGIC + (b"\x00" * 128), "legacy.xls", "application/vnd.ms-excel")

    with patch(
        "rag.parsing.formats._convert_with_libreoffice",
        side_effect=LegacyDocumentNormalizationError("xlsx convert failed"),
    ):
        with pytest.raises(LegacyDocumentNormalizationError):
            normalize_legacy_document(
                OLE_MAGIC + (b"\x00" * 128),
                resolved,
                "legacy.xls",
            )
