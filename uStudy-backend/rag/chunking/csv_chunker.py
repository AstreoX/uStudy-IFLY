"""CSV document chunker using built-in csv module."""

import csv
import io
import logging

import chardet

from rag.chunking.base import BaseChunker, Chunk

logger = logging.getLogger(__name__)


class CSVChunker(BaseChunker):
    """CSV 文档切片器（.csv）"""

    # 大文件分段阈值
    LARGE_FILE_ROW_THRESHOLD = 500

    def chunk(self, content: bytes | str, filename: str | None = None) -> list[Chunk]:
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
            return []

        try:
            # 自动检测分隔符
            dialect = csv.Sniffer().sniff(text[:8192])
            reader = csv.reader(io.StringIO(text), dialect)
        except csv.Error:
            # 检测失败，默认逗号分隔
            reader = csv.reader(io.StringIO(text))

        rows = list(reader)
        if not rows:
            logger.warning("CSV 文件没有数据行")
            return []

        header = rows[0]
        data_rows = rows[1:]

        if not data_rows:
            # 只有表头
            segments = ["| " + " | ".join(header) + " |"]
        elif len(data_rows) > self.LARGE_FILE_ROW_THRESHOLD:
            # 大文件分段，每段保留表头
            segments = []
            for i in range(0, len(data_rows), self.LARGE_FILE_ROW_THRESHOLD):
                batch = data_rows[i:i + self.LARGE_FILE_ROW_THRESHOLD]
                table_md = self._rows_to_markdown(header, batch)
                if table_md:
                    segments.append(table_md)
        else:
            segments = [self._rows_to_markdown(header, data_rows)]

        segments = [s for s in segments if s]
        if not segments:
            logger.warning("CSV 文件没有可提取的内容")
            return []

        chunks = self._merge_into_chunks(segments)

        for chunk in chunks:
            chunk.metadata["source_type"] = "csv"
            if filename:
                chunk.metadata["filename"] = filename

        return chunks

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
