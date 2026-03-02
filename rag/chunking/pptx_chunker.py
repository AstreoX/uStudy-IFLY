"""PowerPoint document chunker using python-pptx."""

import io
import logging

from pptx import Presentation

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class PowerPointChunker(BaseChunker):
    """PowerPoint 文档切片器（.pptx, .ppt）"""

    def chunk(self, content: bytes | str, filename: str | None = None) -> list[Chunk]:
        if isinstance(content, str):
            raise ValueError("PowerPoint content must be bytes, not string")

        try:
            prs = Presentation(io.BytesIO(content))
        except Exception as e:
            logger.error("无法打开 PowerPoint 文件: %s", e)
            raise ValueError(f"无法解析 PowerPoint 文件: {e}")

        segments: list[str] = []

        for slide_num, slide in enumerate(prs.slides, start=1):
            slide_parts: list[str] = [f"[Slide {slide_num}]"]

            # 提取所有 shape 的文本
            for shape in slide.shapes:
                if shape.has_text_frame:
                    text = shape.text_frame.text.strip()
                    if text:
                        slide_parts.append(text)

                # 提取表格
                if shape.has_table:
                    table_text = self._extract_table(shape.table)
                    if table_text:
                        slide_parts.append(table_text)

            # 提取备注
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    slide_parts.append(f"[Notes] {notes}")

            # 只有标题以外有内容才保留
            if len(slide_parts) > 1:
                segments.append("\n".join(slide_parts))

        if not segments:
            logger.warning("PowerPoint 文件没有可提取的文本内容")
            return []

        chunks = self._merge_into_chunks(segments)

        for chunk in chunks:
            chunk.metadata["source_type"] = "pptx"
            if filename:
                chunk.metadata["filename"] = filename

        return chunks

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
            # 确保列数一致
            while len(row) < len(rows_data[0]):
                row.append("")
            lines.append("| " + " | ".join(row[:len(rows_data[0])]) + " |")

        return "\n".join(lines)
