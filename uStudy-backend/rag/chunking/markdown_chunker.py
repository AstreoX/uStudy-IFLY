"""Markdown document chunker."""

import logging
import re
from typing import Iterator

import chardet

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class MarkdownChunker(BaseChunker):
    """Markdown 文档切片器（.md）"""

    # 匹配 h1-h3 标题行
    _HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
        # 编码检测（复用 TextChunker 的 chardet 逻辑）
        if isinstance(content, bytes):
            detected = chardet.detect(content)
            encoding = detected.get("encoding") or "utf-8"
            try:
                text = content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
                    try:
                        text = content.decode(enc)
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                else:
                    text = content.decode("latin-1")
        else:
            text = content

        text = text.strip()
        if not text:
            logger.warning("Markdown 文件内容为空")
            return

        # 按标题边界分段
        segments = self._split_by_headings(text)

        if not segments:
            logger.warning("Markdown 文件没有可提取的内容")
            return

        chunks = self._merge_into_chunks(segments)

        for chunk in chunks:
            chunk.metadata["source_type"] = "markdown"
            if filename:
                chunk.metadata["filename"] = filename
            yield chunk

    def _split_by_headings(self, text: str) -> list[str]:
        """按 h1-h3 标题边界分段，保持代码块完整"""
        # 先标记代码块位置，避免误分割代码块内的 #
        code_blocks: list[tuple[int, int]] = []
        for m in re.finditer(r"```[\s\S]*?```", text):
            code_blocks.append((m.start(), m.end()))

        def _in_code_block(pos: int) -> bool:
            return any(start <= pos < end for start, end in code_blocks)

        # 找到所有有效的标题位置
        split_positions: list[int] = [0]
        for m in self._HEADING_PATTERN.finditer(text):
            if not _in_code_block(m.start()):
                if m.start() > 0:
                    split_positions.append(m.start())

        segments: list[str] = []
        for i, start in enumerate(split_positions):
            end = split_positions[i + 1] if i + 1 < len(split_positions) else len(text)
            segment = text[start:end].strip()
            if segment:
                segments.append(segment)

        return segments
