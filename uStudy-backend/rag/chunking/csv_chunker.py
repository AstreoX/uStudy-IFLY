"""CSV document chunker using built-in csv module."""

import csv
import io
import logging
from typing import Iterator

import chardet

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class CSVChunker(BaseChunker):
    """CSV 文档切片器（.csv）"""

    # 大文件分段阈值
    LARGE_FILE_ROW_THRESHOLD = 500

    def iter_chunks(
        self, content: bytes | str, filename: str | None = None
    ) -> Iterator[Chunk]:
        # 编码检测
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
            logger.warning("CSV 文件内容为空")
            return

        try:
            # 自动检测分隔符
            dialect = csv.Sniffer().sniff(text[:8192])
            reader = csv.reader(io.StringIO(text), dialect)
        except csv.Error:
            # 检测失败，默认逗号分隔
            reader = csv.reader(io.StringIO(text))

        header = next(reader, None)
        if not header:
            logger.warning("CSV 文件没有数据行")
            return

        segments: list[tuple[str, int]] = []
        batch: list[list[str]] = []
        has_data_rows = False
        for row in reader:
            has_data_rows = True
            batch.append(row)
            if len(batch) >= self.LARGE_FILE_ROW_THRESHOLD:
                table_md = self._rows_to_markdown(header, batch)
                if table_md:
                    segments.append((table_md, self.count_tokens(table_md)))
                batch = []

        if batch:
            table_md = self._rows_to_markdown(header, batch)
            if table_md:
                segments.append((table_md, self.count_tokens(table_md)))
        elif not has_data_rows:
            header_md = self._header_to_markdown(header)
            segments.append((header_md, self.count_tokens(header_md)))

        if not segments:
            logger.warning("CSV 文件没有可提取的内容")
            return

        chunks = self._merge_into_chunks(segments)

        for chunk in chunks:
            chunk.metadata["source_type"] = "csv"
            if filename:
                chunk.metadata["filename"] = filename
            yield chunk

    def _rows_to_markdown(self, header: list[str], data_rows: list[list[str]]) -> str:
        """将行数据转为 Markdown 表格"""
        lines: list[str] = []
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")

        for row in data_rows:
            # 确保列数与表头一致
            while len(row) < len(header):
                row.append("")
            cells = row[:len(header)]
            lines.append("| " + " | ".join(cells) + " |")

        return "\n".join(lines)

    def _header_to_markdown(self, header: list[str]) -> str:
        return "\n".join(
            [
                "| " + " | ".join(header) + " |",
                "| " + " | ".join("---" for _ in header) + " |",
            ]
        )
