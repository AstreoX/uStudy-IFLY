"""Chunking base classes and utilities."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator

import tiktoken

from config import get_settings


@dataclass
class Chunk:
    """文档切片"""

    content: str
    index: int
    token_count: int
    metadata: dict = field(default_factory=dict)


class BaseChunker(ABC):
    """切片器基类"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.target_size = self.settings.chunk_size_tokens
        self.overlap = self.settings.chunk_overlap_tokens
        self.min_size = self.settings.chunk_min_size_tokens

        # 使用 tiktoken 进行 token 计数（cl100k_base 是 GPT-4/text-embedding-3 使用的编码）
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """计算文本的 token 数"""
        return len(self._tokenizer.encode(text))

    def _split_into_sentences(self, text: str) -> list[str]:
        """将文本分割为句子"""
        # 使用正则表达式按句号、问号、感叹号分割
        # 保留中文和英文标点
        pattern = r"(?<=[。！？.!?])\s*"
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _segment_parts(self, segment: str | tuple[str, int]) -> tuple[str, int]:
        """Normalize a segment into text and token count."""
        if isinstance(segment, tuple):
            return segment
        return segment, self.count_tokens(segment)

    def _merge_into_chunks(self, segments: list[str | tuple[str, int]]) -> list[Chunk]:
        """
        将文本段落合并为切片

        Args:
            segments: 文本段落列表（可以是句子或段落）

        Returns:
            切片列表
        """
        chunks: list[Chunk] = []
        current_content: list[str] = []
        current_tokens = 0
        chunk_index = 0

        for segment in segments:
            segment_text, segment_tokens = self._segment_parts(segment)

            # 如果单个段落就超过目标大小，需要进一步分割
            if segment_tokens > self.target_size:
                # 先保存当前累积的内容
                if current_content:
                    chunk_text = "\n".join(current_content)
                    if self.count_tokens(chunk_text) >= self.min_size:
                        chunks.append(
                            Chunk(
                                content=chunk_text,
                                index=chunk_index,
                                token_count=self.count_tokens(chunk_text),
                            )
                        )
                        chunk_index += 1
                    current_content = []
                    current_tokens = 0

                # 对长段落进行句子级别分割
                sentences = [
                    (sentence, self.count_tokens(sentence))
                    for sentence in self._split_into_sentences(segment_text)
                ]
                for sentence in sentences:
                    sentence_text, sentence_tokens = sentence

                    if current_tokens + sentence_tokens > self.target_size:
                        if current_content:
                            chunk_text = " ".join(current_content)
                            if self.count_tokens(chunk_text) >= self.min_size:
                                chunks.append(
                                    Chunk(
                                        content=chunk_text,
                                        index=chunk_index,
                                        token_count=self.count_tokens(chunk_text),
                                    )
                                )
                                chunk_index += 1

                            # 保留重叠部分
                            overlap_content = self._get_overlap_content(current_content)
                            current_content = overlap_content
                            current_tokens = self.count_tokens(" ".join(current_content))

                    current_content.append(sentence_text)
                    current_tokens += sentence_tokens

            # 正常段落处理
            elif current_tokens + segment_tokens > self.target_size:
                # 当前累积内容已达到目标大小
                if current_content:
                    chunk_text = "\n".join(current_content)
                    if self.count_tokens(chunk_text) >= self.min_size:
                        chunks.append(
                            Chunk(
                                content=chunk_text,
                                index=chunk_index,
                                token_count=self.count_tokens(chunk_text),
                            )
                        )
                        chunk_index += 1

                    # 保留重叠部分
                    overlap_content = self._get_overlap_content(current_content)
                    current_content = overlap_content + [segment_text]
                    current_tokens = self.count_tokens("\n".join(current_content))
                else:
                    current_content = [segment_text]
                    current_tokens = segment_tokens
            else:
                current_content.append(segment_text)
                current_tokens += segment_tokens

        # 处理剩余内容
        if current_content:
            chunk_text = "\n".join(current_content)
            if self.count_tokens(chunk_text) >= self.min_size:
                chunks.append(
                    Chunk(
                        content=chunk_text,
                        index=chunk_index,
                        token_count=self.count_tokens(chunk_text),
                    )
                )

        return chunks

    def _get_overlap_content(self, content: list[str]) -> list[str]:
        """获取重叠部分的内容"""
        if not content:
            return []

        overlap_content: list[str] = []
        overlap_tokens = 0

        # 从后向前添加内容，直到达到重叠大小
        for segment in reversed(content):
            segment_tokens = self.count_tokens(segment)
            if overlap_tokens + segment_tokens > self.overlap:
                break
            overlap_content.insert(0, segment)
            overlap_tokens += segment_tokens

        return overlap_content

    def chunk(self, content: bytes | str, filename: str | None = None) -> list[Chunk]:
        """Compatibility wrapper for chunkers that now stream via iter_chunks()."""
        return list(self.iter_chunks(content, filename=filename))

    @abstractmethod
    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
        """
        以迭代器形式将文档切片。

        Args:
            content: 文档内容（字节或字符串）
            filename: 文件名（可选，用于确定处理方式）

        Returns:
            切片迭代器
        """
        raise NotImplementedError

    async def enrich(
        self, chunks: list[Chunk], content: bytes, filename: str | None = None,
        on_progress=None,
    ) -> list[Chunk]:
        """
        异步后处理：VLM OCR / 图片描述等增强处理。

        默认 no-op，子类按需 override。

        Args:
            chunks: chunk() 产出的切片列表
            content: 原始文档字节内容
            filename: 文件名
            on_progress: 可选的进度回调 (completed, total)

        Returns:
            增强后的切片列表
        """
        return chunks
