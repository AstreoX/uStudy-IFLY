"""Review Tools - Tool definitions and Executor for marking reviews completed"""

import logging
from typing import Any
from uuid import UUID

from chat.tools.base import ToolResult
from review.service import complete_review, complete_reviews_by_node_label

logger = logging.getLogger(__name__)

# Tool definition (OpenAI Function Calling Format)
REVIEW_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "mark_review_completed",
            "description": (
                "标记用户的某个知识点复习为已完成。"
                "仅在以下情况调用：用户在对话中已充分展示了对该知识点的理解（如正确回答问题、主动讲解概念等），"
                "你确认其已完成有效复习后，才调用此工具。"
                "禁止：未经讨论就直接调用；用户仅提到知识点名称就调用；用户明确表示不想复习时调用。"
                "推荐使用 node_label 参数（知识点名称），会批量标记该知识点所有到期复习。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "node_label": {
                        "type": "string",
                        "description": "知识点名称，批量标记该知识点所有到期待复习项为已完成",
                    },
                    "review_id": {
                        "type": "string",
                        "description": "复习计划 ID（UUID），精确标记单条复习。仅在需要精确控制时使用",
                    },
                },
            },
        },
    },
]

REVIEW_TOOL_NAMES: set[str] = {"mark_review_completed"}

# Metadata for tool card display
REVIEW_TOOL_METADATA: dict[str, dict[str, Any]] = {
    "mark_review_completed": {
        "requires_confirmation": False,
        "display_name": "标记复习完成",
    },
}


class ReviewToolExecutor:
    """Executor for review tools - uses short-lived DB sessions per call"""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name != "mark_review_completed":
            return ToolResult(
                success=False, data=None, message=f"未知的工具: {tool_name}"
            )

        node_label = arguments.get("node_label")
        review_id = arguments.get("review_id")

        if not node_label and not review_id:
            return ToolResult(
                success=False,
                data=None,
                message="请提供 node_label（知识点名称）或 review_id（复习计划ID）",
            )

        try:
            if node_label:
                count = await complete_reviews_by_node_label(
                    self.user_id, node_label
                )
                if count == 0:
                    return ToolResult(
                        success=True,
                        data={"node_label": node_label, "completed_count": 0},
                        message=f"未找到知识点「{node_label}」的到期待复习项",
                    )
                return ToolResult(
                    success=True,
                    data={"node_label": node_label, "completed_count": count},
                    message=f"已标记知识点「{node_label}」的 {count} 条到期复习为完成",
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
                message=f"无效的 review_id 格式: {review_id}",
            )
        except Exception as e:
            logger.error(f"Review tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False, data=None, message=f"标记复习完成失败: {str(e)}"
            )
