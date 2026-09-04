"""Tests for ImageExtractor."""
from unittest.mock import patch

import pytest

from rag.image_extractor import ExtractedImage, ImageExtractor


def test_extracted_image_dataclass():
    """ExtractedImage must hold image_bytes, page_num, image_index."""
    img = ExtractedImage(image_bytes=b"PNG", page_num=1, image_index=0)
    assert img.image_bytes == b"PNG"
    assert img.page_num == 1
    assert img.image_index == 0


@patch("rag.image_extractor.fitz", None)
def test_extract_pdf_returns_empty_when_fitz_unavailable():
    """extract_from_pdf should return [] gracefully when PyMuPDF is missing."""
    extractor = ImageExtractor()
    result = extractor.extract_from_pdf(b"fake pdf bytes")
    assert result == []


def test_extract_from_unsupported_mime_returns_empty():
    """Unknown MIME type returns empty list without raising."""
    extractor = ImageExtractor()
    result = extractor.extract(b"some data", mime_type="text/plain")
    assert result == []
