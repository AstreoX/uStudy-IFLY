"""Excel document chunker using openpyxl."""

import io
import logging
from typing import Iterator

import openpyxl

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class ExcelChunker(BaseChunker):
    """Excel 文档切片器（.xlsx, .xls）"""

    # 大 sheet 分段阈值
    LARGE_SHEET_ROW_THRESHOLD = 500

    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
        if isinstance(content, str):
            raise ValueError("Excel content must be bytes, not string")

        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as e:
            logger.error("无法打开 Excel 文件: %s", e)
            raise ValueError(f"无法解析 Excel 文件: {e}")

        segments: list[tuple[str, int]] = []

        try:
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                row_iter = ws.iter_rows(values_only=True)
                header = next(row_iter, None)
                if not header:
                    continue

                # 提取表头
                header_cells = [str(c) if c is not None else "" for c in header]
                batch: list[tuple] = []
                has_data_rows = False

                for row in row_iter:
                    has_data_rows = True
                    batch.append(row)
                    if len(batch) >= self.LARGE_SHEET_ROW_THRESHOLD:
                        table_md = self._rows_to_markdown(header_cells, batch, sheet_name)
                        if table_md:
                            segments.append((table_md, self.count_tokens(table_md)))
                        batch = []

                if batch:
                    table_md = self._rows_to_markdown(header_cells, batch, sheet_name)
                    if table_md:
                        segments.append((table_md, self.count_tokens(table_md)))
                elif not has_data_rows:
                    header_md = self._header_to_markdown(header_cells, sheet_name)
                    segments.append((header_md, self.count_tokens(header_md)))
        finally:
            wb.close()

        if not segments:
            logger.warning("Excel 文件没有可提取的内容")
            return

        chunks = self._merge_into_chunks(segments)

        for chunk in chunks:
            chunk.metadata["source_type"] = "excel"
            if filename:
                chunk.metadata["filename"] = filename
            yield chunk

    def _rows_to_markdown(
        self, header: list[str], data_rows: list[tuple], sheet_name: str
    ) -> str:
        """将行数据转为 Markdown 表格"""
        lines = [f"[Sheet: {sheet_name}]"]

        # Header row
        lines.append("| " + " | ".join(header) + " |")
        # Separator
        lines.append("| " + " | ".join("---" for _ in header) + " |")

        for row in data_rows:
            cells = [str(c) if c is not None else "" for c in row]
            # 确保列数与表头一致
            while len(cells) < len(header):
                cells.append("")
            cells = cells[:len(header)]
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def _header_to_markdown(self, header: list[str], sheet_name: str) -> str:
        return "\n".join(
            [
                f"[Sheet: {sheet_name}]",
                "| " + " | ".join(header) + " |",
                "| " + " | ".join("---" for _ in header) + " |",
            ]
        )
