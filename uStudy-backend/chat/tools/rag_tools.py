"""RAG Tools - Document Search and Retrieval (plaintext, no embedding)"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from chat.tools.base import ToolResult
from db.database import get_scoped_session
from rag.retrieval.text_search import TextSearchService

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 2000
MAX_FULL_TEXT_CHARS = 8000
MAX_PAGE_TEXT_EXCERPT_CHARS = 2000
PDF_MIME_TYPE = "application/pdf"
PDF_RENDER_DPI_SEQUENCE = (160, 128, 96)
PDF_RENDER_MAX_BYTES = 4 * 1024 * 1024


RAG_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_keywords",
            "description": (
                "在知识库文档中进行关键词全文搜索（BM25 排名）。"
                "返回匹配词前后各约200字的摘录，自动附带相关图片。"
                "适合查找概念、知识点、文档中的具体内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或短语",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 5，最大 10",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_regex",
            "description": (
                "使用正则表达式在知识库文档中搜索。"
                "适合查找特定格式内容：公式、代码片段、日期、数字等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "PostgreSQL 正则表达式模式（区分大小写）",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回数量，默认 10",
                        "default": 10,
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": (
                "列出当前学习空间中所有已上传的文档和链接。"
                "返回文件名、类型、大小、上传时间和处理状态。"
                "如果 PDF 是扫描件，系统会跳过自动 OCR/文本解析；"
                "请先用本工具获取 document_id，再用 view_document_page 按页查看。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": (
                "读取指定文档的全文内容（或指定片段）。"
                "不传 offset 和 length 时返回全文（超过8000字自动截断）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "文档 UUID（从 list_documents 获取）",
                    },
                    "offset_chars": {
                        "type": "integer",
                        "description": "起始字符偏移（默认 0）",
                        "default": 0,
                    },
                    "length_chars": {
                        "type": "integer",
                        "description": "读取字符数（默认 8000）",
                        "default": 8000,
                    },
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_document_page",
            "description": (
                "将 PDF 文档的指定页渲染为页面截图，并直接作为视觉上下文交给当前对话主 AI 查看。"
                "不调用额外 VLM，不做 OCR，不持久化截图。适合查看课本页、图表、公式、扫描页。"
                "对于扫描件 PDF，应根据当前页内容自行决定下一步继续查看哪一页。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "PDF 文档 UUID（从 list_documents 获取）",
                    },
                    "page_number": {
                        "type": "integer",
                        "description": "要查看的页码，1-based",
                    },
                },
                "required": ["document_id", "page_number"],
            },
        },
    },
]


class RAGToolExecutor:
    """Executor for RAG document tools (plaintext search)."""

    def __init__(self, space_id: UUID) -> None:
        self.space_id = space_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        handlers = {
            "search_keywords": self._search_keywords,
            "search_regex": self._search_regex,
            "list_documents": self._list_documents,
            "read_document": self._read_document,
            "view_document_page": self._view_document_page,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return ToolResult(success=False, data=None, message=f"未知工具: {tool_name}")

        try:
            return await handler(arguments)
        except Exception as exc:
            logger.error("RAG tool '%s' error: %s", tool_name, exc, exc_info=True)
            return ToolResult(success=False, data=None, message=f"工具执行错误: {exc!s}")

    async def _search_keywords(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, data=None, message="搜索查询不能为空")
        if len(query) > MAX_QUERY_LENGTH:
            return ToolResult(success=False, data=None, message=f"查询过长（最大 {MAX_QUERY_LENGTH} 字符）")

        top_k = min(int(args.get("top_k", 5)), 10)

        async with get_scoped_session() as db:
            service = TextSearchService(db)
            results = await service.search(query=query, space_id=self.space_id, top_k=top_k)

        if not results:
            return ToolResult(success=True, data={"results": [], "total": 0}, message="未找到相关内容")

        formatted = [
            {
                "content": r.content,
                "source": r.document_title or r.document_filename,
                "document_id": str(r.document_id),
                "score": round(r.score, 4),
                "images": [
                    _encode_image({**img, "document_id": str(r.document_id)})
                    for img in r.images
                ],
            }
            for r in results
        ]
        return ToolResult(
            success=True,
            data={"results": formatted, "total": len(formatted)},
            message=f"找到 {len(formatted)} 条相关内容",
        )

    async def _search_regex(self, args: dict[str, Any]) -> ToolResult:
        pattern = str(args.get("pattern", "")).strip()
        if not pattern:
            return ToolResult(success=False, data=None, message="正则模式不能为空")

        max_results = min(int(args.get("max_results", 10)), 20)

        async with get_scoped_session() as db:
            service = TextSearchService(db)
            results = await service.search_regex(pattern=pattern, space_id=self.space_id, max_results=max_results)

        if not results:
            return ToolResult(success=True, data={"results": [], "total": 0}, message="未找到匹配内容")

        formatted = [
            {
                "content": r.content,
                "source": r.document_title or r.document_filename,
                "document_id": str(r.document_id),
                "images": [
                    _encode_image({**img, "document_id": str(r.document_id)})
                    for img in r.images
                ],
            }
            for r in results
        ]
        return ToolResult(
            success=True,
            data={"results": formatted, "total": len(formatted)},
            message=f"找到 {len(formatted)} 条匹配内容",
        )

    async def _list_documents(self, args: dict[str, Any]) -> ToolResult:
        from sqlalchemy import select
        from db.models import SpaceDocument, DocumentProcessingTask

        async with get_scoped_session() as db:
            result = await db.execute(
                select(SpaceDocument, DocumentProcessingTask)
                .outerjoin(DocumentProcessingTask, DocumentProcessingTask.document_id == SpaceDocument.id)
                .where(SpaceDocument.space_id == self.space_id)
                .order_by(SpaceDocument.created_at.desc())
            )
            rows = result.fetchall()

        if not rows:
            return ToolResult(success=True, data={"documents": [], "total": 0}, message="知识库中暂无文档")

        docs = [
            {
                "document_id": str(row.SpaceDocument.id),
                "title": row.SpaceDocument.title,
                "type": row.SpaceDocument.doc_type.value,
                "file_size": row.SpaceDocument.file_size,
                "created_at": row.SpaceDocument.created_at.isoformat() if row.SpaceDocument.created_at else None,
                "processing_status": (
                    row.DocumentProcessingTask.status.value
                    if row.DocumentProcessingTask
                    else "unknown"
                ),
            }
            for row in rows
        ]
        return ToolResult(
            success=True,
            data={"documents": docs, "total": len(docs)},
            message=f"共 {len(docs)} 个文档",
        )

    async def _read_document(self, args: dict[str, Any]) -> ToolResult:
        doc_id_str = str(args.get("document_id", "")).strip()
        if not doc_id_str:
            return ToolResult(success=False, data=None, message="document_id 不能为空")

        try:
            doc_id = UUID(doc_id_str)
        except ValueError:
            return ToolResult(success=False, data=None, message="document_id 格式无效")

        offset = max(0, int(args.get("offset_chars", 0)))
        length = min(int(args.get("length_chars", MAX_FULL_TEXT_CHARS)), MAX_FULL_TEXT_CHARS)

        from sqlalchemy import select, text as sa_text
        from db.models import DocumentText
        from rag.retrieval.text_search import resolve_images

        async with get_scoped_session() as db:
            result = await db.execute(
                select(DocumentText).where(
                    DocumentText.document_id == doc_id,
                    DocumentText.space_id == self.space_id,
                )
            )
            doc_text = result.scalar_one_or_none()

        if not doc_text:
            return ToolResult(success=False, data=None, message="文档不存在或尚未处理完成")

        full_content = doc_text.content
        total_chars = len(full_content)
        snippet = full_content[offset: offset + length]

        img_ids_in_snippet = resolve_images(snippet)
        images: list[dict] = []
        if img_ids_in_snippet:
            async with get_scoped_session() as db:
                img_result = await db.execute(
                    sa_text(
                        "SELECT id, file_path, vlm_description, page_num "
                        "FROM document_images WHERE id::text = ANY(:ids)"
                    ),
                    {"ids": img_ids_in_snippet},
                )
                images = [
                    _encode_image({
                        "image_id": str(r.id),
                        "file_path": r.file_path,
                        "vlm_description": r.vlm_description,
                        "page_num": r.page_num,
                        "document_id": str(doc_id),
                    })
                    for r in img_result.fetchall()
                ]

        return ToolResult(
            success=True,
            data={
                "content": snippet,
                "offset": offset,
                "length": len(snippet),
                "total_chars": total_chars,
                "has_more": offset + length < total_chars,
                "images": images,
            },
            message=f"已读取 {len(snippet)} 字符（共 {total_chars} 字符）",
        )

    async def _view_document_page(self, args: dict[str, Any]) -> ToolResult:
        doc_id_str = str(args.get("document_id", "")).strip()
        if not doc_id_str:
            return ToolResult(success=False, data=None, message="document_id 不能为空")

        try:
            doc_id = UUID(doc_id_str)
        except ValueError:
            return ToolResult(success=False, data=None, message="document_id 格式无效")

        try:
            page_number = int(args.get("page_number"))
        except (TypeError, ValueError):
            return ToolResult(success=False, data=None, message="page_number 必须是整数")
        if page_number < 1:
            return ToolResult(success=False, data=None, message="page_number 必须从 1 开始")

        from config import get_settings
        from sqlalchemy import select
        from db.models import DocumentType, SpaceDocument

        async with get_scoped_session() as db:
            result = await db.execute(
                select(SpaceDocument).where(
                    SpaceDocument.id == doc_id,
                    SpaceDocument.space_id == self.space_id,
                )
            )
            document = result.scalar_one_or_none()

        if not document:
            return ToolResult(success=False, data=None, message="文档不存在或无权限访问")

        if document.doc_type != DocumentType.DOCUMENT or not _is_pdf_document(document):
            return ToolResult(success=False, data=None, message="view_document_page 仅支持 PDF 文档")

        settings = get_settings()
        file_path = _resolve_document_file_path(document.url, settings.upload_dir)
        if not file_path.exists():
            return ToolResult(success=False, data=None, message=f"源文件不存在: {file_path}")

        try:
            rendered = await _render_pdf_page(file_path, page_number)
        except ValueError as exc:
            return ToolResult(success=False, data=None, message=str(exc))

        image_base64 = base64.b64encode(rendered["image_bytes"]).decode("ascii")
        data = {
            "document_id": str(document.id),
            "title": document.title,
            "page_number": page_number,
            "page_count": rendered["page_count"],
            "page_text_excerpt": rendered["page_text_excerpt"],
        }
        return ToolResult(
            success=True,
            data=data,
            message=f"已渲染《{document.title}》第 {page_number}/{rendered['page_count']} 页",
            image_base64=image_base64,
        )


def _encode_image(img: dict) -> dict:
    """Return lightweight image metadata without embedding base64 bytes."""
    return {
        "image_id": img.get("image_id"),
        "document_id": img.get("document_id"),
        "page_num": img.get("page_num"),
        "vlm_description": img.get("vlm_description"),
    }


def _is_pdf_document(document: Any) -> bool:
    mime_type = str(getattr(document, "mime_type", "") or "").lower()
    if mime_type == PDF_MIME_TYPE:
        return True

    names = [
        getattr(document, "original_filename", None),
        getattr(document, "title", None),
        getattr(document, "url", None),
    ]
    return any(str(name or "").lower().endswith(".pdf") for name in names)


def _resolve_document_file_path(url: str, upload_dir: str) -> Path:
    relative_path = str(url or "").lstrip("/")
    return Path(upload_dir).parent / relative_path


async def _render_pdf_page(file_path: Path, page_number: int) -> dict[str, Any]:
    """Render a PDF page to PNG bytes without calling any VLM/OCR service."""
    import asyncio

    return await asyncio.to_thread(_render_pdf_page_sync, file_path, page_number)


def _render_pdf_page_sync(file_path: Path, page_number: int) -> dict[str, Any]:
    import fitz

    pdf = fitz.open(str(file_path))
    try:
        page_count = pdf.page_count
        if page_number > page_count:
            raise ValueError(f"页码越界：该 PDF 共 {page_count} 页")

        page = pdf.load_page(page_number - 1)
        page_text = page.get_text("text").strip()
        page_text_excerpt = page_text[:MAX_PAGE_TEXT_EXCERPT_CHARS]

        last_image_bytes: bytes | None = None
        for dpi in PDF_RENDER_DPI_SEQUENCE:
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_bytes = pix.tobytes("png")
            if len(image_bytes) <= PDF_RENDER_MAX_BYTES:
                return {
                    "image_bytes": image_bytes,
                    "page_count": page_count,
                    "page_text_excerpt": page_text_excerpt,
                }
            last_image_bytes = image_bytes

        size_mb = (len(last_image_bytes or b"")) / (1024 * 1024)
        raise ValueError(f"页面截图过大（{size_mb:.1f}MB），请换页或降低渲染质量后重试")
    finally:
        pdf.close()
