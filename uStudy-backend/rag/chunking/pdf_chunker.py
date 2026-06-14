"""PDF document chunker using PyMuPDF."""

import io
import logging
from typing import TYPE_CHECKING, Iterator

import fitz  # PyMuPDF

from config import get_settings
from rag.chunking.base import BaseChunker, Chunk

if TYPE_CHECKING:
    from rag.vlm_processor import VLMProcessor, VLMTask

logger = logging.getLogger(__name__)


class PDFChunker(BaseChunker):
    """PDF 文档切片器"""

    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
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

        # 提取每页的文本（含表格检测）
        page_texts: list[tuple[int, str]] = []
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")

                # 尝试检测并提取表格为 Markdown 格式
                table_texts = self._extract_tables_from_page(page)

                # 合并页面文本和表格
                page_content_parts: list[str] = []
                if text.strip():
                    page_content_parts.append(text)
                if table_texts:
                    page_content_parts.extend(table_texts)

                if page_content_parts:
                    combined = "\n\n".join(page_content_parts)
                    page_texts.append((page_num + 1, combined))
        finally:
            doc.close()

        if not page_texts:
            logger.warning("PDF 文件没有可提取的文本内容")
            return

        # 将页面文本分割为段落，保留页码信息
        segments_with_page: list[tuple[str, int, int]] = []
        for page_num, page_text in page_texts:
            # 清理文本
            page_text = self._clean_text(page_text)

            # 按段落分割
            paragraphs = self._split_into_paragraphs(page_text)

            for para in paragraphs:
                if para:
                    segments_with_page.append((para, page_num, self.count_tokens(para)))

        # 合并为切片（带页码跟踪）
        chunks = self._merge_with_page_info(segments_with_page)

        # 添加元数据
        for chunk in chunks:
            chunk.metadata["source_type"] = "pdf"
            if filename:
                chunk.metadata["filename"] = filename
            yield chunk

    def _extract_tables_from_page(self, page) -> list[str]:
        """使用 PyMuPDF find_tables() 检测页面表格并转为 Markdown"""
        try:
            tables = page.find_tables()
        except Exception:
            # find_tables() 在某些页面可能失败，静默忽略
            return []

        result: list[str] = []
        for table in tables:
            try:
                extracted = table.extract()
                if not extracted or len(extracted) < 2:
                    continue

                # 清洗单元格内容
                header = [str(c).strip() if c else "" for c in extracted[0]]
                lines = ["| " + " | ".join(header) + " |"]
                lines.append("| " + " | ".join("---" for _ in header) + " |")

                for row in extracted[1:]:
                    cells = [str(c).strip() if c else "" for c in row]
                    # 确保列数与表头一致
                    while len(cells) < len(header):
                        cells.append("")
                    cells = cells[:len(header)]
                    lines.append("| " + " | ".join(cells) + " |")

                result.append("\n".join(lines))
            except Exception:
                continue

        return result

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
        self, segments_with_page: list[tuple[str, int, int]]
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

        for segment, page_num, segment_tokens in segments_with_page:

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

    async def enrich(
        self, chunks: list[Chunk], content: bytes, filename: str | None = None
    ) -> list[Chunk]:
        """
        VLM 后处理：扫描件 OCR + 嵌入图片描述

        1. 逐页检查：文字少 + 有图片 → 判定为扫描页 → OCR
        2. 嵌入图片提取 → 过滤小图 → VLM 描述 → 作为额外 Chunk
        """
        settings = get_settings()

        if not settings.vlm_processing_enabled:
            return chunks

        from rag.vlm_processor import VLMProcessor, VLMTask

        vlm = VLMProcessor()
        vlm_tasks: list[VLMTask] = []
        task_metadata: list[dict] = []

        try:
            pdf_stream = io.BytesIO(content)
            doc = fitz.open(stream=pdf_stream, filetype="pdf")
        except Exception:
            return chunks

        images_processed = 0
        max_images = settings.vlm_max_images_per_document

        try:
            for page_num in range(len(doc)):
                if images_processed >= max_images:
                    break

                page = doc[page_num]
                page_text = page.get_text("text").strip()

                # 扫描页检测: 文字极少 + 有图片
                if settings.vlm_ocr_enabled and len(page_text) < 20:
                    page_images = page.get_images(full=True)
                    if page_images:
                        try:
                            pix = page.get_pixmap(dpi=200)
                            img_bytes = pix.tobytes("png")
                            vlm_tasks.append(VLMTask(
                                image_bytes=img_bytes,
                                task_type="ocr",
                                page_num=page_num + 1,
                            ))
                            task_metadata.append({
                                "type": "ocr",
                                "page_num": page_num + 1,
                            })
                            images_processed += 1
                        except Exception as e:
                            logger.warning("PDF 页面渲染失败 (page %d): %s", page_num + 1, e)
                        continue

                # 嵌入图片提取
                if settings.vlm_image_description_enabled:
                    for img_info in page.get_images(full=True):
                        if images_processed >= max_images:
                            break

                        xref = img_info[0]
                        try:
                            img_data = doc.extract_image(xref)
                            if not img_data:
                                continue

                            img_bytes = img_data["image"]
                            img_size = len(img_bytes)

                            if img_size < settings.vlm_min_image_size_bytes:
                                continue
                            if img_size > settings.vlm_max_image_size_bytes:
                                continue

                            vlm_tasks.append(VLMTask(
                                image_bytes=img_bytes,
                                task_type="describe",
                                context=page_text[:500] if page_text else "",
                                page_num=page_num + 1,
                            ))
                            task_metadata.append({
                                "type": "describe",
                                "page_num": page_num + 1,
                            })
                            images_processed += 1
                        except Exception as e:
                            logger.warning("PDF 图片提取失败 (xref %d): %s", xref, e)
        finally:
            doc.close()

        if not vlm_tasks:
            return chunks

        logger.info("PDF VLM 处理: %d 个任务 (文件: %s)", len(vlm_tasks), filename)
        try:
            results = await vlm.process_batch(vlm_tasks)
        except Exception as e:
            logger.error("VLM 批量处理失败，降级返回原始 chunks: %s", e)
            return chunks

        next_index = max((c.index for c in chunks), default=-1) + 1
        added = 0

        for result_text, meta in zip(results, task_metadata):
            if not result_text or result_text.strip() == "[无可识别文字]":
                continue

            if meta["type"] == "ocr":
                chunk = Chunk(
                    content=result_text,
                    index=next_index,
                    token_count=self.count_tokens(result_text),
                    metadata={
                        "source_type": "pdf",
                        "vlm_type": "ocr",
                        "page_start": meta["page_num"],
                        "page_end": meta["page_num"],
                    },
                )
            else:
                desc_text = f"[图片描述] {result_text}"
                chunk = Chunk(
                    content=desc_text,
                    index=next_index,
                    token_count=self.count_tokens(desc_text),
                    metadata={
                        "source_type": "pdf",
                        "vlm_type": "image_description",
                        "page_start": meta["page_num"],
                        "page_end": meta["page_num"],
                    },
                )

            if filename:
                chunk.metadata["filename"] = filename

            chunks.append(chunk)
            next_index += 1
            added += 1

        if added:
            logger.info("PDF VLM 处理完成，新增 %d 个 chunks", added)

        return chunks
