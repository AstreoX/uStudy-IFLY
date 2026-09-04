"""RAG Tools - Document Search and Retrieval (plaintext, no embedding)"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from chat.tools.base import ToolMedia, ToolResult
from db.database import get_scoped_session
from rag.retrieval.text_search import TextSearchService

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 2000
MAX_REGEX_PATTERN_LENGTH = 256
MAX_FULL_TEXT_CHARS = 8000
MAX_PAGE_TEXT_EXCERPT_CHARS = 2000
PDF_MIME_TYPE = "application/pdf"
PDF_RENDER_DPI_SEQUENCE = (160, 128, 96)
PDF_RENDER_MAX_BYTES = 4 * 1024 * 1024

_NESTED_REGEX_QUANTIFIER = re.compile(
    r"\((?:[^()\\]|\\.)*[+*](?:[^()\\]|\\.)*\)\s*(?:[+*]|\{\d)",
)
_REGEX_BACKREFERENCE = re.compile(r"\\[1-9]")


def _regex_validation_error(pattern: str) -> str | None:
    if len(pattern) > MAX_REGEX_PATTERN_LENGTH:
        return f"正则模式过长（最大 {MAX_REGEX_PATTERN_LENGTH} 字符）"
    if any(ord(character) < 32 for character in pattern):
        return "正则模式不能包含控制字符"
    if _NESTED_REGEX_QUANTIFIER.search(pattern):
        return "正则模式包含高开销的嵌套重复结构"
    if pattern.count(".*") > 2 or _REGEX_BACKREFERENCE.search(pattern):
        return "正则模式包含高开销结构"
    return None


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
                        "minimum": 1,
                        "maximum": 10,
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
                        "maxLength": 256,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回数量，默认 10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
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
                "返回文件名、类型、大小、处理阶段以及 PDF 视觉目录状态。"
                "扫描 PDF 可继续用 get_document_outline 和 view_document_pages 渐进查看。"
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
                "读取指定文档的全文内容（或指定片段）；Agentic PDF 返回生成的目录 Markdown。"
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
                        "minimum": 0,
                    },
                    "length_chars": {
                        "type": "integer",
                        "description": "读取字符数（默认 8000）",
                        "default": 8000,
                        "minimum": 1,
                        "maximum": 8000,
                    },
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_outline",
            "description": (
                "读取 PDF 的结构化目录索引、印刷页码与 PDF 物理页码映射。"
                "回答扫描教材问题时先读目录，再按 resolved_pdf_page 查看页面。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "PDF 文档 UUID（从 list_documents 获取）",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "目录条目起始偏移，默认 0",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "条目数量，默认 100，最大 500",
                        "default": 100,
                    },
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_document_pages",
            "description": (
                "渐进查看已生成的 PDF 页面图。先用每图4页粗定位，再用2页缩小范围，"
                "最后用单页精读。physical_page 始终是从1开始的PDF物理页，不是书本印刷页。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "PDF 文档 UUID",
                    },
                    "physical_page": {
                        "type": "integer",
                        "description": "目标 PDF 物理页，1-based",
                    },
                    "pages_per_image": {
                        "type": "integer",
                        "enum": [1, 2, 4],
                        "description": "每张图包含的连续页数",
                        "default": 4,
                    },
                    "count": {
                        "type": "integer",
                        "description": "连续返回的图片数，1至4",
                        "default": 1,
                    },
                },
                "required": ["document_id", "physical_page", "pages_per_image"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_document_page",
            "description": (
                "查看 PDF 的指定单页并直接作为视觉上下文交给当前对话主 AI。"
                "优先读取私有单页缓存；旧文档才即时渲染。不调用额外 VLM，不做 OCR。"
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

RAG_TOOL_NAMES = frozenset(tool["function"]["name"] for tool in RAG_TOOLS)


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
            "get_document_outline": self._get_document_outline,
            "view_document_pages": self._view_document_pages,
            "view_document_page": self._view_document_page,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return ToolResult(
                success=False, data=None, message=f"未知工具: {tool_name}"
            )

        try:
            return await handler(arguments)
        except Exception as exc:
            logger.exception("RAG tool '%s' failed", tool_name)
            return ToolResult(
                success=False, data=None, message=f"工具执行错误: {exc!s}"
            )

    async def _search_keywords(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(success=False, data=None, message="搜索查询不能为空")
        if len(query) > MAX_QUERY_LENGTH:
            return ToolResult(
                success=False,
                data=None,
                message=f"查询过长（最大 {MAX_QUERY_LENGTH} 字符）",
            )

        try:
            top_k = int(args.get("top_k", 5))
        except (TypeError, ValueError):
            return ToolResult(success=False, data=None, message="top_k 必须是整数")
        if not 1 <= top_k <= 10:
            return ToolResult(
                success=False, data=None, message="top_k 必须在 1 到 10 之间"
            )

        async with get_scoped_session() as db:
            service = TextSearchService(db)
            results = await service.search(
                query=query, space_id=self.space_id, top_k=top_k
            )

        if not results:
            return ToolResult(
                success=True, data={"results": [], "total": 0}, message="未找到相关内容"
            )

        formatted = [
            {
                "chunk_id": str(r.chunk_id),
                "content": r.content,
                "source": r.document_title or r.document_filename,
                "document_id": str(r.document_id),
                "score": round(r.score, 4),
                "retrieval_score": (
                    round(r.retrieval_score, 4)
                    if r.retrieval_score is not None
                    else None
                ),
                "retrieval_source": r.retrieval_source,
                "chunk_kind": (r.metadata or {}).get("chunk_kind"),
                "page_number": (r.metadata or {}).get("page_number"),
                "page_end": (r.metadata or {}).get("page_end"),
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
        validation_error = _regex_validation_error(pattern)
        if validation_error:
            return ToolResult(success=False, data=None, message=validation_error)

        try:
            max_results = int(args.get("max_results", 10))
        except (TypeError, ValueError):
            return ToolResult(
                success=False, data=None, message="max_results 必须是整数"
            )
        if not 1 <= max_results <= 20:
            return ToolResult(
                success=False, data=None, message="max_results 必须在 1 到 20 之间"
            )

        from rag.retrieval.text_search import TextSearchTimeoutError

        async with get_scoped_session() as db:
            service = TextSearchService(db)
            try:
                results = await service.search_regex(
                    pattern=pattern, space_id=self.space_id, max_results=max_results
                )
            except TextSearchTimeoutError:
                return ToolResult(
                    success=False,
                    data={"code": "regex_timeout"},
                    message="正则搜索超时，请缩小或简化模式",
                )

        if not results:
            return ToolResult(
                success=True, data={"results": [], "total": 0}, message="未找到匹配内容"
            )

        formatted = [
            {
                "chunk_id": str(r.chunk_id),
                "content": r.content,
                "source": r.document_title or r.document_filename,
                "document_id": str(r.document_id),
                "retrieval_source": r.retrieval_source,
                "chunk_kind": (r.metadata or {}).get("chunk_kind"),
                "page_number": (r.metadata or {}).get("page_number"),
                "page_end": (r.metadata or {}).get("page_end"),
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
        from sqlalchemy import and_, select

        from db.models import DocumentProcessingTask, PdfVisualIndex, SpaceDocument

        async with get_scoped_session() as db:
            result = await db.execute(
                select(SpaceDocument, DocumentProcessingTask, PdfVisualIndex)
                .outerjoin(
                    DocumentProcessingTask,
                    DocumentProcessingTask.document_id == SpaceDocument.id,
                )
                .outerjoin(
                    PdfVisualIndex,
                    and_(
                        PdfVisualIndex.document_id == SpaceDocument.id,
                        PdfVisualIndex.is_current.is_(True),
                        PdfVisualIndex.state == "published",
                    ),
                )
                .where(SpaceDocument.space_id == self.space_id)
                .order_by(SpaceDocument.created_at.desc())
            )
            rows = result.fetchall()

        if not rows:
            return ToolResult(
                success=True,
                data={"documents": [], "total": 0},
                message="知识库中暂无文档",
            )

        docs = [
            {
                "document_id": str(row.SpaceDocument.id),
                "title": row.SpaceDocument.title,
                "type": row.SpaceDocument.doc_type.value,
                "file_size": row.SpaceDocument.file_size,
                "created_at": row.SpaceDocument.created_at.isoformat()
                if row.SpaceDocument.created_at
                else None,
                "processing_status": (
                    row.DocumentProcessingTask.status.value
                    if row.DocumentProcessingTask
                    else "unknown"
                ),
                "processing_stage": (
                    row.DocumentProcessingTask.stage
                    if row.DocumentProcessingTask
                    else None
                ),
                "visual_index_status": (
                    row.PdfVisualIndex.state if row.PdfVisualIndex else None
                ),
                "page_count": (
                    row.PdfVisualIndex.page_count if row.PdfVisualIndex else None
                ),
                "outline_status": (
                    row.PdfVisualIndex.outline_status if row.PdfVisualIndex else None
                ),
                "page_offset": (
                    row.PdfVisualIndex.page_offset if row.PdfVisualIndex else None
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

        try:
            offset = int(args.get("offset_chars", 0))
            length = int(args.get("length_chars", MAX_FULL_TEXT_CHARS))
        except (TypeError, ValueError):
            return ToolResult(
                success=False,
                data=None,
                message="offset_chars 和 length_chars 必须是整数",
            )
        if offset < 0:
            return ToolResult(
                success=False, data=None, message="offset_chars 不能为负数"
            )
        if not 1 <= length <= MAX_FULL_TEXT_CHARS:
            return ToolResult(
                success=False,
                data=None,
                message=f"length_chars 必须在 1 到 {MAX_FULL_TEXT_CHARS} 之间",
            )

        from sqlalchemy import select

        from db.models import DocumentImage, DocumentText
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
            return ToolResult(
                success=False, data=None, message="文档不存在或尚未处理完成"
            )

        full_content = doc_text.content
        total_chars = len(full_content)
        snippet = full_content[offset : offset + length]

        img_ids_in_snippet = resolve_images(snippet)
        images: list[dict] = []
        if img_ids_in_snippet:
            valid_image_ids: list[UUID] = []
            for image_id in img_ids_in_snippet:
                try:
                    valid_image_ids.append(UUID(image_id))
                except ValueError:
                    continue
            async with get_scoped_session() as db:
                image_rows = list(
                    (
                        await db.scalars(
                            select(DocumentImage).where(
                                DocumentImage.id.in_(valid_image_ids),
                                DocumentImage.document_id == doc_id,
                                DocumentImage.space_id == self.space_id,
                            )
                        )
                    ).all()
                )
                images = [
                    _encode_image(
                        {
                            "image_id": str(r.id),
                            "file_path": r.file_path,
                            "vlm_description": r.vlm_description,
                            "page_num": r.page_num,
                            "document_id": str(doc_id),
                        }
                    )
                    for r in image_rows
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

    async def _get_document_outline(self, args: dict[str, Any]) -> ToolResult:
        doc_id_str = str(args.get("document_id", "")).strip()
        try:
            doc_id = UUID(doc_id_str)
        except (TypeError, ValueError):
            return ToolResult(success=False, data=None, message="document_id 格式无效")

        try:
            entry_offset = max(0, int(args.get("offset", 0)))
            limit = int(args.get("limit", 100))
        except (TypeError, ValueError):
            return ToolResult(
                success=False, data=None, message="offset 和 limit 必须是整数"
            )
        if limit < 1 or limit > 500:
            return ToolResult(
                success=False, data=None, message="limit 必须在 1 到 500 之间"
            )

        from sqlalchemy import select

        from db.models import PdfVisualIndex, SpaceDocument

        async with get_scoped_session() as db:
            result = await db.execute(
                select(PdfVisualIndex, SpaceDocument)
                .join(SpaceDocument, SpaceDocument.id == PdfVisualIndex.document_id)
                .where(
                    PdfVisualIndex.document_id == doc_id,
                    PdfVisualIndex.space_id == self.space_id,
                    SpaceDocument.space_id == self.space_id,
                    PdfVisualIndex.is_current.is_(True),
                    PdfVisualIndex.state == "published",
                )
            )
            row = result.first()

        if row is None:
            return ToolResult(
                success=False,
                data={"code": "pdf_visual_index_not_ready"},
                message="PDF 视觉索引尚未处理完成",
            )

        visual_index, document = row
        entries = list(visual_index.outline_entries or [])
        page = entries[entry_offset : entry_offset + limit]
        offset_value = visual_index.page_offset
        return ToolResult(
            success=True,
            data={
                "document_id": str(document.id),
                "title": document.title,
                "generation": visual_index.generation,
                "outline_status": visual_index.outline_status,
                "page_count": visual_index.page_count,
                "toc_physical_page_start": visual_index.toc_pdf_page_start,
                "toc_physical_page_end": visual_index.toc_pdf_page_end,
                "page_offset": offset_value,
                "printed_page_1_pdf_page": (
                    offset_value + 1 if offset_value is not None else None
                ),
                "mapping_rule": "physical_pdf_page = printed_page_number + page_offset",
                "entries": page,
                "offset": entry_offset,
                "limit": limit,
                "total": len(entries),
                "has_more": entry_offset + limit < len(entries),
            },
            message=(
                f"已读取《{document.title}》目录条目 "
                f"{entry_offset + 1}-{entry_offset + len(page)} / {len(entries)}"
                if page
                else f"《{document.title}》没有可返回的目录条目"
            ),
        )

    async def _view_document_pages(self, args: dict[str, Any]) -> ToolResult:
        doc_id_str = str(args.get("document_id", "")).strip()
        try:
            doc_id = UUID(doc_id_str)
        except (TypeError, ValueError):
            return ToolResult(success=False, data=None, message="document_id 格式无效")
        try:
            physical_page = int(args.get("physical_page"))
            pages_per_image = int(args.get("pages_per_image", 4))
            count = int(args.get("count", 1))
        except (TypeError, ValueError):
            return ToolResult(success=False, data=None, message="页面参数必须是整数")
        if physical_page < 1:
            return ToolResult(
                success=False, data=None, message="physical_page 必须从 1 开始"
            )
        if pages_per_image not in {1, 2, 4}:
            return ToolResult(
                success=False, data=None, message="pages_per_image 只能是 1、2 或 4"
            )
        if count < 1 or count > 4:
            return ToolResult(
                success=False, data=None, message="count 必须在 1 到 4 之间"
            )

        from sqlalchemy import select

        from config import get_settings
        from db.models import PdfPageAsset, PdfVisualIndex, SpaceDocument

        aligned_start = _aligned_asset_start(physical_page, pages_per_image)
        async with get_scoped_session() as db:
            index_result = await db.execute(
                select(PdfVisualIndex, SpaceDocument)
                .join(SpaceDocument, SpaceDocument.id == PdfVisualIndex.document_id)
                .where(
                    PdfVisualIndex.document_id == doc_id,
                    PdfVisualIndex.space_id == self.space_id,
                    SpaceDocument.space_id == self.space_id,
                    PdfVisualIndex.is_current.is_(True),
                    PdfVisualIndex.state == "published",
                )
            )
            row = index_result.first()
            if row is None:
                return ToolResult(
                    success=False,
                    data={"code": "pdf_visual_index_not_ready"},
                    message="PDF 视觉索引尚未处理完成",
                )
            visual_index, document = row
            if physical_page > visual_index.page_count:
                return ToolResult(
                    success=False,
                    data={"page_count": visual_index.page_count},
                    message=f"页码越界：该 PDF 共 {visual_index.page_count} 页",
                )
            assets = list(
                (
                    await db.scalars(
                        select(PdfPageAsset)
                        .where(
                            PdfPageAsset.index_id == visual_index.id,
                            PdfPageAsset.document_id == doc_id,
                            PdfPageAsset.space_id == self.space_id,
                            PdfPageAsset.pages_per_image == pages_per_image,
                            PdfPageAsset.physical_page_start >= aligned_start,
                        )
                        .order_by(PdfPageAsset.physical_page_start)
                        .limit(count)
                    )
                ).all()
            )

        if not assets or any(
            asset.physical_page_start != aligned_start + index * pages_per_image
            for index, asset in enumerate(assets)
        ):
            return ToolResult(
                success=False,
                data={"code": "pdf_page_asset_missing"},
                message="目标页面资产缺失，请重新处理文档",
            )

        cfg = get_settings()
        private_root = Path(cfg.pdf_private_dir).resolve()
        scoped_asset_root = (
            private_root
            / str(self.space_id)
            / str(doc_id)
            / f"v{int(visual_index.generation):06d}"
        ).resolve()
        transient: list[ToolMedia] = []
        metadata: list[dict[str, Any]] = []
        total_bytes = 0
        for asset in assets:
            try:
                path = _resolve_private_asset_path(
                    private_root,
                    asset.storage_key,
                    required_root=scoped_asset_root,
                )
            except ValueError:
                return ToolResult(
                    success=False,
                    data={"code": "pdf_page_asset_missing"},
                    message="页面资产不可用，请重新处理文档",
                )
            image_bytes = await _read_private_asset(path)
            if (
                len(image_bytes) != asset.byte_size
                or hashlib.sha256(image_bytes).hexdigest() != asset.sha256
            ):
                return ToolResult(
                    success=False,
                    data={"code": "pdf_page_asset_corrupt"},
                    message="页面资产校验失败，请重新处理文档",
                )
            total_bytes += len(image_bytes)
            if total_bytes > cfg.rag_media_max_bytes:
                break
            label = (
                f"《{document.title}》PDF 物理页 "
                f"{asset.physical_page_start}-{asset.physical_page_end}，"
                f"每图 {asset.pages_per_image} 页"
            )
            transient.append(
                ToolMedia(
                    base64_data=base64.b64encode(image_bytes).decode("ascii"),
                    mime_type=asset.mime_type,
                    label=label,
                    physical_page_start=asset.physical_page_start,
                    physical_page_end=asset.physical_page_end,
                )
            )
            metadata.append(
                {
                    "physical_page_start": asset.physical_page_start,
                    "physical_page_end": asset.physical_page_end,
                    "pages_per_image": asset.pages_per_image,
                    "mime_type": asset.mime_type,
                    "width": asset.width,
                    "height": asset.height,
                    "byte_size": asset.byte_size,
                }
            )

        if not transient:
            return ToolResult(
                success=False,
                data={"code": "pdf_media_limit_exceeded"},
                message="页面图片超过本轮视觉上下文大小限制",
            )
        return ToolResult(
            success=True,
            data={
                "document_id": str(document.id),
                "title": document.title,
                "generation": visual_index.generation,
                "page_count": visual_index.page_count,
                "requested_physical_page": physical_page,
                "pages_per_image": pages_per_image,
                "assets": metadata,
            },
            message=f"已加载《{document.title}》{len(transient)} 张渐进页面图",
            media=transient,
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
            return ToolResult(
                success=False, data=None, message="page_number 必须是整数"
            )
        if page_number < 1:
            return ToolResult(
                success=False, data=None, message="page_number 必须从 1 开始"
            )

        cached = await self._view_document_pages(
            {
                "document_id": doc_id_str,
                "physical_page": page_number,
                "pages_per_image": 1,
                "count": 1,
            }
        )
        if cached.success:
            cached.data["page_number"] = page_number
            cached.message = f"已加载 PDF 第 {page_number} 页的单页缓存"
            return cached
        cached_code = cached.data.get("code") if isinstance(cached.data, dict) else None
        if cached_code != "pdf_visual_index_not_ready":
            return cached

        from sqlalchemy import select

        from config import get_settings
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
            return ToolResult(
                success=False, data=None, message="文档不存在或无权限访问"
            )

        if document.doc_type != DocumentType.DOCUMENT or not _is_pdf_document(document):
            return ToolResult(
                success=False, data=None, message="view_document_page 仅支持 PDF 文档"
            )

        settings = get_settings()
        file_path = _resolve_document_file_path(document.url, settings.upload_dir)
        if not file_path.exists():
            return ToolResult(
                success=False, data=None, message=f"源文件不存在: {file_path}"
            )

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
            media=[
                ToolMedia(
                    base64_data=image_base64,
                    mime_type="image/png",
                    label=f"《{document.title}》PDF 物理页 {page_number}",
                    physical_page_start=page_number,
                    physical_page_end=page_number,
                )
            ],
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
    root = Path(upload_dir).resolve()
    value = str(url or "")
    relative_path = (
        value[len("/uploads/") :]
        if value.startswith("/uploads/")
        else value.lstrip("/")
    )
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("document path is outside the upload root")
    return candidate


def _aligned_asset_start(physical_page: int, pages_per_image: int) -> int:
    if physical_page < 1 or pages_per_image not in {1, 2, 4}:
        raise ValueError("invalid physical page or pages_per_image")
    return ((physical_page - 1) // pages_per_image) * pages_per_image + 1


def _resolve_private_asset_path(
    private_root: Path,
    storage_key: str,
    *,
    required_root: Path | None = None,
) -> Path:
    root = private_root.resolve()
    candidate = (root / storage_key).resolve()
    scope = (required_root or root).resolve()
    if (
        not scope.is_relative_to(root)
        or not candidate.is_relative_to(scope)
        or not candidate.is_file()
    ):
        raise ValueError("private PDF asset is missing or outside its root")
    return candidate


async def _read_private_asset(path: Path) -> bytes:
    import asyncio

    return await asyncio.to_thread(path.read_bytes)


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
