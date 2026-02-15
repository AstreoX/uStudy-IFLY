"""Vector Memory Tools - 向量记忆 AI 工具定义"""

from typing import Any


VECTOR_MEMORY_TOOLS: list[dict[str, Any]] = [
    # 工具 1: 写入长期记忆
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": """将重要信息写入用户的长期记忆。长期记忆在所有学习空间和对话中持久保存。

使用时机：
1. 用户明确要求记住某事（"记住我喜欢..."、"以后要注意..."）
2. 用户纠正对其偏好的理解
3. 用户分享重要个人信息或学习目标
4. 发现用户特定的学习习惯或偏好

不应使用：
- 临时性信息
- 特定于某个学习空间的内容（请使用 remember_space）
- 敏感隐私信息（密码、身份证号等）

写入内容应简洁，使用陈述句描述关于用户的信息。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要记住的关于用户的信息",
                        "maxLength": 500,
                    },
                },
                "required": ["content"],
            },
        },
    },
    # 工具 2: 写入空间记忆
    {
        "type": "function",
        "function": {
            "name": "remember_space",
            "description": """将信息写入当前学习空间的记忆。空间记忆仅在当前学习空间内有效。

使用时机：
1. 用户分享与当前学习主题相关的偏好
2. 记录用户在当前学习空间的进度
3. 记录用户在当前主题的难点或关注点
4. 记录与当前学习内容相关的背景知识

不应使用：
- 通用的用户信息（请使用 remember）
- 临时性对话内容

写入内容应具体，与当前学习空间主题相关。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要记住的关于当前学习空间的信息",
                        "maxLength": 500,
                    },
                },
                "required": ["content"],
            },
        },
    },
    # 工具 3: 删除记忆
    {
        "type": "function",
        "function": {
            "name": "forget",
            "description": """删除用户记忆中的特定条目或清空所有记忆。

使用时机：
1. 用户明确要求忘记/删除某条记忆
2. 用户说之前记录的信息已过时或不正确
3. 用户要求清除所有记忆

注意：需要先使用 search_memories 找到要删除的记忆 ID。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "要删除的记忆 ID（UUID 格式）",
                    },
                    "clear_all_long_term": {
                        "type": "boolean",
                        "description": "是否清空所有长期记忆",
                        "default": False,
                    },
                    "clear_all_space": {
                        "type": "boolean",
                        "description": "是否清空当前学习空间的所有记忆",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
    },
    # 工具 4: 搜索记忆
    {
        "type": "function",
        "function": {
            "name": "search_memories",
            "description": """搜索用户记忆中的相关信息。

使用时机：
1. 需要查找用户之前提到的特定信息
2. 用户询问"我之前说过..."
3. 需要找到记忆 ID 以便删除
4. 确认是否已有相关记忆

返回结果按相关性排序，包含记忆 ID、内容和相似度分数。""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询内容",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["long_term", "space", "all"],
                        "description": "搜索范围：long_term（长期记忆）、space（当前空间）、all（全部）",
                        "default": "all",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回结果数量（1-20）",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# 工具名称集合，用于快速判断
VECTOR_MEMORY_TOOL_NAMES: set[str] = {
    "remember",
    "remember_space",
    "forget",
    "search_memories",
}
