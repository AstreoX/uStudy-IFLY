"""Agent todo tools and executor."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from chat.agent_todo_service import (
    AgentTodoItemNotFoundError,
    AgentTodoService,
)
from chat.tools.base import ToolResult
from db.database import get_scoped_session

logger = logging.getLogger(__name__)


AGENT_TODO_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_todo",
            "description": (
                "为当前对话创建 agent 内部 todo 列表项。"
                "只有当任务需要分成多个明确步骤时才调用。"
                "支持一次批量创建多个步骤。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "要创建的 todo 项列表，按执行顺序传入",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "todo 标题，简洁描述这一步要做什么",
                                },
                                "details": {
                                    "type": "string",
                                    "description": "可选备注，补充上下文或约束",
                                },
                            },
                            "required": ["title"],
                        },
                    },
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_todo",
            "description": (
                "更新当前对话中某个已有 todo 的标题或备注。"
                "必须使用 prompt 中已有的 task_id，如 todo_001。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "要更新的 todo 任务 ID，例如 todo_001",
                    },
                    "title": {
                        "type": "string",
                        "description": "新的 todo 标题（可选）",
                    },
                    "details": {
                        "type": "string",
                        "description": "新的 todo 备注（可选，传空字符串可清空）",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_todo",
            "description": (
                "将当前对话中的某个 todo 标记为已完成。"
                "完成后不要改变其他 todo 的顺序。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "要完成的 todo 任务 ID，例如 todo_001",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_todo",
            "description": (
                "删除当前对话中不再需要的某个 todo。"
                "仅在该步骤已无意义时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "要删除的 todo 任务 ID，例如 todo_001",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
]

AGENT_TODO_TOOL_NAMES: set[str] = {
    tool_def["function"]["name"] for tool_def in AGENT_TODO_TOOLS
}

AGENT_TODO_TOOL_METADATA: dict[str, dict[str, Any]] = {
    "create_todo": {
        "requires_confirmation": False,
        "display_name": "创建 Agent Todo",
    },
    "update_todo": {
        "requires_confirmation": False,
        "display_name": "更新 Agent Todo",
    },
    "complete_todo": {
        "requires_confirmation": False,
        "display_name": "完成 Agent Todo",
    },
    "delete_todo": {
        "requires_confirmation": False,
        "display_name": "删除 Agent Todo",
    },
}


class AgentTodoToolExecutor:
    """Executor for agent todo tools."""

    def __init__(self, user_id: UUID, conversation_id: UUID) -> None:
        self.user_id = user_id
        self.conversation_id = conversation_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        try:
            async with get_scoped_session() as db:
                service = AgentTodoService(db)

                if tool_name == "create_todo":
                    payload = await service.create_todos(
                        self.user_id,
                        self.conversation_id,
                        arguments.get("items") or [],
                    )
                    await db.commit()
                    created = payload.get("created_task_ids") or []
                    return ToolResult(
                        success=True,
                        data=payload,
                        message=f"已创建 {len(created)} 个 agent todo",
                    )

                if tool_name == "update_todo":
                    task_id = str(arguments.get("task_id") or "").strip()
                    payload = await service.update_todo(
                        self.user_id,
                        self.conversation_id,
                        task_id,
                        arguments.get("title"),
                        arguments.get("details"),
                        title_provided="title" in arguments,
                        details_provided="details" in arguments,
                    )
                    await db.commit()
                    return ToolResult(
                        success=True,
                        data=payload,
                        message=f"已更新任务 {task_id}",
                    )

                if tool_name == "complete_todo":
                    task_id = str(arguments.get("task_id") or "").strip()
                    payload = await service.complete_todo(
                        self.user_id,
                        self.conversation_id,
                        task_id,
                    )
                    await db.commit()
                    return ToolResult(
                        success=True,
                        data=payload,
                        message=f"已完成任务 {task_id}",
                    )

                if tool_name == "delete_todo":
                    task_id = str(arguments.get("task_id") or "").strip()
                    payload = await service.delete_todo(
                        self.user_id,
                        self.conversation_id,
                        task_id,
                    )
                    await db.commit()
                    return ToolResult(
                        success=True,
                        data=payload,
                        message=f"已删除任务 {task_id}",
                    )

                return ToolResult(
                    success=False,
                    data=None,
                    message=f"未知的工具: {tool_name}",
                )
        except (ValueError, AgentTodoItemNotFoundError) as exc:
            return ToolResult(success=False, data=None, message=str(exc))
        except Exception as exc:
            logger.error("Agent todo tool execution failed: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"agent todo 操作失败: {exc!s}",
            )
