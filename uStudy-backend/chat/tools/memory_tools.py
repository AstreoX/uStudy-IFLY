"""Long-Term Memory Tools - AI 工具定义"""

from typing import Any


MEMORY_TOOLS: list[dict[str, Any]] = [
    # 工具 1: 写入记忆
    {
        "type": "function",
        "function": {
            "name": "write_to_long_term_memory",
            "description": """将重要信息写入用户的长期记忆。长期记忆在所有对话中持久保存。

使用时机：
1. 用户明确要求记住某事（"记住我喜欢..."、"以后要注意..."）
2. 用户纠正对其偏好的理解
3. 用户分享重要个人信息或学习目标
4. 发现用户特定的学习习惯或偏好

不应使用：
- 临时性信息
- 已在学习空间偏好中记录的内容
- 敏感隐私信息（密码、身份证号等）

写入内容应简洁，使用第三人称陈述句。""",
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
    # 工具 2: 删除记忆（按序号）
    {
        "type": "function",
        "function": {
            "name": "delete_from_long_term_memory",
            "description": """删除用户长期记忆中的特定条目。

使用时机：
1. 用户明确要求忘记/删除某条记忆（"忘掉我说的..."、"删掉第X条..."）
2. 用户说之前记录的信息已过时或不正确
3. 用户要求清除所有记忆

操作方式：
- 提供 entry_id 删除指定序号的条目
- 设置 clear_all=true 清空所有长期记忆（谨慎使用）

注意：长期记忆内容已在系统提示词中显示，可直接查看序号。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "integer",
                        "description": "要删除的记忆条目序号",
                    },
                    "clear_all": {
                        "type": "boolean",
                        "description": "是否清空所有长期记忆，默认 false",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
    },
]


# 工具名称集合，用于快速判断
MEMORY_TOOL_NAMES: set[str] = {
    "write_to_long_term_memory",
    "delete_from_long_term_memory",
}
