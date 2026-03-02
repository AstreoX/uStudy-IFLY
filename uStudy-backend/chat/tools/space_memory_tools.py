"""Space Memory Tools - 学习空间级别的记忆工具"""

from typing import Any

SPACE_MEMORY_TOOLS: list[dict[str, Any]] = [
    # 工具 1: 写入空间记忆
    {
        "type": "function",
        "function": {
            "name": "write_to_space_memory",
            "description": """将与当前学习空间相关的信息写入空间记忆。空间记忆仅在此空间的对话中生效。

使用时机：
1. 用户分享与此学习主题相关的背景信息
2. 用户说明在此空间的学习目标或进度
3. 用户提到特定于此主题的偏好（如"这门课我喜欢看例题"）
4. 发现与此空间学习内容相关的重要上下文

不应使用：
- 通用的用户偏好（应使用长期记忆）
- 临时性的对话内容
- 敏感隐私信息

写入内容应简洁，聚焦于与当前学习空间主题相关的信息。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_content": {
                        "type": "string",
                        "description": "要记住的内容",
                        "maxLength": 500,
                    },
                },
                "required": ["memory_content"],
            },
        },
    },
    # 工具 2: 删除空间记忆
    {
        "type": "function",
        "function": {
            "name": "delete_from_space_memory",
            "description": """删除当前学习空间记忆中的特定条目。

使用时机：
1. 用户明确要求忘记/删除某条空间记忆
2. 用户说之前记录的信息已过时或不正确
3. 用户要求清除此空间的所有记忆

操作方式：
- 提供 entry_id 删除指定序号的条目
- 设置 clear_all=true 清空此空间的所有记忆（谨慎使用）

注意：空间记忆内容已在系统提示词中显示，可直接查看序号。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "integer",
                        "description": "要删除的记忆条目序号",
                    },
                    "clear_all": {
                        "type": "boolean",
                        "description": "是否清空此空间的所有记忆，默认 false",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
    },
]

# 工具名称集合，用于 Orchestrator 分发
SPACE_MEMORY_TOOL_NAMES: set[str] = {
    "write_to_space_memory",
    "delete_from_space_memory",
}
