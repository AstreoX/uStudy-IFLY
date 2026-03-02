"""Schedule Tools - Tool definitions for calendar/schedule management.

These tools are executed client-side (e.g. Android system calendar) via the
client_tool_request protocol. Only the SCHEDULE_TOOLS schema list is needed
by the LLM; execution is handled by the frontend.
"""

from typing import Any


# ============ 4 Schedule Tools (OpenAI Function Calling Format) ============

SCHEDULE_TOOLS: list[dict[str, Any]] = [
    # 1. get_schedule
    {
        "type": "function",
        "function": {
            "name": "get_schedule",
            "description": "获取用户在指定日期范围内的日程安排",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "起始日期，格式 YYYY-MM-DD",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "结束日期，格式 YYYY-MM-DD",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    # 2. add_schedule
    {
        "type": "function",
        "function": {
            "name": "add_schedule",
            "description": "向用户的日程中添加一个新日程",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "日程标题",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "开始时间，格式 YYYY-MM-DD HH:MM",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "结束时间，格式 YYYY-MM-DD HH:MM",
                    },
                    "details": {
                        "type": "string",
                        "description": "日程详细信息",
                    },
                },
                "required": ["title", "start_time", "end_time", "details"],
            },
        },
    },
    # 3. delete_schedule
    {
        "type": "function",
        "function": {
            "name": "delete_schedule",
            "description": "从用户的日程中删除一个日程",
            "parameters": {
                "type": "object",
                "properties": {
                    "schedule_id": {
                        "type": "string",
                        "description": "要删除的日程 ID",
                    },
                },
                "required": ["schedule_id"],
            },
        },
    },
    # 4. update_schedule
    {
        "type": "function",
        "function": {
            "name": "update_schedule",
            "description": "更新用户日程中的某个日程信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "schedule_id": {
                        "type": "string",
                        "description": "要更新的日程 ID",
                    },
                    "title": {
                        "type": "string",
                        "description": "新的日程标题",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "新的开始时间，格式 YYYY-MM-DD HH:MM",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "新的结束时间，格式 YYYY-MM-DD HH:MM",
                    },
                    "details": {
                        "type": "string",
                        "description": "新的日程详细信息",
                    },
                },
                "required": ["schedule_id"],
            },
        },
    },
]
