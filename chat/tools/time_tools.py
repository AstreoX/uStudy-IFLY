"""Time Tools - Tool definitions and Executor for getting current time"""

from datetime import datetime, timezone, timedelta
from typing import Any

from chat.tools.base import ToolResult

# Tool definition (OpenAI Function Calling Format)
TIME_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前的日期和时间。当涉及任何与时间相关的操作时（如日程安排、复习计划、截止日期等），必须先调用此工具获取准确的当前时间。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

TIME_TOOL_NAMES: set[str] = {"get_current_time"}

# Metadata for tool card display
TIME_TOOL_METADATA: dict[str, dict[str, Any]] = {
    "get_current_time": {
        "requires_confirmation": False,
        "display_name": "查看当前时间",
    },
}

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


class TimeToolExecutor:
    """Executor for time tools - no DB needed"""

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name != "get_current_time":
            return ToolResult(success=False, data=None, message=f"未知的工具: {tool_name}")

        utc_now = datetime.now(timezone.utc)
        beijing_tz = timezone(timedelta(hours=8))
        beijing_now = utc_now.astimezone(beijing_tz)

        return ToolResult(
            success=True,
            data={
                "current_time": beijing_now.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": "Asia/Shanghai",
                "weekday": WEEKDAY_NAMES[beijing_now.weekday()],
                "iso": utc_now.isoformat(),
            },
            message=f"当前时间：{beijing_now.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)",
        )
