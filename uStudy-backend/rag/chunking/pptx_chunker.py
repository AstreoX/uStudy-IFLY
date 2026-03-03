"""PowerPoint document chunker using python-pptx, with VLM visual enrichment."""

import io
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pptx import Presentation

from config import get_settings
from rag.chunking.base import BaseChunker, Chunk

if TYPE_CHECKING:
    from rag.vlm_processor import VLMProcessor, VLMTask

logger = logging.getLogger(__name__)


class PowerPointChunker(BaseChunker):
    """PowerPoint 文档切片器（.pptx, .ppt）— 每页一个 Chunk，支持 VLM 视觉增强"""

    def chunk(self, content: bytes | str, filename: str | None = None) -> list[Chunk]:
        """
        将 PowerPoint 文档按页切片（每页一个 Chunk）。

        text extraction 作为基础结果和 VLM 降级 fallback。
        """
        if isinstance(content, str):
            raise ValueError("PowerPoint content must be bytes, not string")

        try:
            prs = Presentation(io.BytesIO(content))
        except Exception as e:
            logger.error("无法打开 PowerPoint 文件: %s", e)
            raise ValueError(f"无法解析 PowerPoint 文件: {e}")

        chunks: list[Chunk] = []
        chunk_index = 0

        for slide_num, slide in enumerate(prs.slides, start=1):
            slide_parts: list[str] = [f"[Slide {slide_num}]"]

            for shape in slide.shapes:
                if shape.has_text_frame:
                    text = shape.text_frame.text.strip()
                    if text:
                        slide_parts.append(text)

                if shape.has_table:
                    table_text = self._extract_table(shape.table)
                    if table_text:
                        slide_parts.append(table_text)

            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    slide_parts.append(f"[Notes] {notes}")

            # 只有标题以外有内容才保留
            if len(slide_parts) > 1:
                slide_text = "\n".join(slide_parts)
                chunks.append(
                    Chunk(
                        content=slide_text,
                        index=chunk_index,
                        token_count=self.count_tokens(slide_text),
                        metadata={
                            "source_type": "pptx",
                            "slide_num": slide_num,
                            "page_start": slide_num,
                            "page_end": slide_num,
                        },
                    )
                )
                chunk_index += 1

        if not chunks:
            logger.warning("PowerPoint 文件没有可提取的文本内容")
            return []

        if filename:
            for chunk in chunks:
                chunk.metadata["filename"] = filename

        return chunks

    async def enrich(
        self, chunks: list[Chunk], content: bytes, filename: str | None = None
    ) -> list[Chunk]:
        """
        VLM 逐页处理：PPTX → PDF → PNG → VLM OCR。

        与 PDF enrich 不同，PPT enrich 是 **替换** 模式：
        VLM 结果完全取代 text extraction 的 chunks，因为 PPT 的核心价值在视觉呈现。
        若 VLM 失败，保留原始 text chunks 作为降级。
        """
        settings = get_settings()

        if not settings.vlm_processing_enabled:
            return chunks

        # 1. PPTX → PDF
        pdf_bytes = self._convert_to_pdf(content, filename)
        if pdf_bytes is None:
            logger.warning("PPTX → PDF 转换失败，保留 text extraction 结果")
            return chunks

        # 2. PDF → 逐页 PNG → VLM tasks
        import fitz  # PyMuPDF

        from rag.vlm_processor import VLMProcessor, VLMTask

        try:
            doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
        except Exception as e:
            logger.error("无法打开转换后的 PDF: %s", e)
            return chunks

        vlm = VLMProcessor()
        vlm_tasks: list[VLMTask] = []
        task_slide_nums: list[int] = []

        # 构建 slide_num → text 映射，用于给 VLM 提供上下文
        text_by_slide: dict[int, str] = {}
        for chunk in chunks:
            slide_num = chunk.metadata.get("slide_num")
            if slide_num is not None:
                text_by_slide[slide_num] = chunk.content

        max_images = settings.vlm_max_images_per_document

        try:
            for page_idx in range(len(doc)):
                if len(vlm_tasks) >= max_images:
                    break

                slide_num = page_idx + 1
                page = doc[page_idx]

                try:
                    pix = page.get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("png")
                except Exception as e:
                    logger.warning("PPT 页面渲染失败 (slide %d): %s", slide_num, e)
                    continue

                # 传入 text extraction 结果作为上下文辅助 VLM
                context = text_by_slide.get(slide_num, "")

                vlm_tasks.append(VLMTask(
                    image_bytes=img_bytes,
                    task_type="ocr",
                    context=context,
                    page_num=slide_num,
                ))
                task_slide_nums.append(slide_num)
        finally:
            doc.close()

        if not vlm_tasks:
            return chunks

        # 3. VLM 批量处理
        logger.info("PPT VLM 处理: %d 个页面 (文件: %s)", len(vlm_tasks), filename)
        try:
            results = await vlm.process_batch(vlm_tasks)
        except Exception as e:
            logger.error("VLM 批量处理失败，降级返回 text extraction 结果: %s", e)
            return chunks

        # 4. 用 VLM 结果替换原有 chunks
        vlm_chunks: list[Chunk] = []
        chunk_index = 0

        for result_text, slide_num in zip(results, task_slide_nums):
            if not result_text or result_text.strip() == "[无可识别文字]":
                # VLM 返回空 → 尝试使用原始 text extraction
                fallback_text = text_by_slide.get(slide_num)
                if fallback_text:
                    vlm_chunks.append(
                        Chunk(
                            content=fallback_text,
                            index=chunk_index,
                            token_count=self.count_tokens(fallback_text),
                            metadata={
                                "source_type": "pptx",
                                "slide_num": slide_num,
                                "page_start": slide_num,
                                "page_end": slide_num,
                            },
                        )
                    )
                    chunk_index += 1
                continue

            vlm_chunks.append(
                Chunk(
                    content=result_text,
                    index=chunk_index,
                    token_count=self.count_tokens(result_text),
                    metadata={
                        "source_type": "pptx",
                        "vlm_type": "ocr",
                        "slide_num": slide_num,
                        "page_start": slide_num,
                        "page_end": slide_num,
                    },
                )
            )
            chunk_index += 1

        if not vlm_chunks:
            # 全部 VLM 失败，保留原始 text chunks
            logger.warning("VLM 全部返回空，保留 text extraction 结果")
            return chunks

        if filename:
            for chunk in vlm_chunks:
                chunk.metadata["filename"] = filename

        logger.info(
            "PPT VLM 处理完成，%d 页 → %d 个 chunks（替换原 %d 个 text chunks）",
            len(vlm_tasks), len(vlm_chunks), len(chunks),
        )
        return vlm_chunks

    def _convert_to_pdf(
        self, pptx_bytes: bytes, filename: str | None = None
    ) -> bytes | None:
        """
        PPTX/PPT → PDF 转换（LibreOffice headless）。

        Returns:
            PDF 字节数据，失败返回 None
        """
        # 检测文件格式，确保临时文件扩展名正确（LibreOffice 依赖扩展名判断格式）
        is_legacy_ppt = (
            filename
            and filename.lower().endswith(".ppt")
            and not filename.lower().endswith(".pptx")
        )
        ext = ".ppt" if is_legacy_ppt else ".pptx"
        input_stem = "input"

        tmp_dir = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix="pptx2pdf_")
            tmp_path = Path(tmp_dir)

            input_file = tmp_path / f"{input_stem}{ext}"
            input_file.write_bytes(pptx_bytes)

            # LibreOffice headless 转换
            proc = subprocess.Popen(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", str(tmp_path),
                    str(input_file),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout, stderr = proc.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                logger.error("LibreOffice 转换超时 (120s)")
                return None

            if proc.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace")
                logger.error("LibreOffice 转换失败 (rc=%d): %s", proc.returncode, stderr_text)
                return None

            pdf_file = tmp_path / f"{input_stem}.pdf"
            if not pdf_file.exists():
                logger.error("LibreOffice 转换后未找到 PDF 输出文件")
                return None

            return pdf_file.read_bytes()

        except FileNotFoundError:
            logger.error("LibreOffice 未安装，无法执行 PPTX → PDF 转换")
            return None
        except Exception as e:
            logger.error("PPTX → PDF 转换异常: %s", e)
            return None
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _extract_table(self, table) -> str:
        """提取 PowerPoint 表格为 Markdown 格式"""
        rows_data: list[list[str]] = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows_data.append(cells)

        if not rows_data:
            return ""

        lines: list[str] = []
        # Header
        lines.append("| " + " | ".join(rows_data[0]) + " |")
        lines.append("| " + " | ".join("---" for _ in rows_data[0]) + " |")

        for row in rows_data[1:]:
            while len(row) < len(rows_data[0]):
                row.append("")
            lines.append("| " + " | ".join(row[:len(rows_data[0])]) + " |")

        return "\n".join(lines)
