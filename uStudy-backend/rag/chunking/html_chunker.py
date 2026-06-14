"""HTML document chunker using BeautifulSoup."""

import logging
from typing import Iterator

import chardet
from bs4 import BeautifulSoup

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)

# 需要移除的非内容标签
_REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"}


class HTMLChunker(BaseChunker):
    """HTML 文档切片器（.html, .htm）"""

    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
        # 编码检测
        if isinstance(content, bytes):
            detected = chardet.detect(content)
            encoding = detected.get("encoding") or "utf-8"
            try:
                html_text = content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
                    try:
                        html_text = content.decode(enc)
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                else:
                    html_text = content.decode("latin-1")
        else:
            html_text = content

        soup = BeautifulSoup(html_text, "html.parser")

        # 移除非内容标签
        for tag in soup.find_all(_REMOVE_TAGS):
            tag.decompose()

        # 按语义结构提取段落
        segments = self._extract_segments(soup)

        if not segments:
            logger.warning("HTML 文件没有可提取的文本内容")
            return

        chunks = self._merge_into_chunks(segments)

        for chunk in chunks:
            chunk.metadata["source_type"] = "html"
            if filename:
                chunk.metadata["filename"] = filename
            yield chunk

    def _extract_segments(self, soup: BeautifulSoup) -> list[str]:
        """从 HTML 中提取文本段落"""
        segments: list[str] = []

        # 提取 title
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            segments.append(f"# {title_tag.get_text(strip=True)}")

        # 按块级元素分段
        body = soup.find("body") or soup
        block_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "article",
                      "section", "blockquote", "li", "td", "th", "pre", "figcaption"}

        for element in body.find_all(block_tags):
            # 跳过嵌套的块级元素（只处理叶子级别）
            if element.find(block_tags):
                continue

            text = element.get_text(separator=" ", strip=True)
            if not text or len(text) < 5:
                continue

            # 标题标签加前缀
            tag_name = element.name
            if tag_name and tag_name.startswith("h") and len(tag_name) == 2:
                level = tag_name[1]
                text = f"{'#' * int(level)} {text}"

            segments.append(text)

        # 如果结构化提取失败，回退到全文提取
        if not segments:
            full_text = body.get_text(separator="\n", strip=True)
            if full_text:
                paragraphs = [p.strip() for p in full_text.split("\n") if p.strip()]
                segments = paragraphs

        return segments
