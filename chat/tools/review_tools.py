"""Review Tools - Tool definitions and Executor for marking reviews completed"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from chat.tools.base import ToolResult
from review.service import (
    complete_review,
    complete_reviews_by_activity,
    get_due_reviews_by_space,
)

logger = logging.getLogger(__name__)

# Tool definition (OpenAI Function Calling Format)
REVIEW_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "mark_review_completed",
            "description": (
                "标记用户的某个学习事件的复习为已完成。"
                "仅在用户已充分展示对该学习事件所涉知识点的理解后调用。"
                "使用 activity_id 参数（从 get_review_events 结果中获取）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_id": {
                        "type": "string",
                        "description": "学习事件 ID（UUID），批量标记该事件所有到期待复习项为已完成",
                    },
                    "review_id": {
                        "type": "string",
                        "description": "复习计划 ID（UUID），精确标记单条复习。仅在需要精确控制时使用",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_review_events",
            "description": (
                "查看当前学习空间中到期或逾期的待复习学习事件列表。"
                "当用户表达复习意愿、询问有哪些需要复习的内容时调用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]

REVIEW_TOOL_NAMES: set[str] = {"mark_review_completed", "get_review_events"}

# Metadata for tool card display
REVIEW_TOOL_METADATA: dict[str, dict[str, Any]] = {
    "mark_review_completed": {
        "requires_confirmation": False,
        "display_name": "标记复习完成",
    },
    "get_review_events": {
        "requires_confirmation": False,
        "display_name": "查看复习事件",
    },
}


class ReviewToolExecutor:
    """Executor for review tools - uses short-lived DB sessions per call"""

    def __init__(self, user_id: UUID, space_id: UUID) -> None:
        self.user_id = user_id
        self.space_id = space_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name == "get_review_events":
            return await self._get_review_events()

        if tool_name != "mark_review_completed":
            return ToolResult(
                success=False, data=None, message=f"未知的工具: {tool_name}"
            )

        activity_id = arguments.get("activity_id")
        review_id = arguments.get("review_id")

        if not activity_id and not review_id:
            return ToolResult(
                success=False,
                data=None,
                message="请提供 activity_id（学习事件ID）或 review_id（复习计划ID）",
            )

        try:
            if activity_id:
                activity_uuid = UUID(activity_id)
                count = await complete_reviews_by_activity(
                    self.user_id, activity_uuid
                )
                if count == 0:
                    return ToolResult(
                        success=True,
                        data={"activity_id": activity_id, "completed_count": 0},
                        message=f"未找到该学习事件的到期待复习项",
                    )
                return ToolResult(
                    success=True,
                    data={"activity_id": activity_id, "completed_count": count},
                    message=f"已标记该学习事件的 {count} 条到期复习为完成",
                )
            else:
                review_uuid = UUID(review_id)
                ok = await complete_review(self.user_id, review_uuid)
                if not ok:
                    return ToolResult(
                        success=False,
                        data=None,
                        message=f"复习计划 {review_id} 不存在或已完成",
                    )
                return ToolResult(
                    success=True,
                    data={"review_id": review_id},
                    message=f"已标记复习计划 {review_id} 为完成",
                )
        except ValueError:
            return ToolResult(
                success=False,
                data=None,
                message=f"无效的 ID 格式: {activity_id or review_id}",
            )
        except Exception as e:
            logger.error(f"Review tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False, data=None, message=f"标记复习完成失败: {str(e)}"
            )

    async def _get_review_events(self) -> ToolResult:
        try:
            rows = await get_due_reviews_by_space(
                self.user_id, self.space_id, limit=10
            )
            if not rows:
                return ToolResult(
                    success=True,
                    data={"message": "当前没有到期的复习项", "items": [], "total": 0},
                    message="当前没有到期的复习项",
                )
            today = datetime.now(timezone.utc).date()
            items = []
            for r, activity in rows:
                overdue_days = (today - r.scheduled_date).days
                items.append({
                    "activity_id": str(r.activity_id),
                    "activity_title": activity.title,
                    "related_node_labels": activity.related_node_labels or [],
                    "study_depth": r.study_depth,
                    "review_number": r.review_number,
                    "scheduled_date": str(r.scheduled_date),
                    "overdue_days": overdue_days,
                    "urgency": f"逾期{overdue_days}天" if overdue_days > 0 else "今日到期",
                })
            return ToolResult(
                success=True,
                data={
                    "message": f"找到 {len(items)} 条待复习学习事件",
                    "items": items,
                    "total": len(items),
                },
                message=f"找到 {len(items)} 条待复习学习事件",
            )
        except Exception as e:
            logger.error(f"get_review_events failed: {e}", exc_info=True)
            return ToolResult(
                success=False, data=None, message=f"获取复习事件失败: {str(e)}"
            )
