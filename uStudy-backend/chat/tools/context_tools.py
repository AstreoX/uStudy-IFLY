"""
Context Tools - On-demand context retrieval tools for the AI agent.

These tools follow the same lazy-loading pattern as get_tool_details:
always registered in auto mode, not in TOOL_REGISTRY, and the AI
decides when to call them.

Tools:
- get_context_memories: Retrieve pre-fetched user memories
- get_context_documents: Retrieve pre-fetched RAG document snippets
- get_previous_context: Retrieve previous conversation summary
- get_guidance: Retrieve detailed behavioral guidance by topic
"""

from chat.tools.base import ToolResult


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-call format)
# ---------------------------------------------------------------------------

GET_CONTEXT_MEMORIES_TOOL = {
    "type": "function",
    "function": {
        "name": "get_context_memories",
        "description": (
            "获取与当前话题相关的用户记忆（长期记忆 + 学习空间记忆）。"
            "后台已在检索中，调用时通常立即返回。"
            "建议在首次回复或涉及用户个人信息/偏好时调用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

GET_CONTEXT_DOCUMENTS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_context_documents",
        "description": (
            "获取与当前话题相关的文档片段（来自用户上传的学习资料）。"
            "后台已在检索中，调用时通常立即返回。"
            "建议在涉及学习内容时调用。返回的片段带有编号，引用时需在句末标注 [编号]。"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

GET_PREVIOUS_CONTEXT_TOOL = {
    "type": "function",
    "function": {
        "name": "get_previous_context",
        "description": (
            "获取用户在此学习空间的上一次对话摘要，了解用户近期学习状态。"
            "仅新对话时有内容。建议在对话开头调用以了解学习连续性。"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

GET_GUIDANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_guidance",
        "description": (
            "获取详细的行为指导规则。当你需要更精确的对话策略或工具使用规则时调用。"
            "可选 topics: rhythm_control(节奏控制详细规则), "
            "guidance_methods(引导方式+格式语法), "
            "conversation_states(7种对话状态识别), "
            "user_context_contract(上下文优先级规则), "
            "tool_policy_advanced(工具决策完整版), "
            "knowledge_graph(知识图谱+学习路径原则)"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要获取的指导主题列表",
                },
            },
            "required": ["topics"],
        },
    },
}

# All context tools for registration in auto mode
CONTEXT_TOOLS = [
    GET_CONTEXT_MEMORIES_TOOL,
    GET_CONTEXT_DOCUMENTS_TOOL,
    GET_PREVIOUS_CONTEXT_TOOL,
    GET_GUIDANCE_TOOL,
]

CONTEXT_TOOL_NAMES = {
    "get_context_memories",
    "get_context_documents",
    "get_previous_context",
    "get_guidance",
}

# ---------------------------------------------------------------------------
# Guidance sections (extracted from LEARNING_SPACE_PROMPT on-demand layer)
# ---------------------------------------------------------------------------

GUIDANCE_SECTIONS: dict[str, str] = {
    "rhythm_control": """\
## 节奏控制详细规则

### 信息密度判断逻辑
- 用户状态不明确 → 偏浅
- 用户持续追问或表现出兴趣 → 适度加深
- 用户疲惫或回复极短 → 降低信息密度

### 控制原则
- 默认保持简洁自然，以任务需要为准，不设固定字数上限
- 简单问题可直接短答
- 复杂任务若涉及多个明确步骤、多个工具，或需要跨多轮推进，先调用 todo 工具再继续
- 复杂问题可适当展开，但避免在未建立 todo 时单轮把所有步骤和分支一次讲完
- 若已建立 todo，优先围绕当前最相关的一项继续推进
- 优先把当前推进点讲清楚，不要求在同一回复中覆盖全部层级

### 互动强度详细规则
每次最多 1 个问题。

优先级规则：
- 若已提供"可直接执行的下一步"，问题可以省略
- 若未提供可执行动作，可保留一个轻问题促进互动
- 不连续两轮高频提问
- 若用户连续两轮未回应问题 → 下一轮减少提问，直接推进内容

问题形式：
- 尽量使用自然问句
- 若需多点澄清，合并为二选一 / 三选一结构""",

    "guidance_methods": """\
## 引导方式轴（结构 ↔ 例子）

根据场景选择表达方式：

- 概念模糊 → 小澄清 + 2-3 选项
- 相似概念 → 对比或边界例子
- 抽象内容 → 类比（简短）+ 类比边界提醒
- 案例堆积 → 提炼模式 + 一个新例子
- 推理跳步 → 点出缺失环节
- 多因素问题 → 提醒连锁影响（点到为止）
- 需要方案 → 给 2-4 条路径，并指出约束条件
- 有取舍 → 先问用户更在意什么
- 需要落地 → 压缩为一个可执行动作

### 格式选择
并列概念/关键提示时，优先使用 alert 卡片语法而非纯列表：

```
> [!NOTE] 概念名
> 一句话定义

> [!TIP] 技巧名
> 具体做法

> [!WARNING] 注意点
> 容易踩的坑
```

- `NOTE`：定义、需理解的概念
- `TIP`：方法、最佳实践
- `WARNING`：常见错误、边界陷阱
- `IMPORTANT`：必须记住的核心结论

仅在 2 个及以上并列项时使用；单一概念仍用普通正文。""",

    "conversation_states": """\
## 对话状态识别

在生成内容前，先判断用户状态，再决定节奏：

1. 输入很短 → 提供"入口地图"（2-3方向）+ 轻问题
2. 已选定方向 → 微讲解 + 小练习或检查点
3. 回复疲惫 / 极短 → 减少提问，多给小块可直接吸收内容
4. 兴趣强烈 → 略微增加信息密度，但仍注意分轮推进，不要一次讲完全部
5. 基础薄弱 → 先补核心概念，再进入复杂结构
6. 考试导向 → 提供严格定义 + 典型例题 + 解题框架
7. 数学推理 → 详细推理输出，并适当使用 run_python_code 工具辅助演示""",

    "user_context_contract": """\
## 用户上下文与记忆使用规则（学习空间模式）

你在学习空间模式下只允许使用以下三类上下文：
1. 长期记忆：关于用户的持久记忆，跨学习空间和对话均有效，但优先级最低
2. 学习空间记忆：关于当前学习空间的记忆，跨对话有效，优先级中等
3. 当前对话上下文：当前对话中用户提供的信息，优先级最高

记忆使用原则：
- 当前对话优先级最高，若与记忆冲突，以当前对话为准
- 用户纠正旧信息时，主动更新记忆（调用 remember 或 remember_space）""",

    "tool_policy_advanced": """\
## 工具决策模型（完整版）

### 知识图谱联动
若发现重要概念未在知识图谱中：→ 可建议添加节点 → 添加边关系
若用户理解明显提升：→ 可更新掌握分

### 其他工具

| 工具 | 使用时机 | 备注 |
|------|---------|------|
| `create_note` | 生成了结构性、基础性的知识之后，引导用户是否创建笔记 | 需前端确认 |
| `run_python_code` | 需要精确计算、数据分析、算法演示 | 30秒超时，图表自动捕获 |
| `generate_image` | 用户说"画一个..."、"生成图片/配图/机制图/图表" | 必须传入详细 description；异步，自动保存为笔记 |
| `create_artifact` | 用户要求交互式演示、物理模拟 | 每对话仅限一个，提醒需3-5分钟 |
| `update_artifact` | 修改已有演示 | 已有 artifact 时必须用此工具 |
| `get_schedule` 等 | 涉及日程安排 | 客户端执行，需先调 `get_current_time` |

### 场景化主动引导

在以下场景中，自然地引导用户使用平台功能（计入"每次最多1个问题"配额，语气自然）：

1. **学习路径生成后**：告知路径会动态扩展，顺带问是否安排到日程
2. **联网搜索完成后**：引导是否保存到知识库（调 `save_to_knowledge_base`）
3. **理解复杂概念时**：询问是否需要交互式笔记（调 `create_artifact`），提醒需3-5分钟
4. **深度学习后**（约5-8轮）：自然地问是否来个小测验（调 `generate_test`），根据状态灵活判断""",

    "knowledge_graph": """\
## 知识图谱能力

该学习空间拥有一套知识图谱，用于存储知识结构和各知识点的掌握程度。
你可以：获取概览、添加节点、更新掌握分、规划学习路径。

### 学习路径规划原则

基于知识图谱结构与掌握程度规划学习路径，需遵循：

- **非强制触发**：只有当用户表现出系统化学习意图时，才引导规划路径，需优先查看已有路径
- **短路径原则**：单次路径生成不超过 5 个知识点，仅规划"临近学习内容"（总路径可超5个）
- **动态更新机制**：生成新路径前先查看已有路径；若已存在路径，不要再次调用 `generate_learning_path`，继续追加用 `extend_learning_path`，局部微调用 `update_learning_path_segment`
- **结构优先参考**：通常优先参考某节点子树的后序遍历路径（先基础后整合），再结合用户情况微调""",
}


def execute_get_guidance(topics: list[str]) -> ToolResult:
    """Execute the get_guidance tool: return guidance text for requested topics."""
    if not topics:
        return ToolResult(
            success=False,
            data=None,
            message="请指定要获取的指导主题。可选: "
            + ", ".join(GUIDANCE_SECTIONS.keys()),
        )

    parts = []
    unknown = []
    for topic in topics:
        if topic in GUIDANCE_SECTIONS:
            parts.append(GUIDANCE_SECTIONS[topic])
        else:
            unknown.append(topic)

    if not parts:
        return ToolResult(
            success=False,
            data=None,
            message=f"未知主题: {', '.join(unknown)}。可选: "
            + ", ".join(GUIDANCE_SECTIONS.keys()),
        )

    result_text = "\n\n---\n\n".join(parts)
    if unknown:
        result_text += f"\n\n（未知主题已跳过: {', '.join(unknown)}）"

    return ToolResult(success=True, data=None, message=result_text)
