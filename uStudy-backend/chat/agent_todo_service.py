"""Conversation-scoped agent todo service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_scoped_session
from db.models import AgentTodoStatus, Conversation, ConversationAgentTodo

_MAX_TITLE_LEN = 200
_MAX_DETAILS_LEN = 2000


class ConversationTodoNotFoundError(Exception):
    """Raised when a conversation does not exist."""


class ConversationTodoAccessDeniedError(Exception):
    """Raised when a user cannot access the conversation todo list."""


class AgentTodoItemNotFoundError(Exception):
    """Raised when a todo item cannot be found in a conversation."""


def _serialize_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _normalize_title(value: Any) -> str:
    title = str(value or "").strip()
    if not title:
        raise ValueError("todo 标题不能为空")
    if len(title) > _MAX_TITLE_LEN:
        title = title[:_MAX_TITLE_LEN].strip()
    if not title:
        raise ValueError("todo 标题不能为空")
    return title


def _normalize_details(value: Any) -> str | None:
    if value is None:
        return None
    details = str(value).strip()
    if not details:
        return None
    if len(details) > _MAX_DETAILS_LEN:
        details = details[:_MAX_DETAILS_LEN].strip()
    return details or None


class AgentTodoService:
    """CRUD service for conversation-scoped agent todos."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_todos(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> dict[str, Any]:
        await self._get_conversation_with_check(user_id, conversation_id)
        todos = await self._list_todos(conversation_id)
        return {
            "conversation_id": str(conversation_id),
            "todos": self.serialize_todos(todos),
        }

    async def create_todos(
        self,
        user_id: UUID,
        conversation_id: UUID,
        items: Iterable[dict[str, Any]],
    ) -> dict[str, Any]:
        await self._get_conversation_with_check(user_id, conversation_id)

        normalized_items = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("items 中的每一项都必须是对象")
            normalized_items.append({
                "title": _normalize_title(item.get("title")),
                "details": _normalize_details(item.get("details")),
            })

        if not normalized_items:
            raise ValueError("items 不能为空")

        max_sort_order = await self.db.scalar(
            select(func.max(ConversationAgentTodo.sort_order)).where(
                ConversationAgentTodo.conversation_id == conversation_id
            )
        )
        next_sort_order = (max_sort_order or 0) + 1

        created_task_ids: list[str] = []
        for item in normalized_items:
            task_id = f"todo_{next_sort_order:03d}"
            todo = ConversationAgentTodo(
                conversation_id=conversation_id,
                task_id=task_id,
                title=item["title"],
                details=item["details"],
                status=AgentTodoStatus.PENDING.value,
                sort_order=next_sort_order,
            )
            self.db.add(todo)
            created_task_ids.append(task_id)
            next_sort_order += 1

        await self.db.flush()
        todos = await self._list_todos(conversation_id)
        return {
            "conversation_id": str(conversation_id),
            "created_task_ids": created_task_ids,
            "todos": self.serialize_todos(todos),
        }

    async def update_todo(
        self,
        user_id: UUID,
        conversation_id: UUID,
        task_id: str,
        title: Any = None,
        details: Any = None,
        *,
        title_provided: bool = False,
        details_provided: bool = False,
    ) -> dict[str, Any]:
        await self._get_conversation_with_check(user_id, conversation_id)
        if not title_provided and not details_provided:
            raise ValueError("update_todo 至少需要更新 title 或 details")

        todo = await self._get_todo(conversation_id, task_id)
        if title_provided:
            todo.title = _normalize_title(title)
        if details_provided:
            todo.details = _normalize_details(details)

        await self.db.flush()
        todos = await self._list_todos(conversation_id)
        return {
            "conversation_id": str(conversation_id),
            "updated_task_id": todo.task_id,
            "todos": self.serialize_todos(todos),
        }

    async def complete_todo(
        self,
        user_id: UUID,
        conversation_id: UUID,
        task_id: str,
    ) -> dict[str, Any]:
        await self._get_conversation_with_check(user_id, conversation_id)
        todo = await self._get_todo(conversation_id, task_id)
        todo.status = AgentTodoStatus.COMPLETED.value
        if todo.completed_at is None:
            todo.completed_at = datetime.now(timezone.utc)

        await self.db.flush()
        todos = await self._list_todos(conversation_id)
        return {
            "conversation_id": str(conversation_id),
            "completed_task_id": todo.task_id,
            "todos": self.serialize_todos(todos),
        }

    async def set_todo_completion(
        self,
        user_id: UUID,
        conversation_id: UUID,
        task_id: str,
        completed: bool,
    ) -> dict[str, Any]:
        await self._get_conversation_with_check(user_id, conversation_id)
        todo = await self._get_todo(conversation_id, task_id)

        if completed:
            todo.status = AgentTodoStatus.COMPLETED.value
            if todo.completed_at is None:
                todo.completed_at = datetime.now(timezone.utc)
        else:
            todo.status = AgentTodoStatus.PENDING.value
            todo.completed_at = None

        await self.db.flush()
        todos = await self._list_todos(conversation_id)
        return {
            "conversation_id": str(conversation_id),
            "todos": self.serialize_todos(todos),
        }

    async def delete_todo(
        self,
        user_id: UUID,
        conversation_id: UUID,
        task_id: str,
    ) -> dict[str, Any]:
        await self._get_conversation_with_check(user_id, conversation_id)
        todo = await self._get_todo(conversation_id, task_id)
        deleted_task_id = todo.task_id
        await self.db.delete(todo)
        await self.db.flush()

        todos = await self._list_todos(conversation_id)
        return {
            "conversation_id": str(conversation_id),
            "deleted_task_id": deleted_task_id,
            "todos": self.serialize_todos(todos),
        }

    async def _get_conversation_with_check(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> Conversation:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise ConversationTodoNotFoundError(f"对话 {conversation_id} 不存在")
        if conversation.user_id != user_id:
            raise ConversationTodoAccessDeniedError(
                f"无权访问对话 {conversation_id}"
            )
        return conversation

    async def _get_todo(
        self,
        conversation_id: UUID,
        task_id: str,
    ) -> ConversationAgentTodo:
        result = await self.db.execute(
            select(ConversationAgentTodo).where(
                ConversationAgentTodo.conversation_id == conversation_id,
                ConversationAgentTodo.task_id == task_id,
            )
        )
        todo = result.scalar_one_or_none()
        if not todo:
            raise AgentTodoItemNotFoundError(f"未找到任务 {task_id}")
        return todo

    async def _list_todos(
        self,
        conversation_id: UUID,
    ) -> list[ConversationAgentTodo]:
        result = await self.db.execute(
            select(ConversationAgentTodo)
            .where(ConversationAgentTodo.conversation_id == conversation_id)
            .order_by(ConversationAgentTodo.sort_order.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    def serialize_todos(
        todos: Iterable[ConversationAgentTodo],
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": str(todo.id),
                "conversation_id": str(todo.conversation_id),
                "task_id": todo.task_id,
                "title": todo.title,
                "details": todo.details,
                "status": todo.status,
                "sort_order": todo.sort_order,
                "completed_at": _serialize_dt(todo.completed_at),
                "created_at": _serialize_dt(todo.created_at),
                "updated_at": _serialize_dt(todo.updated_at),
            }
            for todo in todos
        ]


async def get_conversation_todos(
    user_id: UUID,
    conversation_id: UUID,
) -> dict[str, Any]:
    """Fetch the normalized todo list for a conversation."""
    async with get_scoped_session() as db:
        service = AgentTodoService(db)
        return await service.get_todos(user_id, conversation_id)


async def get_agent_todo_prompt_state(
    user_id: UUID,
    conversation_id: UUID,
) -> str:
    """Load and format the todo list for prompt injection."""
    payload = await get_conversation_todos(user_id, conversation_id)
    return format_agent_todos_for_prompt(payload.get("todos") or [])


def format_agent_todos_for_prompt(todos: list[dict[str, Any]]) -> str:
    """Render normalized todos into a compact prompt section body."""
    if not todos:
        return "无待办"

    lines: list[str] = []
    for todo in todos:
        status = str(todo.get("status") or AgentTodoStatus.PENDING.value).lower()
        task_id = str(todo.get("task_id") or "")
        title = str(todo.get("title") or "").strip()
        details = str(todo.get("details") or "").strip()
        line = f"- {task_id} | {status} | {title}"
        if details:
            truncated = details[:120]
            if len(details) > 120:
                truncated += "..."
            line += f" | details: {truncated}"
        lines.append(line)
    return "\n".join(lines)
