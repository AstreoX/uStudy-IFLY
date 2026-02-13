"""Learning Space Tool Executor for Quick Chat Mode"""

import html
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.tools.base import ToolResult
from db.database import get_scoped_session
from db.models import Conversation, Space

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


def _sanitize_text(text: str | None, max_length: int = 200) -> str | None:
    """
    Sanitize user input text.

    - Strips leading/trailing whitespace
    - Truncates to max_length
    - Escapes HTML entities to prevent XSS

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text or None if input was None/empty
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

    Args:
        preferences: Raw preferences dict from tool arguments

    Returns:
        Validated preferences dict with metadata, or None if invalid/empty
    """
    if not preferences or not isinstance(preferences, dict):
        return None

    result: dict[str, Any] = {}

    # Validate preset_preferences
    preset = preferences.get("preset_preferences", [])
    if isinstance(preset, list):
        valid_presets = [
            p
            for p in preset
            if isinstance(p, str) and p in VALID_PRESET_PREFERENCES
        ][:8]  # Max 8 presets
        if valid_presets:
            result["preset_preferences"] = valid_presets

    # Validate custom_preference
    custom = preferences.get("custom_preference")
    if custom:
        sanitized = _sanitize_text(custom, max_length=500)
        if sanitized:
            result["custom_preference"] = sanitized

    # Add metadata if we have any valid preferences
    if result:
        result["created_at"] = datetime.now(timezone.utc).isoformat()
        result["source"] = "quick_chat"

    return result if result else None


class LearningSpaceToolExecutor:
    """
    Executor for learning space management tools in quick chat mode.

    Handles:
    - view_learning_spaces: List user's learning spaces
    - rebind_to_learning_space: Bind conversation to existing space
    - create_learning_space: Create new space and bind conversation
    """

    def __init__(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> None:
        """
        Initialize the executor.

        Args:
            user_id: Current user ID
            conversation_id: Current conversation ID
        """
        self.user_id = user_id
        self.conversation_id = conversation_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute a learning space tool. Each call creates an independent short-lived DB session.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            ToolResult with execution result
        """
        try:
            async with get_scoped_session() as db:
                if tool_name == "view_learning_spaces":
                    return await self._view_learning_spaces(db)
                elif tool_name == "rebind_to_learning_space":
                    return await self._rebind_to_learning_space(
                        db,
                        space_name=arguments.get("space_name", ""),
                    )
                elif tool_name == "create_learning_space":
                    return await self._create_learning_space(
                        db,
                        name=arguments.get("name", ""),
                        description=arguments.get("description"),
                        color=arguments.get("color", "#3B82F6"),
                        learning_preferences=arguments.get("learning_preferences"),
                    )
                else:
                    return ToolResult(
                        success=False,
                        data=None,
                        message=f"未知的工具: {tool_name}",
                    )
        except Exception as e:
            logger.error(f"Tool execution error [{tool_name}]: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"工具执行失败: {str(e)}",
            )

    async def _view_learning_spaces(self, db: AsyncSession) -> ToolResult:
        """
        List all learning spaces for the current user.

        Returns:
            ToolResult with list of spaces
        """
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
        """
        Bind the current conversation to an existing learning space by name.

        Args:
            db: Database session
            space_name: Name of the target space

        Returns:
            ToolResult with binding result
        """
        if not space_name:
            return ToolResult(
                success=False,
                data=None,
                message="缺少学习空间名称",
            )

        # Find space by name and user_id
        space_result = await db.execute(
            select(Space).where(
                Space.user_id == self.user_id,
                Space.name == space_name
            )
        )
        space = space_result.scalar_one_or_none()

        if not space:
            return ToolResult(
                success=False,
                data=None,
                message=f"未找到名为「{space_name}」的学习空间",
            )

        # Get conversation and verify ownership
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

        # Update conversation's space binding
        conversation.space_id = space.id
        await db.commit()

        logger.info(
            f"Conversation {self.conversation_id} bound to space {space.id} by name '{space_name}'"
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
        name: str,
        description: str | None = None,
        color: str = "#3B82F6",
        learning_preferences: dict | None = None,
    ) -> ToolResult:
        """
        Create a new learning space and bind the current conversation.

        Args:
            db: Database session
            name: Space name
            description: Optional description
            color: Hex color code
            learning_preferences: Optional learning preferences from AI inference

        Returns:
            ToolResult with created space info
        """
        # Sanitize inputs
        sanitized_name = _sanitize_text(name, max_length=200)
        if not sanitized_name:
            return ToolResult(
                success=False,
                data=None,
                message="学习空间名称不能为空",
            )

        sanitized_description = _sanitize_text(description, max_length=500)

        # Validate color format
        if not re.match(r"^#[0-9A-Fa-f]{6}$", color):
            color = "#3B82F6"  # Default blue

        # Validate learning preferences
        validated_preferences = _validate_learning_preferences(learning_preferences)

        # Create space
        space = Space(
            user_id=self.user_id,
            name=sanitized_name,
            description=sanitized_description,
            color=color,
            learning_preferences=validated_preferences,
        )
        db.add(space)
        await db.flush()  # Get the space ID

        # Get conversation and bind to new space
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
        await db.refresh(space)

        logger.info(
            f"Created space {space.id} and bound conversation {self.conversation_id}"
        )

        return ToolResult(
            success=True,
            data={
                "action": "navigate_to_space_chat",
                "space_id": str(space.id),
                "space_name": space.name,
                "conversation_id": str(self.conversation_id),
            },
            message=f"已创建学习空间「{space.name}」",
        )
