"""Artifact Tools - 创建/更新交互式 HTML 教学演示"""

import logging
from typing import Any
from uuid import UUID

from agents.artifact_agent import CDN_LIBRARIES
from agents.schemas import AgentTaskStatusEnum
from chat.tools.base import ToolResult
from db.database import get_scoped_session
from db.models import AgentTask, AgentTaskStatus, AgentTaskType, Conversation, Note
from graph.service import GraphService

logger = logging.getLogger(__name__)

ALLOWED_LIBRARIES = list(CDN_LIBRARIES.keys())

# ============ Tool Definitions ============

ARTIFACT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_artifact",
            "description": (
                "创建交互式 HTML 教学演示（物理模拟、数据可视化、动画、交互图表等）。"
                "演示将在笔记面板中以 iframe 方式渲染。异步生成，立即返回。\n"
                "【重要】每个对话仅允许一个 artifact。如果当前对话已有 artifact，"
                "请使用 update_artifact 修改，不要重复调用 create_artifact。"
                "再次调用 create_artifact 会覆盖已有的 artifact。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "演示标题",
                    },
                    "description": {
                        "type": "string",
                        "description": "详细描述要生成的交互演示内容、功能和交互方式",
                    },
                    "node_label": {
                        "type": "string",
                        "description": (
                            "挂载到的知识节点名称。传 'FREE' 表示不挂载到任何节点（默认）"
                        ),
                    },
                    "libraries": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ALLOWED_LIBRARIES,
                        },
                        "description": (
                            f"需要的 JS 库列表，可选: {', '.join(ALLOWED_LIBRARIES)}。"
                            "不需要外部库时传空数组。"
                        ),
                    },
                },
                "required": ["title", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_artifact",
            "description": (
                "更新当前对话中已有的交互式 HTML 演示。"
                "基于现有内容进行修改，异步生成。"
                "当用户要求修改、调整、改进已有 artifact 时使用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "修改说明（例如：改变颜色、增加交互、修复问题等）",
                    },
                    "libraries": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ALLOWED_LIBRARIES,
                        },
                        "description": "需要额外引入的 JS 库（可选）",
                    },
                },
                "required": ["description"],
            },
        },
    },
]

ARTIFACT_TOOL_NAMES: set[str] = {t["function"]["name"] for t in ARTIFACT_TOOLS}


# ============ Executor ============


class ArtifactToolExecutor:
    """Executor for artifact tools"""

    def __init__(self, user_id: UUID, space_id: UUID, conversation_id: UUID) -> None:
        self.user_id = user_id
        self.space_id = space_id
        self.conversation_id = conversation_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        dispatch = {
            "create_artifact": self._create_artifact,
            "update_artifact": self._update_artifact,
        }
        handler = dispatch.get(tool_name)
        if not handler:
            return ToolResult(success=False, data=None, message=f"未知工具: {tool_name}")

        try:
            return await handler(arguments)
        except Exception as e:
            logger.error("Artifact tool error: %s", e, exc_info=True)
            return ToolResult(success=False, data=None, message=f"操作失败: {e!s}")

    async def _create_artifact(self, args: dict[str, Any]) -> ToolResult:
        title = args.get("title", "交互演示")
        description = args.get("description", "")
        node_label = args.get("node_label", "FREE")
        libraries = args.get("libraries", [])

        # Validate libraries
        libraries = [lib for lib in libraries if lib in ALLOWED_LIBRARIES]

        async with get_scoped_session() as db:
            from sqlalchemy import select

            # Resolve node_label → node_id
            node_id = None
            if node_label and node_label.upper() != "FREE":
                graph_service = GraphService(db)
                node = await graph_service.get_node_by_label(self.space_id, node_label)
                if node:
                    node_id = node.id
                else:
                    return ToolResult(
                        success=False, data=None,
                        message=f"未找到名为「{node_label}」的知识节点，请检查节点名称是否正确",
                    )

            result = await db.execute(
                select(Conversation).where(Conversation.id == self.conversation_id)
            )
            conv = result.scalar_one_or_none()
            if not conv:
                return ToolResult(success=False, data=None, message="对话不存在")

            # Reuse existing artifact note if conversation already has one
            if conv.artifact_note_id:
                result = await db.execute(
                    select(Note).where(Note.id == conv.artifact_note_id)
                )
                existing_note = result.scalar_one_or_none()
                if existing_note:
                    existing_note.title = title
                    existing_note.content = ""
                    existing_note.node_id = node_id
                    existing_note.metadata_ = {
                        "generating": True,
                        "libraries": libraries,
                        "version": (existing_note.metadata_ or {}).get("version", 0) + 1,
                    }
                    await db.commit()
                    note_id = existing_note.id
                else:
                    note_id = await self._create_note_record(
                        db, conv, title, libraries, node_id
                    )
            else:
                note_id = await self._create_note_record(
                    db, conv, title, libraries, node_id
                )

            # Create agent task in the SAME session to ensure atomicity
            from agents.service import AgentService
            agent_service = AgentService(db)
            task_resp = await agent_service.create_artifact_task(
                user_id=self.user_id,
                space_id=self.space_id,
                conversation_id=self.conversation_id,
                note_id=note_id,
                description=description,
                libraries=libraries,
            )

        return ToolResult(
            success=True,
            data={
                "note_id": str(note_id),
                "task_id": str(task_resp.task_id),
                "status": "generating",
                "title": title,
            },
            message=f"正在生成交互演示「{title}」，完成后会通知你。",
        )

    @staticmethod
    async def _create_note_record(
        db, conv, title: str, libraries: list, node_id: UUID | None = None,
    ) -> UUID:
        """Create a new Note and link it to the conversation. Returns note_id."""
        note = Note(
            space_id=conv.space_id,
            node_id=node_id,
            title=title,
            content="",
            note_type="interactive_html",
            metadata_={"generating": True, "libraries": libraries, "version": 1},
        )
        db.add(note)
        await db.flush()
        conv.artifact_note_id = note.id
        await db.commit()
        await db.refresh(note)
        return note.id

    async def _update_artifact(self, args: dict[str, Any]) -> ToolResult:
        description = args.get("description", "")
        libraries = args.get("libraries")
        if libraries:
            libraries = [lib for lib in libraries if lib in ALLOWED_LIBRARIES]

        async with get_scoped_session() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(Conversation).where(Conversation.id == self.conversation_id)
            )
            conv = result.scalar_one_or_none()
            if not conv or not conv.artifact_note_id:
                return ToolResult(
                    success=False, data=None,
                    message="当前对话没有交互演示，请先使用 create_artifact 创建",
                )

            note_id = conv.artifact_note_id

            result = await db.execute(
                select(Note).where(Note.id == note_id)
            )
            note = result.scalar_one_or_none()
            if not note:
                return ToolResult(success=False, data=None, message="演示笔记不存在")

            # Block update while previous generation is in progress
            current_meta = note.metadata_ or {}
            if current_meta.get("generating"):
                return ToolResult(
                    success=False, data=None,
                    message="当前演示正在生成中，请等待生成完成后再更新",
                )

            existing_html = note.content or ""
            version = current_meta.get("version", 1) + 1

            # Update metadata (immutable pattern)
            new_meta = {**current_meta, "generating": True, "version": version}
            if libraries:
                existing_libs = current_meta.get("libraries", [])
                new_meta["libraries"] = list(set(existing_libs + libraries))
            note.metadata_ = new_meta

            # Create agent task in same session
            from agents.service import AgentService
            agent_service = AgentService(db)
            task_resp = await agent_service.create_artifact_task(
                user_id=self.user_id,
                space_id=self.space_id,
                conversation_id=self.conversation_id,
                note_id=note_id,
                description=description,
                libraries=libraries,
                existing_html=existing_html,
            )

        return ToolResult(
            success=True,
            data={
                "note_id": str(note_id),
                "task_id": str(task_resp.task_id),
                "status": "generating",
                "version": version,
            },
            message=f"正在更新交互演示（v{version}），完成后会通知你。",
        )
