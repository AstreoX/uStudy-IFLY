"""PDF document chunker using PyMuPDF."""

import io
import logging

import fitz  # PyMuPDF

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class PDFChunker(BaseChunker):
    """PDF 文档切片器"""

    def chunk(self, content: bytes | str, filename: str | None = None) -> list[Chunk]:
        """
        将 PDF 文档切片

        Args:
            content: PDF 文件内容（字节）
            filename: 文件名（可选）

        Returns:
            切片列表
        """
        if isinstance(content, str):
            raise ValueError("PDF content must be bytes, not string")

        # 打开 PDF
        try:
            pdf_stream = io.BytesIO(content)
            doc = fitz.open(stream=pdf_stream, filetype="pdf")
        except Exception as e:
            logger.error("无法打开 PDF 文件: %s", e)
            raise ValueError(f"无法解析 PDF 文件: {e}")

        # 提取每页的文本
        page_texts: list[tuple[int, str]] = []
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    page_texts.append((page_num + 1, text))  # 页码从 1 开始
        finally:
            doc.close()

        if not page_texts:
            logger.warning("PDF 文件没有可提取的文本内容")
            return []

        # 将页面文本分割为段落，保留页码信息
        segments_with_page: list[tuple[str, int]] = []
        for page_num, page_text in page_texts:
            # 清理文本
            page_text = self._clean_text(page_text)

            # 按段落分割
            paragraphs = self._split_into_paragraphs(page_text)

            for para in paragraphs:
                if para:
                    segments_with_page.append((para, page_num))

        # 合并为切片（带页码跟踪）
        chunks = self._merge_with_page_info(segments_with_page)

        # 添加元数据
        for chunk in chunks:
            chunk.metadata["source_type"] = "pdf"
            if filename:
                chunk.metadata["filename"] = filename

        return chunks

    def _clean_text(self, text: str) -> str:
        """清理 PDF 提取的文本"""
        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # PDF 中的软换行（行末空格+换行）合并
        import re

        text = re.sub(r" +\n", " ", text)

        # 移除页眉页脚常见的重复内容（多余空行）
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text.strip()

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """将文本分割为段落"""
        paragraphs = text.split("\n\n")
        result = []
        for para in paragraphs:
            # 合并段落内的换行（PDF 常见问题）
            para = " ".join(para.split())
            if para:
                result.append(para)
        return result

    def _merge_with_page_info(
        self, segments_with_page: list[tuple[str, int]]
    ) -> list[Chunk]:
        """
        合并段落为切片，同时记录页码信息

        Args:
            segments_with_page: (段落文本, 页码) 列表

        Returns:
            切片列表，每个切片包含 page_start 和 page_end 元数据
        """
        chunks: list[Chunk] = []
        current_content: list[str] = []
        current_tokens = 0
        current_pages: set[int] = set()
        chunk_index = 0

        for segment, page_num in segments_with_page:
            segment_tokens = self.count_tokens(segment)

            if current_tokens + segment_tokens > self.target_size:
                # 保存当前切片
                if current_content:
                    chunk_text = "\n".join(current_content)
                    if self.count_tokens(chunk_text) >= self.min_size:
                        chunks.append(
                            Chunk(
                                content=chunk_text,
                                index=chunk_index,
                                token_count=self.count_tokens(chunk_text),
                                metadata={
                                    "page_start": min(current_pages),
                                    "page_end": max(current_pages),
                                },
                            )
                        )
                        chunk_index += 1

                    # 计算重叠
                    overlap_content = self._get_overlap_content(current_content)
                    current_content = overlap_content + [segment]
                    current_tokens = self.count_tokens("\n".join(current_content))
                    # 重叠部分保留页码 + 新段落页码
                    current_pages = {page_num}
                else:
                    current_content = [segment]
                    current_tokens = segment_tokens
                    current_pages = {page_num}
            else:
                current_content.append(segment)
                current_tokens += segment_tokens
                current_pages.add(page_num)

        # 处理剩余内容
        if current_content:
            chunk_text = "\n".join(current_content)
            if self.count_tokens(chunk_text) >= self.min_size:
                chunks.append(
                    Chunk(
                        content=chunk_text,
                        index=chunk_index,
                        token_count=self.count_tokens(chunk_text),
                        metadata={
                            "page_start": min(current_pages),
                            "page_end": max(current_pages),
                        },
                    )
                )

        return chunks
