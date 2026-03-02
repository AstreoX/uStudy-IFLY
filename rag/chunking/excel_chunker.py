"""Excel document chunker using openpyxl."""

import io
import logging

import openpyxl

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class ExcelChunker(BaseChunker):
    """Excel 文档切片器（.xlsx, .xls）"""

    # 大 sheet 分段阈值
    LARGE_SHEET_ROW_THRESHOLD = 500

    def chunk(self, content: bytes | str, filename: str | None = None) -> list[Chunk]:
        if isinstance(content, str):
            raise ValueError("Excel content must be bytes, not string")

        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception as e:
            logger.error("无法打开 Excel 文件: %s", e)
            raise ValueError(f"无法解析 Excel 文件: {e}")

        segments: list[str] = []

        try:
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(values_only=True))

                if not rows:
                    continue

                # 提取表头
                header = rows[0]
                header_cells = [str(c) if c is not None else "" for c in header]
                data_rows = rows[1:]

                if not data_rows:
                    # 只有表头，作为单段
                    segments.append(f"[Sheet: {sheet_name}]\n| " + " | ".join(header_cells) + " |")
                    continue

                # 大 sheet 分段处理，每段保留表头
                if len(data_rows) > self.LARGE_SHEET_ROW_THRESHOLD:
                    for i in range(0, len(data_rows), self.LARGE_SHEET_ROW_THRESHOLD):
                        batch = data_rows[i:i + self.LARGE_SHEET_ROW_THRESHOLD]
                        table_md = self._rows_to_markdown(header_cells, batch, sheet_name)
                        if table_md:
                            segments.append(table_md)
                else:
                    table_md = self._rows_to_markdown(header_cells, data_rows, sheet_name)
                    if table_md:
                        segments.append(table_md)
        finally:
            wb.close()

        if not segments:
            logger.warning("Excel 文件没有可提取的内容")
            return []

        chunks = self._merge_into_chunks(segments)

        for chunk in chunks:
            chunk.metadata["source_type"] = "excel"
            if filename:
                chunk.metadata["filename"] = filename

        return chunks

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
