"""Chunking module for document segmentation."""

from importlib import import_module

from rag.chunking.base import BaseChunker, Chunk
from rag.parsing import canonical_type_from_hint

_CHUNKER_CLASS_PATHS = {
    "pdf": "rag.chunking.pdf_chunker:PDFChunker",
    "docx": "rag.chunking.docx_chunker:DocxChunker",
    "text": "rag.chunking.text_chunker:TextChunker",
    "xlsx": "rag.chunking.excel_chunker:ExcelChunker",
    "pptx": "rag.chunking.pptx_chunker:PowerPointChunker",
    "markdown": "rag.chunking.markdown_chunker:MarkdownChunker",
    "html": "rag.chunking.html_chunker:HTMLChunker",
    "csv": "rag.chunking.csv_chunker:CSVChunker",
    "epub": "rag.chunking.epub_chunker:EPUBChunker",
}


def _load_chunker_class(canonical_type: str):
    module_name, class_name = _CHUNKER_CLASS_PATHS[canonical_type].split(":")
    module = import_module(module_name)
    return getattr(module, class_name)


def get_chunker(format_hint: str) -> BaseChunker:
    """
    根据 MIME 类型或 canonical type 获取对应的切片器。

    Args:
        format_hint: 文件 MIME 类型或 canonical type

    Returns:
        对应的切片器实例
    """
    canonical_type = canonical_type_from_hint(format_hint)
    try:
        chunker_class = _load_chunker_class(canonical_type)
    except KeyError as exc:
        raise ValueError(f"不支持的文件类型: {format_hint}") from exc
    return chunker_class()


__all__ = [
    "BaseChunker",
    "Chunk",
    "get_chunker",
]
