"""Plain text chunker."""

from typing import Iterator

import chardet

from rag.chunking.base import BaseChunker, Chunk


class TextChunker(BaseChunker):
    """纯文本切片器"""

    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
        """
        将纯文本切片

        Args:
            content: 文本内容（字节或字符串）
            filename: 文件名（可选）

        Returns:
            切片列表
        """
        # 如果是字节，先检测编码并解码
        if isinstance(content, bytes):
            detected = chardet.detect(content)
            encoding = detected.get("encoding") or "utf-8"
            try:
                text = content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                # 如果检测的编码失败，尝试常见编码
                for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
                    try:
                        text = content.decode(enc)
                        break
                    except (UnicodeDecodeError, LookupError):
                        continue
                else:
                    # 所有编码都失败，使用 latin-1（不会失败）
                    text = content.decode("latin-1")
        else:
            text = content

        # 清理文本
        text = self._clean_text(text)

        # 按段落分割
        paragraphs = self._split_into_paragraphs(text)

        # 合并为切片
        chunks = self._merge_into_chunks(paragraphs)

        # 添加元数据
        for chunk in chunks:
            chunk.metadata["source_type"] = "text"
            if filename:
                chunk.metadata["filename"] = filename
            yield chunk

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 移除过多的空行（保留最多两个连续换行）
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text.strip()

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """将文本分割为段落"""
        # 按双换行分割段落
        paragraphs = text.split("\n\n")

        # 处理每个段落
        result = []
        for para in paragraphs:
            # 清理段落内的多余空白
            para = " ".join(para.split())
            if para:
                result.append(para)

        return result
