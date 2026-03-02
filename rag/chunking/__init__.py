"""Chunking module for document segmentation."""

from rag.chunking.base import BaseChunker, Chunk
from rag.chunking.csv_chunker import CSVChunker
from rag.chunking.docx_chunker import DocxChunker
from rag.chunking.epub_chunker import EPUBChunker
from rag.chunking.excel_chunker import ExcelChunker
from rag.chunking.html_chunker import HTMLChunker
from rag.chunking.markdown_chunker import MarkdownChunker
from rag.chunking.pdf_chunker import PDFChunker
from rag.chunking.pptx_chunker import PowerPointChunker
from rag.chunking.text_chunker import TextChunker


def get_chunker(mime_type: str) -> BaseChunker:
    """
    根据 MIME 类型获取对应的切片器

    Args:
        mime_type: 文件 MIME 类型

    Returns:
        对应的切片器实例

    Raises:
        ValueError: 不支持的文件类型
    """
    chunker_map = {
        "application/pdf": PDFChunker,
        "application/msword": DocxChunker,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxChunker,
        "text/plain": TextChunker,
        # Excel
        "application/vnd.ms-excel": ExcelChunker,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ExcelChunker,
        # PowerPoint
        "application/vnd.ms-powerpoint": PowerPointChunker,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": PowerPointChunker,
        # Markdown
        "text/markdown": MarkdownChunker,
        # HTML
        "text/html": HTMLChunker,
        # CSV
        "text/csv": CSVChunker,
        # EPUB
        "application/epub+zip": EPUBChunker,
    }

    chunker_class = chunker_map.get(mime_type)
    if not chunker_class:
        raise ValueError(f"不支持的文件类型: {mime_type}")

    return chunker_class()


__all__ = [
    "BaseChunker",
    "Chunk",
    "PDFChunker",
    "DocxChunker",
    "TextChunker",
    "ExcelChunker",
    "PowerPointChunker",
    "MarkdownChunker",
    "HTMLChunker",
    "CSVChunker",
    "EPUBChunker",
    "get_chunker",
]
