"""Learning Space Tool Executor for Quick Chat Mode"""

import html
import logging
import random
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.schemas import KnowledgeGraphGenerateRequest
from agents.service import AgentService
from chat.tools.base import ToolResult
from db.database import get_scoped_session
from db.models import (
    AgentTask,
    AgentTaskStatus,
    Conversation,
    QuickChatToolTask,
    QuickChatToolTaskStage,
    QuickChatToolTaskStatus,
    Space,
    SpaceMember,
    SpaceMemberRole,
    User,
)
from spaces.colors import get_next_color
from quota.exceptions import SpaceCountQuotaExceeded
from quota.service import check_space_count_quota

logger = logging.getLogger(__name__)

# Valid preset preference IDs (matching frontend createSpace.vue)
VALID_PRESET_PREFERENCES = {
    "university",  # 大学课程
    "quick",  # 快速掌握
    "solid",  # 扎实学习
    "hobby",  # 业余自学
    "exam",  # 应对考试
    "work",  # 职场技能
    "research",  # 学术研究
    "practice",  # 实践项目
}

SPACE_COLOR_POOL = [
    "#0F6FFF",
    "#A18CD1",
    "#FA709A",
    "#84FAB0",
    "#F43B37",
]

TOOL_CREATE_LEARNING_SPACE = "create_learning_space"
TASK_TIMEOUT_SECONDS = 120


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _sanitize_text(text: str | None, max_length: int = 200) -> str | None:
    """
    Sanitize user input text.

    - Strips leading/trailing whitespace
    - Truncates to max_length
    - Escapes HTML entities to prevent XSS
    """
    if not text:
        return None
    sanitized = text.strip()
    if not sanitized:
        return None
    sanitized = sanitized[:max_length]
    sanitized = html.escape(sanitized)
    return sanitized


def _validate_learning_preferences(preferences: dict | None) -> dict | None:
    """
    Validate and sanitize learning preferences from AI tool call.

    Returns validated preferences dict with metadata, or None if invalid/empty.
    """
    if not preferences or not isinstance(preferences, dict):
        return None

    result: dict[str, Any] = {}

    preset = preferences.get("preset_preferences", [])
    if isinstance(preset, list):
        valid_presets = [
            p for p in preset if isinstance(p, str) and p in VALID_PRESET_PREFERENCES
        ][:8]
        if valid_presets:
            result["preset_preferences"] = valid_presets

    custom = preferences.get("custom_preference")
    if custom:
        sanitized = _sanitize_text(custom, max_length=500)
        if sanitized:
            result["custom_preference"] = sanitized

    if result:
        result["created_at"] = _now_utc().isoformat()
        result["source"] = "quick_chat"

    return result if result else None


def _format_user_preference(preferences: dict | None) -> str | None:
    """Map structured learning_preferences into Agent API user_preference text."""
    if not preferences:
        return None

    preset_map = {
        "university": "大学课程",
        "quick": "快速掌握",
        "solid": "扎实学习",
        "hobby": "业余自学",
        "exam": "应对考试",
        "work": "职场技能",
        "research": "学术研究",
        "practice": "实践项目",
    }

    parts: list[str] = []
    preset = preferences.get("preset_preferences") or []
    labels = [preset_map.get(p, p) for p in preset if isinstance(p, str)]
    if labels:
        parts.append("预设偏好：" + "、".join(labels))

    custom = preferences.get("custom_preference")
    if isinstance(custom, str) and custom.strip():
        parts.append("自定义偏好：" + custom.strip())

    if not parts:
        return None
    return "；".join(parts)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


class LearningSpaceToolExecutor:
    """
    Executor for learning space management tools in quick chat mode.

    Handles:
    - view_learning_spaces: List user's learning spaces
    - rebind_to_learning_space: Bind conversation to existing space
    - create_learning_space: Create new space + async KG task, bind later
    """

    def __init__(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> None:
        self.user_id = user_id
        self.conversation_id = conversation_id

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> ToolResult:
        """
        Execute a learning space tool. Each call uses an independent short-lived DB session.
        """
        try:
            async with get_scoped_session() as db:
                if tool_name == "view_learning_spaces":
                    return await self._view_learning_spaces(db)
                if tool_name == "rebind_to_learning_space":
                    return await self._rebind_to_learning_space(
                        db,
                        space_name=arguments.get("space_name", ""),
                    )
                if tool_name == TOOL_CREATE_LEARNING_SPACE:
                    return await self._create_learning_space(
                        db,
                        tool_call_id=tool_call_id,
                        name=arguments.get("name", ""),
                        learning_preferences=arguments.get("learning_preferences"),
                    )
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"未知的工具: {tool_name}",
                )
        except Exception as e:
            logger.error("Tool execution error [%s]: %s", tool_name, e, exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"工具执行失败: {str(e)}",
            )

    async def get_tool_task_status(self, tool_call_id: str) -> ToolResult:
        """Get and sync a specific async create-space tool task status."""
        async with get_scoped_session() as db:
            task = await self._get_create_task(db, tool_call_id)
            if not task:
                return ToolResult(
                    success=False,
                    data=None,
                    message="未找到对应的异步任务",
                )

            await self._sync_create_task_state(db, task)
            payload = await self._commit_refresh_and_serialize(db, task)
            return ToolResult(
                success=True,
                data=payload,
                message="任务状态获取成功",
            )

    async def list_tool_tasks(self) -> ToolResult:
        """List async create-space tasks for current quick chat conversation."""
        async with get_scoped_session() as db:
            result = await db.execute(
                select(QuickChatToolTask)
                .where(
                    QuickChatToolTask.user_id == self.user_id,
                    QuickChatToolTask.conversation_id == self.conversation_id,
                    QuickChatToolTask.tool_name == TOOL_CREATE_LEARNING_SPACE,
                )
                .order_by(QuickChatToolTask.created_at.desc())
                .limit(50)
            )
            tasks = result.scalars().all()

            for task in tasks:
                await self._sync_create_task_state(db, task)
            await db.commit()

            for task in tasks:
                await self._safe_refresh(db, task)
            data = [self._serialize_task(task) for task in tasks]
            return ToolResult(
                success=True,
                data={"tasks": data, "count": len(data)},
                message="任务列表获取成功",
            )

    async def bind_tool_task(self, tool_call_id: str) -> ToolResult:
        """Bind conversation to created space after KG generation is done."""
        async with get_scoped_session() as db:
            task = await self._get_create_task(db, tool_call_id)
            if not task:
                return ToolResult(
                    success=False,
                    data=None,
                    message="未找到对应的异步任务",
                )

            await self._sync_create_task_state(db, task)

            if _enum_value(task.status) == QuickChatToolTaskStatus.FAILED.value:
                payload = await self._commit_refresh_and_serialize(db, task)
                return ToolResult(
                    success=False,
                    data=payload,
                    message=task.error_message or "学习空间创建任务失败",
                )

            if _enum_value(task.stage) != QuickChatToolTaskStage.KG_DONE.value:
                payload = await self._commit_refresh_and_serialize(db, task)
                return ToolResult(
                    success=False,
                    data=payload,
                    message="知识图谱尚未生成完成，暂不能绑定",
                )

            if not task.space_id:
                await self._mark_task_failed(
                    db,
                    task,
                    stage=QuickChatToolTaskStage.BINDING_FAILED.value,
                    error_stage="binding",
                    error_code="SPACE_ID_MISSING",
                    error_message="学习空间不存在，无法绑定",
                    cleanup_space=False,
                )
                payload = await self._commit_refresh_and_serialize(db, task)
                return ToolResult(
                    success=False,
                    data=payload,
                    message=task.error_message or "学习空间不存在，无法绑定",
                )

            task.stage = QuickChatToolTaskStage.BINDING

            conv_result = await db.execute(
                select(Conversation).where(Conversation.id == self.conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()
            if not conversation or conversation.user_id != self.user_id:
                await self._mark_task_failed(
                    db,
                    task,
                    stage=QuickChatToolTaskStage.BINDING_FAILED.value,
                    error_stage="binding",
                    error_code="CONVERSATION_NOT_FOUND",
                    error_message="对话不存在或无权访问，无法绑定",
                    cleanup_space=True,
                )
                payload = await self._commit_refresh_and_serialize(db, task)
                return ToolResult(
                    success=False,
                    data=payload,
                    message=task.error_message or "对话不存在或无权访问，无法绑定",
                )

            space_result = await db.execute(
                select(Space).where(
                    Space.id == task.space_id,
                    Space.user_id == self.user_id,
                )
            )
            space = space_result.scalar_one_or_none()
            if not space:
                await self._mark_task_failed(
                    db,
                    task,
                    stage=QuickChatToolTaskStage.BINDING_FAILED.value,
                    error_stage="binding",
                    error_code="SPACE_NOT_FOUND",
                    error_message="学习空间不存在，无法绑定",
                    cleanup_space=False,
                )
                payload = await self._commit_refresh_and_serialize(db, task)
                return ToolResult(
                    success=False,
                    data=payload,
                    message=task.error_message or "学习空间不存在，无法绑定",
                )

            try:
                conversation.space_id = space.id
                task.stage = QuickChatToolTaskStage.BINDING_DONE
                task.status = QuickChatToolTaskStatus.DONE
                task.completed_at = _now_utc()
                task.error_stage = None
                task.error_code = None
                task.error_message = None
                result_payload = dict(task.result_payload or {})
                result_payload.update(
                    {
                        "action": "navigate_to_space_chat",
                        "space_id": str(space.id),
                        "space_name": space.name,
                        "conversation_id": str(self.conversation_id),
                    }
                )
                task.result_payload = result_payload
                serialized_task = await self._commit_refresh_and_serialize(db, task)
            except Exception as e:
                await self._mark_task_failed(
                    db,
                    task,
                    stage=QuickChatToolTaskStage.BINDING_FAILED.value,
                    error_stage="binding",
                    error_code="BINDING_FAILED",
                    error_message=f"绑定学习空间失败: {str(e)}",
                    cleanup_space=True,
                )
                payload = await self._commit_refresh_and_serialize(db, task)
                return ToolResult(
                    success=False,
                    data=payload,
                    message=task.error_message or "绑定学习空间失败",
                )

            return ToolResult(
                success=True,
                data={
                    **serialized_task,
                    "action": "navigate_to_space_chat",
                    "space_id": str(space.id),
                    "space_name": space.name,
                    "conversation_id": str(self.conversation_id),
                },
                message="学习空间已创建并绑定，正在跳转…",
            )

    async def _view_learning_spaces(self, db: AsyncSession) -> ToolResult:
        result = await db.execute(
            select(Space)
            .where(Space.user_id == self.user_id)
            .order_by(Space.updated_at.desc())
        )
        spaces = result.scalars().all()

        if not spaces:
            return ToolResult(
                success=True,
                data={"spaces": [], "count": 0},
                message="你还没有创建任何学习空间。",
            )

        space_list = [
            {
                "id": str(space.id),
                "name": space.name,
                "description": space.description,
                "color": space.color,
            }
            for space in spaces
        ]

        return ToolResult(
            success=True,
            data={"spaces": space_list, "count": len(space_list)},
            message=f"找到 {len(space_list)} 个学习空间。",
        )

    async def _rebind_to_learning_space(
        self,
        db: AsyncSession,
        space_name: str,
    ) -> ToolResult:
        if not space_name:
            return ToolResult(
                success=False,
                data=None,
                message="缺少学习空间名称",
            )

        space_result = await db.execute(
            select(Space).where(
                Space.user_id == self.user_id,
                Space.name == space_name,
            )
        )
        space = space_result.scalar_one_or_none()

        if not space:
            return ToolResult(
                success=False,
                data=None,
                message=f"未找到名为「{space_name}」的学习空间",
            )

        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == self.conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()

        if not conversation:
            return ToolResult(
                success=False,
                data=None,
                message="对话不存在",
            )

        if conversation.user_id != self.user_id:
            return ToolResult(
                success=False,
                data=None,
                message="无权访问该对话",
            )

        conversation.space_id = space.id
        await db.commit()

        logger.info(
            "Conversation %s bound to space %s by name '%s'",
            self.conversation_id,
            space.id,
            space_name,
        )

        return ToolResult(
            success=True,
            data={
                "action": "navigate_to_space_chat",
                "space_id": str(space.id),
                "space_name": space.name,
                "conversation_id": str(self.conversation_id),
            },
            message=f"已绑定到学习空间「{space.name}」",
        )

    async def _create_learning_space(
        self,
        db: AsyncSession,
        tool_call_id: str | None,
        name: str,
        learning_preferences: dict | None,
    ) -> ToolResult:
        if not tool_call_id:
            return ToolResult(
                success=False,
                data=None,
                message="缺少工具调用 ID",
            )

        running_task = await self._find_running_create_task(db)
        if running_task:
            return ToolResult(
                success=False,
                data={
                    "action": "existing_running_task",
                    "existing_task_id": str(running_task.id),
                    "existing_tool_call_id": running_task.tool_call_id,
                    "existing_stage": _enum_value(running_task.stage),
                    "existing_space_id": (
                        str(running_task.space_id) if running_task.space_id else None
                    ),
                    "existing_kg_task_id": (
                        str(running_task.kg_task_id) if running_task.kg_task_id else None
                    ),
                },
                message="当前对话已有一个学习空间创建任务正在进行中",
            )

        sanitized_name = _sanitize_text(name, max_length=200)
        if not sanitized_name:
            return ToolResult(
                success=False,
                data=None,
                message="学习空间名称不能为空",
            )

        validated_preferences = _validate_learning_preferences(learning_preferences)
        if not validated_preferences:
            return ToolResult(
                success=False,
                data=None,
                message="learning_preferences 必填，且至少包含一个有效偏好",
            )

        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == self.conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            return ToolResult(success=False, data=None, message="对话不存在")
        if conversation.user_id != self.user_id:
            return ToolResult(success=False, data=None, message="无权访问该对话")

        # Check space count quota
        user_result = await db.execute(
            select(User).where(User.id == self.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return ToolResult(success=False, data=None, message="用户不存在")
        try:
            await check_space_count_quota(db, user)
        except SpaceCountQuotaExceeded as e:
            return ToolResult(
                success=False,
                data=e.to_response_body(),
                message=e.message,
            )

        color = random.choice(SPACE_COLOR_POOL)
        space = Space(
            user_id=self.user_id,
            name=sanitized_name,
            description=None,
            color=color,
            learning_preferences=validated_preferences,
        )
        db.add(space)
        await db.flush()

        # Create SpaceMember (OWNER) so the space shows up in homepage queries
        owner_member = SpaceMember(
            space_id=space.id,
            user_id=self.user_id,
            role=SpaceMemberRole.OWNER,
            color=get_next_color(0),
        )
        db.add(owner_member)

        task = QuickChatToolTask(
            user_id=self.user_id,
            conversation_id=self.conversation_id,
            tool_call_id=tool_call_id,
            tool_name=TOOL_CREATE_LEARNING_SPACE,
            status=QuickChatToolTaskStatus.RUNNING,
            stage=QuickChatToolTaskStage.SPACE_CREATED,
            space_id=space.id,
            request_payload={
                "name": sanitized_name,
                "learning_preferences": validated_preferences,
                "assigned_color": color,
            },
            result_payload={},
        )
        db.add(task)
        await db.flush()

        try:
            agent_service = AgentService(db)
            kg_request = KnowledgeGraphGenerateRequest(
                topic=sanitized_name,
                user_preference=_format_user_preference(validated_preferences),
            )
            kg_task = await agent_service.create_knowledge_graph_task(
                user_id=self.user_id,
                space_id=space.id,
                request=kg_request,
                conversation_id=self.conversation_id,
            )
            task.kg_task_id = kg_task.task_id
            task.stage = QuickChatToolTaskStage.KG_RUNNING
            task.result_payload = {
                "kg_task_status": _enum_value(kg_task.status),
            }
            await db.commit()
        except Exception as e:
            await self._mark_task_failed(
                db,
                task,
                stage=QuickChatToolTaskStage.KG_FAILED.value,
                error_stage="kg_generation",
                error_code="KG_TASK_CREATE_FAILED",
                error_message=f"启动知识图谱任务失败: {str(e)}",
                cleanup_space=True,
            )
            payload = await self._commit_refresh_and_serialize(db, task)
            return ToolResult(
                success=False,
                data=payload,
                message=task.error_message or "启动知识图谱任务失败",
            )

        logger.info(
            "Created async quick-chat space task %s (space=%s, kg_task=%s)",
            task.id,
            space.id,
            task.kg_task_id,
        )

        return ToolResult(
            success=True,
            data={
                "action": "async_create_learning_space",
                "task_id": str(task.id),
                "tool_call_id": tool_call_id,
                "space_id": str(space.id),
                "space_name": space.name,
                "kg_task_id": str(task.kg_task_id) if task.kg_task_id else None,
                "stage": _enum_value(task.stage),
                "status": _enum_value(task.status),
            },
            message="学习空间创建请求已受理，正在后台生成知识图谱…",
        )

    async def _find_running_create_task(
        self,
        db: AsyncSession,
    ) -> QuickChatToolTask | None:
        result = await db.execute(
            select(QuickChatToolTask)
            .where(
                QuickChatToolTask.user_id == self.user_id,
                QuickChatToolTask.conversation_id == self.conversation_id,
                QuickChatToolTask.tool_name == TOOL_CREATE_LEARNING_SPACE,
                QuickChatToolTask.status == QuickChatToolTaskStatus.RUNNING,
            )
            .order_by(QuickChatToolTask.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_create_task(
        self,
        db: AsyncSession,
        tool_call_id: str,
    ) -> QuickChatToolTask | None:
        result = await db.execute(
            select(QuickChatToolTask).where(
                QuickChatToolTask.user_id == self.user_id,
                QuickChatToolTask.conversation_id == self.conversation_id,
                QuickChatToolTask.tool_name == TOOL_CREATE_LEARNING_SPACE,
                QuickChatToolTask.tool_call_id == tool_call_id,
            )
        )
        return result.scalar_one_or_none()

    async def _sync_create_task_state(
        self,
        db: AsyncSession,
        task: QuickChatToolTask,
    ) -> None:
        """Sync task state from AgentTask / timeout; no commit inside."""
        if _enum_value(task.status) != QuickChatToolTaskStatus.RUNNING.value:
            return

        if _enum_value(task.stage) == QuickChatToolTaskStage.KG_DONE.value:
            return

        now = _now_utc()
        created_at = task.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if (now - created_at).total_seconds() > TASK_TIMEOUT_SECONDS:
            await self._mark_task_failed(
                db,
                task,
                stage=QuickChatToolTaskStage.TIMEOUT.value,
                error_stage="kg_generation_timeout",
                error_code="KG_TASK_TIMEOUT",
                error_message="知识图谱生成超时（2分钟）",
                cleanup_space=True,
            )
            return

        if not task.kg_task_id:
            await self._mark_task_failed(
                db,
                task,
                stage=QuickChatToolTaskStage.KG_FAILED.value,
                error_stage="kg_generation",
                error_code="KG_TASK_ID_MISSING",
                error_message="知识图谱任务不存在，无法继续",
                cleanup_space=True,
            )
            return

        result = await db.execute(
            select(AgentTask).where(
                AgentTask.id == task.kg_task_id,
                AgentTask.user_id == self.user_id,
            )
        )
        kg_task = result.scalar_one_or_none()
        if not kg_task:
            await self._mark_task_failed(
                db,
                task,
                stage=QuickChatToolTaskStage.KG_FAILED.value,
                error_stage="kg_generation",
                error_code="KG_TASK_NOT_FOUND",
                error_message="知识图谱任务不存在，无法继续",
                cleanup_space=True,
            )
            return

        if kg_task.status == AgentTaskStatus.DONE:
            task.stage = QuickChatToolTaskStage.KG_DONE
            result_payload = dict(task.result_payload or {})
            output_data = kg_task.output_data or {}
            result_payload.update(
                {
                    "node_count": output_data.get("node_count"),
                    "edge_count": output_data.get("edge_count"),
                }
            )
            task.result_payload = result_payload
            return

        if kg_task.status == AgentTaskStatus.FAILED:
            await self._mark_task_failed(
                db,
                task,
                stage=QuickChatToolTaskStage.KG_FAILED.value,
                error_stage="kg_generation",
                error_code="KG_TASK_FAILED",
                error_message=kg_task.error_message or "知识图谱生成失败",
                cleanup_space=True,
            )
            return

        task.stage = QuickChatToolTaskStage.KG_RUNNING

    async def _cleanup_space(self, db: AsyncSession, space_id: UUID | None) -> tuple[bool, str | None]:
        if not space_id:
            return True, None

        result = await db.execute(
            select(Space).where(
                Space.id == space_id,
                Space.user_id == self.user_id,
            )
        )
        space = result.scalar_one_or_none()
        if not space:
            return True, None

        try:
            await db.delete(space)
            await db.flush()
            return True, None
        except Exception as e:
            logger.error("Failed to cleanup space %s: %s", space_id, e, exc_info=True)
            return False, str(e)

    async def _mark_task_failed(
        self,
        db: AsyncSession,
        task: QuickChatToolTask,
        *,
        stage: str,
        error_stage: str,
        error_code: str,
        error_message: str,
        cleanup_space: bool,
    ) -> None:
        task.status = QuickChatToolTaskStatus.FAILED
        task.stage = stage
        task.error_stage = error_stage
        task.error_code = error_code
        task.error_message = error_message
        task.completed_at = _now_utc()

        result_payload = dict(task.result_payload or {})
        if cleanup_space:
            cleanup_ok, cleanup_error = await self._cleanup_space(db, task.space_id)
            if cleanup_ok:
                result_payload["cleanup_stage"] = QuickChatToolTaskStage.CLEANUP_DONE.value
            else:
                result_payload["cleanup_stage"] = QuickChatToolTaskStage.CLEANUP_FAILED.value
                result_payload["cleanup_error"] = cleanup_error
                task.error_message = f"{error_message}\n清理失败：{cleanup_error}"

        task.result_payload = result_payload if result_payload else None

    async def _safe_refresh(
        self,
        db: AsyncSession,
        task: QuickChatToolTask,
    ) -> None:
        """Refresh task instance safely to avoid expired-attribute lazy loads."""
        try:
            await db.refresh(task)
        except Exception:
            # Best-effort refresh; serialization can still proceed with loaded fields.
            pass

    async def _commit_refresh_and_serialize(
        self,
        db: AsyncSession,
        task: QuickChatToolTask,
    ) -> dict[str, Any]:
        """Commit, refresh task instance, then serialize."""
        await db.commit()
        await self._safe_refresh(db, task)
        return self._serialize_task(task)

    def _serialize_task(self, task: QuickChatToolTask) -> dict[str, Any]:
        status = _enum_value(task.status)
        stage = _enum_value(task.stage)
        return {
            "task_id": str(task.id),
            "tool_call_id": task.tool_call_id,
            "tool_name": task.tool_name,
            "status": status,
            "stage": stage,
            "space_id": str(task.space_id) if task.space_id else None,
            "kg_task_id": str(task.kg_task_id) if task.kg_task_id else None,
            "source_message_id": (
                str(task.source_message_id) if task.source_message_id else None
            ),
            "request_payload": task.request_payload or {},
            "result_payload": task.result_payload or {},
            "error_stage": task.error_stage,
            "error_code": task.error_code,
            "error_message": task.error_message,
            "can_bind": (
                status == QuickChatToolTaskStatus.RUNNING.value
                and stage == QuickChatToolTaskStage.KG_DONE.value
            ),
            "created_at": _to_iso(task.created_at),
            "updated_at": _to_iso(task.updated_at),
            "completed_at": _to_iso(task.completed_at),
        }
