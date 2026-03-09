"""Note Tools - AI 创建学习笔记"""

import logging
import re
from typing import Any
from uuid import UUID, uuid4

import httpx

from chat.tools.base import ToolResult
from db.database import get_scoped_session
from graph.service import GraphService
from notes.schemas import NoteCreate, NoteUpdate
from notes.service import NoteService
from upload.storage import get_storage

logger = logging.getLogger(__name__)

# Image download constraints
_IMAGE_DOWNLOAD_TIMEOUT = 10  # seconds
_IMAGE_MAX_SIZE = 10 * 1024 * 1024  # 10MB
_IMAGE_URL_PATTERN = re.compile(r'!\[([^\]]*)\]\((https?://[^)]+)\)')

# Allowed image extensions
_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico"}


# ============ Tool Definition ============

NOTE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": (
                "为用户创建学习笔记卡片。支持 Markdown 格式，可包含图片引用。"
                "图片 URL 会自动下载并存储到本地。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "node_label": {
                        "type": "string",
                        "description": (
                            "挂载到的知识节点名称。传 'FREE' 表示自由笔记（不挂载到任何节点）"
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": "笔记内容（Markdown 格式，可包含 ![alt](url) 图片引用）",
                    },
                    "title": {
                        "type": "string",
                        "description": "笔记标题（可选）",
                    },
                },
                "required": ["node_label", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "查看某个知识节点下的笔记列表（粗略概览）",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_label": {
                        "type": "string",
                        "description": (
                            "节点名称，传 'FREE' 查看自由笔记，传 'ALL' 查看所有笔记"
                        ),
                    },
                },
                "required": ["node_label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_note_detail",
            "description": "查看笔记的完整内容（带行号，方便引用特定行）",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "笔记 ID（从 list_notes 获取）",
                    },
                },
                "required": ["note_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_note",
            "description": (
                "更新笔记内容。支持两种模式：\n"
                "1. 按行号区间替换局部内容（指定 line_start/line_end）\n"
                "2. 整篇替换（不指定行号）\n"
                "更新后返回带行号的新内容，方便确认结果。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "笔记 ID",
                    },
                    "title": {
                        "type": "string",
                        "description": "新标题（可选，不传则不改）",
                    },
                    "line_start": {
                        "type": "integer",
                        "description": "起始行号（含），从 1 开始（可选）",
                    },
                    "line_end": {
                        "type": "integer",
                        "description": "结束行号（含）（可选，不传则等于 line_start）",
                    },
                    "new_content": {
                        "type": "string",
                        "description": "替换内容（指定行号时替换该区间；否则替换整篇内容）",
                    },
                },
                "required": ["note_id", "new_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": "删除指定笔记（同时清理附件文件）",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "笔记 ID（从 list_notes 获取）",
                    },
                },
                "required": ["note_id"],
            },
        },
    },
]

NOTE_TOOL_NAMES: set[str] = {t["function"]["name"] for t in NOTE_TOOLS}


# ============ Executor ============


class NoteToolExecutor:
    """Executor for note-related tools"""

    def __init__(self, user_id: UUID, space_id: UUID) -> None:
        self.user_id = user_id
        self.space_id = space_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        dispatch = {
            "create_note": ("创建笔记", self._create_note),
            "list_notes": ("查询笔记列表", self._list_notes),
            "view_note_detail": ("查看笔记详情", self._view_note_detail),
            "update_note": ("更新笔记", self._update_note),
            "delete_note": ("删除笔记", self._delete_note),
        }

        entry = dispatch.get(tool_name)
        if not entry:
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的工具: {tool_name}",
            )

        label, handler = entry
        try:
            return await handler(arguments)
        except Exception as e:
            logger.error(f"Note tool execution error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"{label}失败: {e!s}",
            )

    async def _create_note(self, args: dict[str, Any]) -> ToolResult:
        node_label = args.get("node_label", "FREE")
        content = args.get("content", "")
        title = args.get("title")

        # 1. Resolve node_id from label
        node_id = None
        if node_label and node_label.upper() != "FREE":
            async with get_scoped_session() as db:
                graph_service = GraphService(db)
                node = await graph_service.get_node_by_label(self.space_id, node_label)
                if node:
                    node_id = node.id
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        message=f"未找到名为「{node_label}」的知识节点，请检查节点名称是否正确",
                    )

        # 2. Download and replace external images in content
        content, download_warnings = await self._process_images(content)

        # 3. Create note via NoteService
        async with get_scoped_session() as db:
            note_service = NoteService(db)
            note_create = NoteCreate(
                title=title,
                content=content,
                node_id=node_id,
            )
            note = await note_service.create_note(
                self.user_id, self.space_id, note_create
            )

        # 4. Build result message
        location = f"节点「{node_label}」" if node_id else "自由笔记"
        message = f"已创建笔记「{title or '无标题'}」，位置：{location}"
        if download_warnings:
            message += f"\n注意：{'; '.join(download_warnings)}"

        return ToolResult(
            success=True,
            data={
                "note_id": str(note.id),
                "title": note.title,
                "node_label": node_label if node_id else "FREE",
            },
            message=message,
        )

    async def _list_notes(self, args: dict[str, Any]) -> ToolResult:
        node_label = args.get("node_label", "ALL")
        upper_label = node_label.upper()

        node_id = None
        free_only = False

        if upper_label == "FREE":
            free_only = True
        elif upper_label != "ALL":
            async with get_scoped_session() as db:
                graph_service = GraphService(db)
                node = await graph_service.get_node_by_label(self.space_id, node_label)
                if not node:
                    return ToolResult(
                        success=False,
                        data=None,
                        message=f"未找到名为「{node_label}」的知识节点",
                    )
                node_id = node.id

        async with get_scoped_session() as db:
            note_service = NoteService(db)
            notes = await note_service.list_notes(
                self.user_id, self.space_id,
                node_id=node_id, free_only=free_only,
            )

        if not notes:
            return ToolResult(
                success=True,
                data={"notes": []},
                message="没有找到笔记",
            )

        items = []
        lines = []
        for i, n in enumerate(notes, 1):
            preview = (n.content or "")[:100]
            if len(n.content or "") > 100:
                preview += "..."
            items.append({
                "note_id": str(n.id),
                "title": n.title or "无标题",
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
                "attachment_count": n.attachment_count,
                "content_preview": preview,
            })
            lines.append(
                f"{i}. [{items[-1]['title']}] (id={items[-1]['note_id']}) "
                f"附件:{n.attachment_count} — {preview}"
            )

        return ToolResult(
            success=True,
            data={"notes": items},
            message=f"共 {len(items)} 篇笔记：\n" + "\n".join(lines),
        )

    async def _view_note_detail(self, args: dict[str, Any]) -> ToolResult:
        note_id_str = args.get("note_id", "")
        try:
            note_id = UUID(note_id_str)
        except (ValueError, AttributeError):
            return ToolResult(
                success=False,
                data=None,
                message=f"无效的笔记 ID: {note_id_str}",
            )

        async with get_scoped_session() as db:
            note_service = NoteService(db)
            note = await note_service.get_note(self.user_id, self.space_id, note_id)

        content = note.content or ""
        numbered_lines = [
            f"{i + 1}\t{line}" for i, line in enumerate(content.split("\n"))
        ]
        numbered_content = "\n".join(numbered_lines)

        attachments = [
            {"id": str(a.id), "file_name": a.original_filename, "file_url": a.file_url}
            for a in (note.attachments or [])
        ]

        return ToolResult(
            success=True,
            data={
                "note_id": str(note.id),
                "title": note.title,
                "numbered_content": numbered_content,
                "attachments": attachments,
            },
            message=(
                f"笔记「{note.title or '无标题'}」内容：\n"
                f"{numbered_content}"
                + (f"\n\n附件({len(attachments)}): "
                   + ", ".join(a["file_name"] for a in attachments)
                   if attachments else "")
            ),
        )

    async def _update_note(self, args: dict[str, Any]) -> ToolResult:
        note_id_str = args.get("note_id", "")
        try:
            note_id = UUID(note_id_str)
        except (ValueError, AttributeError):
            return ToolResult(
                success=False,
                data=None,
                message=f"无效的笔记 ID: {note_id_str}",
            )

        new_content = args.get("new_content", "")
        title = args.get("title")
        line_start = args.get("line_start")
        line_end = args.get("line_end")

        # Build final content
        if line_start is not None:
            if line_end is None:
                line_end = line_start

            # Need current content for line-based editing
            async with get_scoped_session() as db:
                note_service = NoteService(db)
                current = await note_service.get_note(self.user_id, self.space_id, note_id)

            lines = (current.content or "").split("\n")
            total = len(lines)

            if line_start < 1 or line_end < line_start or line_end > total:
                return ToolResult(
                    success=False,
                    data=None,
                    message=(
                        f"行号范围无效: line_start={line_start}, line_end={line_end}，"
                        f"笔记共 {total} 行（有效范围 1~{total}）"
                    ),
                )

            lines[line_start - 1 : line_end] = new_content.split("\n")
            final_content = "\n".join(lines)
        else:
            final_content = new_content

        # Build update data via constructor so model_fields_set is correct
        update_kwargs: dict[str, Any] = {"content": final_content}
        if title is not None:
            update_kwargs["title"] = title
        update_data = NoteUpdate(**update_kwargs)

        async with get_scoped_session() as db:
            note_service = NoteService(db)
            updated = await note_service.update_note(
                self.user_id, self.space_id, note_id, update_data
            )

        # Return numbered content (same format as view_note_detail)
        content = updated.content or ""
        numbered_lines = [
            f"{i + 1}\t{line}" for i, line in enumerate(content.split("\n"))
        ]
        numbered_content = "\n".join(numbered_lines)

        mode = f"行 {line_start}~{line_end} 局部替换" if line_start is not None else "整篇替换"
        return ToolResult(
            success=True,
            data={
                "note_id": str(updated.id),
                "title": updated.title,
                "numbered_content": numbered_content,
            },
            message=(
                f"已更新笔记「{updated.title or '无标题'}」（{mode}）：\n"
                f"{numbered_content}"
            ),
        )

    async def _delete_note(self, args: dict[str, Any]) -> ToolResult:
        note_id_str = args.get("note_id", "")
        try:
            note_id = UUID(note_id_str)
        except (ValueError, AttributeError):
            return ToolResult(
                success=False,
                data=None,
                message=f"无效的笔记 ID: {note_id_str}",
            )

        async with get_scoped_session() as db:
            note_service = NoteService(db)
            await note_service.delete_note(self.user_id, self.space_id, note_id)

        return ToolResult(
            success=True,
            data={"note_id": note_id_str},
            message=f"已删除笔记 (id={note_id_str})",
        )

    async def _process_images(self, content: str) -> tuple[str, list[str]]:
        """Download external images and replace URLs with local paths.

        Returns:
            (processed_content, warnings)
        """
        matches = _IMAGE_URL_PATTERN.findall(content)
        if not matches:
            return content, []

        warnings: list[str] = []
        storage = get_storage()

        async with httpx.AsyncClient(
            timeout=_IMAGE_DOWNLOAD_TIMEOUT,
            follow_redirects=True,
        ) as client:
            for alt_text, url in matches:
                local_path = await self._download_and_save_image(
                    client, storage, url, warnings
                )
                if local_path:
                    content = content.replace(f"({url})", f"({local_path})")

        return content, warnings

    async def _download_and_save_image(
        self,
        client: httpx.AsyncClient,
        storage: Any,
        url: str,
        warnings: list[str],
    ) -> str | None:
        """Download a single image and save to storage. Returns local path or None."""
        try:
            response = await client.get(url)
            response.raise_for_status()

            data = response.content
            if len(data) > _IMAGE_MAX_SIZE:
                warnings.append(f"图片过大已跳过（>{_IMAGE_MAX_SIZE // 1024 // 1024}MB）: {url[:80]}")
                return None

            # Determine extension from URL or content-type
            ext = self._guess_extension(url, response.headers.get("content-type", ""))
            filename = f"{uuid4()}.{ext}"

            local_path = await storage.save(data, filename, subdir="notes/images")
            return local_path

        except Exception as e:
            logger.warning(f"Failed to download image {url[:100]}: {e}")
            warnings.append(f"图片下载失败已保留原始链接: {url[:80]}")
            return None

    @staticmethod
    def _guess_extension(url: str, content_type: str) -> str:
        """Guess image file extension from URL or Content-Type."""
        # Try from URL path
        path = url.split("?")[0].split("#")[0]
        if "." in path:
            ext = path.rsplit(".", 1)[-1].lower()
            if ext in _ALLOWED_EXTENSIONS:
                return ext

        # Try from Content-Type
        ct_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp",
            "image/svg+xml": "svg",
            "image/bmp": "bmp",
        }
        for ct, ext in ct_map.items():
            if ct in content_type:
                return ext

        return "png"  # fallback
