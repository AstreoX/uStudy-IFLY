"""EPUB document chunker using ebooklib + BeautifulSoup."""

import io
import logging
from typing import Iterator

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)

# 需要移除的非内容标签
_REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript"}


class EPUBChunker(BaseChunker):
    """EPUB 电子书切片器（.epub）"""

    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
        if isinstance(content, str):
            raise ValueError("EPUB content must be bytes, not string")

        try:
            book = epub.read_epub(io.BytesIO(content))
        except Exception as e:
            logger.error("无法打开 EPUB 文件: %s", e)
            raise ValueError(f"无法解析 EPUB 文件: {e}")

        segments: list[str] = []

        # 按章节顺序提取内容
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html_content = item.get_content()

            try:
                chapter_text = self._extract_text_from_html(html_content)
            except Exception as e:
                logger.warning("EPUB 章节解析失败: %s", e)
                continue

            if chapter_text:
                segments.append(chapter_text)

        if not segments:
            logger.warning("EPUB 文件没有可提取的文本内容")
            return

        chunks = self._merge_into_chunks(segments)

        for chunk in chunks:
            chunk.metadata["source_type"] = "epub"
            if filename:
                chunk.metadata["filename"] = filename
            yield chunk

    def _extract_text_from_html(self, html_bytes: bytes) -> str:
        """从章节 HTML 中提取纯文本（复用 HTMLChunker 的逻辑）"""
        soup = BeautifulSoup(html_bytes, "html.parser")

        # 移除非内容标签
        for tag in soup.find_all(_REMOVE_TAGS):
            tag.decompose()

        body = soup.find("body") or soup

        # 提取块级元素文本
        block_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "div",
                      "blockquote", "li", "pre", "figcaption"}

        parts: list[str] = []
        for element in body.find_all(block_tags):
            if element.find(block_tags):
                continue

            text = element.get_text(separator=" ", strip=True)
            if not text or len(text) < 3:
                continue

            tag_name = element.name
            if tag_name and tag_name.startswith("h") and len(tag_name) == 2:
                level = tag_name[1]
                text = f"{'#' * int(level)} {text}"

            parts.append(text)

        # 回退到全文提取
        if not parts:
            full_text = body.get_text(separator="\n", strip=True)
            if full_text:
                parts = [p.strip() for p in full_text.split("\n") if p.strip()]

        return "\n\n".join(parts)
