"""Learning Space Tools for Quick Chat Mode"""

from typing import Any

# Tool definitions in OpenAI function calling format
LEARNING_SPACE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "view_learning_spaces",
            "description": "查看用户已有的所有学习空间列表。当用户询问自己有哪些学习空间、想要选择学习空间时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rebind_to_learning_space",
            "description": """将当前对话绑定到指定学习空间，绑定后切换到学习空间对话模式。

使用时机：
1. 用户明确要求进入某个学习空间（如"进入Python空间"、"打开数学空间"）
2. 用户说"帮我进入XX那个空间"
3. 对话主题与用户已有的学习空间高度相关，且用户同意进入

重要：调用前建议先调用 view_learning_spaces 确认用户有该名称的学习空间。此工具需要用户确认后才会执行。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "space_name": {
                        "type": "string",
                        "description": "要绑定的学习空间名称（必须与用户已有的学习空间名称完全匹配）",
                    },
                },
                "required": ["space_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_learning_space",
            "description": "创建新学习空间并在后台异步生成知识图谱。完成后再绑定当前对话。当用户想创建新的学习主题时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "学习空间名称",
                    },
                    "learning_preferences": {
                        "type": "object",
                        "description": "学习偏好设置（必填）。根据用户表达的学习目标和风格推断。",
                        "properties": {
                            "preset_preferences": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": [
                                        "university",
                                        "quick",
                                        "solid",
                                        "hobby",
                                        "exam",
                                        "work",
                                        "research",
                                        "practice",
                                    ],
                                },
                                "description": "预设偏好: university(大学课程), quick(快速掌握), solid(扎实学习), hobby(业余自学), exam(应对考试), work(职场技能), research(学术研究), practice(实践项目)",
                            },
                            "custom_preference": {
                                "type": "string",
                                "description": "自定义偏好描述",
                            },
                        },
                    },
                },
                "required": ["name", "learning_preferences"],
            },
        },
    },
]

# Tool metadata for confirmation logic
TOOL_METADATA: dict[str, dict[str, Any]] = {
    "view_learning_spaces": {
        "requires_confirmation": False,
        "display_name": "查看学习空间",
    },
    "rebind_to_learning_space": {
        "requires_confirmation": True,
        "display_name": "绑定到学习空间",
    },
    "create_learning_space": {
        "requires_confirmation": True,
        "display_name": "创建学习空间",
    },
    "get_current_time": {
        "requires_confirmation": False,
        "display_name": "查看当前时间",
    },
}


def get_tool_metadata(tool_name: str) -> dict[str, Any]:
    """Get metadata for a tool by name."""
    return TOOL_METADATA.get(tool_name, {"requires_confirmation": False, "display_name": tool_name})


def get_allowed_tool_names() -> set[str]:
    """Get set of allowed tool names for validation."""
    return set(TOOL_METADATA.keys())
