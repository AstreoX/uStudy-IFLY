"""Word document (DOCX) chunker using python-docx."""

import io
import logging
from typing import Iterator

from docx import Document

from config import get_settings
from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class DocxChunker(BaseChunker):
    """Word 文档切片器"""

    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
        """
        将 Word 文档切片

        Args:
            content: DOCX 文件内容（字节）
            filename: 文件名（可选）

        Returns:
            切片列表
        """
        if isinstance(content, str):
            raise ValueError("DOCX content must be bytes, not string")

        # 打开 Word 文档
        try:
            doc_stream = io.BytesIO(content)
            doc = Document(doc_stream)
        except Exception as e:
            logger.error("无法打开 Word 文档: %s", e)
            raise ValueError(f"无法解析 Word 文档: {e}")

        # 提取段落和标题
        segments_with_heading: list[tuple[str, str | None, int]] = []
        current_heading: str | None = None

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # 检查是否是标题样式
            if para.style and para.style.name and para.style.name.startswith("Heading"):
                current_heading = text
                # 标题本身也作为内容保留
                segments_with_heading.append((text, current_heading, self.count_tokens(text)))
            else:
                segments_with_heading.append((text, current_heading, self.count_tokens(text)))

        # 提取表格内容
        for table in doc.tables:
            table_text = self._extract_table_text(table)
            if table_text:
                segments_with_heading.append(
                    (table_text, current_heading, self.count_tokens(table_text))
                )

        if not segments_with_heading:
            logger.warning("Word 文档没有可提取的文本内容")
            return

        # 合并为切片
        chunks = self._merge_with_heading_info(segments_with_heading)

        # 添加元数据
        for chunk in chunks:
            chunk.metadata["source_type"] = "docx"
            if filename:
                chunk.metadata["filename"] = filename
            yield chunk

    def _extract_table_text(self, table) -> str:
        """提取表格内容为 Markdown 表格格式"""
        rows_data: list[list[str]] = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows_data.append(cells)

        if not rows_data:
            return ""

        # 确保所有行列数一致
        max_cols = max(len(r) for r in rows_data)
        for row in rows_data:
            while len(row) < max_cols:
                row.append("")

        lines: list[str] = []
        # Header row
        lines.append("| " + " | ".join(rows_data[0]) + " |")
        # Separator
        lines.append("| " + " | ".join("---" for _ in rows_data[0]) + " |")
        # Data rows
        for row in rows_data[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _merge_with_heading_info(
        self, segments_with_heading: list[tuple[str, str | None, int]]
    ) -> list[Chunk]:
        """
        合并段落为切片，同时记录标题信息

        Args:
            segments_with_heading: (段落文本, 所属标题) 列表

        Returns:
            切片列表，每个切片包含 heading 元数据
        """
        chunks: list[Chunk] = []
        current_content: list[str] = []
        current_tokens = 0
        current_headings: set[str] = set()
        chunk_index = 0

        for segment, heading, segment_tokens in segments_with_heading:

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
                                metadata={
                                    "headings": list(current_headings - {None}),
                                },
                            )
                        )
                        chunk_index += 1
                    current_content = []
                    current_tokens = 0
                    current_headings = set()

                # 对长段落进行句子级别分割
                sentences = self._split_into_sentences(segment)
                for sentence in sentences:
                    sentence_tokens = self.count_tokens(sentence)

                    if current_tokens + sentence_tokens > self.target_size:
                        if current_content:
                            chunk_text = " ".join(current_content)
                            if self.count_tokens(chunk_text) >= self.min_size:
                                chunks.append(
                                    Chunk(
                                        content=chunk_text,
                                        index=chunk_index,
                                        token_count=self.count_tokens(chunk_text),
                                        metadata={
                                            "headings": list(
                                                current_headings - {None}
                                            ),
                                        },
                                    )
                                )
                                chunk_index += 1

                            overlap_content = self._get_overlap_content(current_content)
                            current_content = overlap_content
                            current_tokens = self.count_tokens(" ".join(current_content))
                            current_headings = {heading} if heading else set()

                    current_content.append(sentence)
                    current_tokens += sentence_tokens
                    if heading:
                        current_headings.add(heading)

            elif current_tokens + segment_tokens > self.target_size:
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
                                    "headings": list(current_headings - {None}),
                                },
                            )
                        )
                        chunk_index += 1

                    overlap_content = self._get_overlap_content(current_content)
                    current_content = overlap_content + [segment]
                    current_tokens = self.count_tokens("\n".join(current_content))
                    current_headings = {heading} if heading else set()
                else:
                    current_content = [segment]
                    current_tokens = segment_tokens
                    current_headings = {heading} if heading else set()
            else:
                current_content.append(segment)
                current_tokens += segment_tokens
                if heading:
                    current_headings.add(heading)

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
                            "headings": list(current_headings - {None}),
                        },
                    )
                )

        return chunks

    async def enrich(
        self, chunks: list[Chunk], content: bytes, filename: str | None = None
    ) -> list[Chunk]:
        """VLM 后处理：提取 DOCX 中嵌入图片并生成描述"""
        settings = get_settings()

        if not settings.vlm_processing_enabled or not settings.vlm_image_description_enabled:
            return chunks

        from rag.vlm_processor import VLMProcessor, VLMTask

        try:
            doc = Document(io.BytesIO(content))
        except Exception:
            return chunks

        vlm_tasks: list[VLMTask] = []
        images_processed = 0
        max_images = settings.vlm_max_images_per_document

        # 遍历文档关系中的图片
        for rel in doc.part.rels.values():
            if images_processed >= max_images:
                break

            if "image" not in rel.reltype:
                continue

            try:
                img_bytes = rel.target_part.blob
                img_size = len(img_bytes)

                if img_size < settings.vlm_min_image_size_bytes:
                    continue
                if img_size > settings.vlm_max_image_size_bytes:
                    continue

                vlm_tasks.append(VLMTask(
                    image_bytes=img_bytes,
                    task_type="describe",
                ))
                images_processed += 1
            except Exception as e:
                logger.warning("DOCX 图片提取失败: %s", e)

        if not vlm_tasks:
            return chunks

        logger.info("DOCX VLM 处理: %d 张图片 (文件: %s)", len(vlm_tasks), filename)
        vlm = VLMProcessor()

        try:
            results = await vlm.process_batch(vlm_tasks)
        except Exception as e:
            logger.error("VLM 批量处理失败，降级返回原始 chunks: %s", e)
            return chunks

        next_index = max((c.index for c in chunks), default=-1) + 1
        added = 0

        for result_text in results:
            if not result_text or not result_text.strip():
                continue

            desc_text = f"[图片描述] {result_text}"
            chunk = Chunk(
                content=desc_text,
                index=next_index,
                token_count=self.count_tokens(desc_text),
                metadata={
                    "source_type": "docx",
                    "vlm_type": "image_description",
                },
            )
            if filename:
                chunk.metadata["filename"] = filename

            chunks.append(chunk)
            next_index += 1
            added += 1

        if added:
            logger.info("DOCX VLM 处理完成，新增 %d 个 chunks", added)

        return chunks
