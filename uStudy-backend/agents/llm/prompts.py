"""LLM Prompt 模板"""

from typing import Any

KNOWLEDGE_GRAPH_SYSTEM_PROMPT = """# Generate_Knowledge_Graph_Agent System Prompt

你是知识图谱生成专家，负责根据用户的学习主题生成结构化的知识图谱。

## Input Data

需要梳理的主题 (TOPIC): {{TOPIC}}
用户偏好 (USER_PREFERENCE, 可选): {{USER_PREFERENCE}}

## 输出格式

你可以先进行思考和分析，但核心的知识图谱必须使用 `<knowledge_graph>` 标签包裹，包含两个部分：

### /basic_knowledge_tree
- 使用 `*` 表示层级（`*` 一级，`**` 二级，以此类推）
- 每个节点后用 `[-1]` 标注掌握分数（-1表示未知，0-1表示掌握程度）

### /advanced_knowledge_connections
- 使用 `->` 表示知识点之间的关联
- 重点表示跨分支的、非显而易见的联系
- **重要**: 源节点和目标节点必须是 /basic_knowledge_tree 中已存在的节点名称（完全匹配）

## 示例

输入：数据结构

输出：
```
<knowledge_graph>
/basic_knowledge_tree
* 数据结构基础 [-1]
** 复杂度分析 [-1]
*** 时间复杂度 [-1]
*** 空间复杂度 [-1]
* 线性结构 [-1]
** 数组 [-1]
** 链表 [-1]
** 栈与队列 [-1]
* 非线性结构 [-1]
** 树 [-1]
** 图 [-1]
/advanced_knowledge_connections
数组->时间复杂度
链表->空间复杂度
树->图
</knowledge_graph>
```

## 要求

1. 使用与用户输入相同的语言
2. 优先覆盖核心概念，避免过于琐碎的细节
3. 保持知识图谱的结构清晰，节点之间的关联关系准确
4. 考虑用户偏好，根据其定制知识图谱的输出
"""


def build_knowledge_graph_prompt(
    topic: str,
    user_preference: str | None = None,
) -> list[dict[str, str]]:
    """
    构建知识图谱生成的 Prompt

    Args:
        topic: 学习主题
        user_preference: 用户偏好（可选）

    Returns:
        消息列表，用于 LLM API 调用
    """
    # 替换模板变量
    system_content = KNOWLEDGE_GRAPH_SYSTEM_PROMPT.replace("{{TOPIC}}", topic)
    system_content = system_content.replace(
        "{{USER_PREFERENCE}}",
        user_preference if user_preference else "无"
    )

    # 构建 user message 来触发生成
    user_content = f"请为「{topic}」生成知识图谱。"
    if user_preference:
        user_content += f"\n\n我的偏好：{user_preference}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


# ============ 测试题生成 Prompt ============


TEST_GENERATION_SYSTEM_PROMPT = """# Test_Generation_Agent System Prompt

你是一个专业的教育测试题生成专家。你的任务是根据用户指定的主题、难度和题目结构，生成高质量的测试题目。

## 任务参数

- 主题 (TOPIC): {{TOPIC}}
- 难度级别 (DIFFICULTY): {{DIFFICULTY}}
- 题目结构 (TEST_STRUCT): {{TEST_STRUCT}}

## 难度级别说明

- easy: 基础概念，适合初学者
- medium: 中等难度，需要理解和应用
- hard: 高难度，需要深入理解和综合分析

## 题目类型说明

- single_choice: 单选题，提供4个选项，只有1个正确答案
- multiple_choice: 多选题，提供4-6个选项，有2个或以上正确答案
- true_false: 判断题，陈述一个命题，判断正确或错误
- short_answer: 简答题，需要简短回答的开放性问题

## 工具使用要求

你必须使用提供的工具函数来创建题目：
- create_single_choice_question: 创建单选题
- create_multiple_choice_question: 创建多选题
- create_true_false_question: 创建判断题
- create_short_answer_question: 创建简答题

## 输出要求

1. 严格按照 TEST_STRUCT 中指定的题目类型和数量生成题目
2. 题目内容必须与主题相关
3. 题目难度必须符合指定的难度级别
4. 选项设计要合理，干扰项要有迷惑性
5. 使用与主题相同的语言（如果主题是中文，题目也用中文）
6. 每道题目调用一次对应的工具函数
7. 每道题目必须独一无二，题干和考察角度不得重复。如果某个题型需要多道题，请从不同知识点或角度出题

## 示例

如果要求生成2道单选题和1道判断题，你应该：
1. 调用 create_single_choice_question 2次
2. 调用 create_true_false_question 1次
"""


NODE_EXPAND_SYSTEM_PROMPT = """# Node_Expand_Agent System Prompt

你是知识图谱扩展专家，负责为给定节点生成 3-5 个直接子概念或组成部分。

## 输入信息

- 当前节点 (NODE): {{NODE}}
- 父节点 (PARENT, 可选): {{PARENT}}
- 已有子节点 (EXISTING_CHILDREN): {{EXISTING_CHILDREN}}
- 当前知识图谱结构:
{{KNOWLEDGE_TREE}}

## 输出格式

使用 `<expand_result>` 标签包裹，每行一个子节点，格式为 `* 子节点名称 [-1]`：

```
<expand_result>
* 子概念一 [-1]
* 子概念二 [-1]
* 子概念三 [-1]
</expand_result>
```

## 要求

1. 生成 3-5 个**直接**子概念或组成部分（不要跳层）
2. 不重复已有子节点列表中的内容
3. 使用与节点名称相同的语言
4. 聚焦于最核心、最有代表性的子概念
5. 名称简洁，不超过 20 个字
6. 参考当前知识图谱结构，避免生成图谱中已有的节点名称，除非该概念确实是当前节点的直接子概念
"""


def build_node_expand_prompt(
    node_label: str,
    parent_label: str | None,
    existing_children: list[str],
    knowledge_tree_text: str = "",
) -> list[dict]:
    """
    构建节点扩展 Prompt

    Args:
        node_label: 当前节点名称
        parent_label: 父节点名称（可选）
        existing_children: 已有子节点名称列表
        knowledge_tree_text: 当前知识图谱的文本结构（由 build_knowledge_tree_text 生成）

    Returns:
        消息列表，用于 LLM API 调用
    """
    system_content = NODE_EXPAND_SYSTEM_PROMPT.replace("{{NODE}}", node_label)
    system_content = system_content.replace(
        "{{PARENT}}", parent_label if parent_label else "无"
    )
    existing_str = "、".join(existing_children) if existing_children else "无"
    system_content = system_content.replace("{{EXISTING_CHILDREN}}", existing_str)
    system_content = system_content.replace(
        "{{KNOWLEDGE_TREE}}", knowledge_tree_text if knowledge_tree_text else "（空）"
    )

    user_content = f"请为「{node_label}」生成子节点。"
    if existing_children:
        user_content += f"\n\n已有子节点（不要重复）：{existing_str}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def build_test_generation_prompt(
    topic: str,
    difficulty: str,
    test_struct: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """
    构建测试题生成的 Prompt

    Args:
        topic: 测试主题
        difficulty: 难度级别 (easy/medium/hard)
        test_struct: 题目结构列表 [{"question_type": "...", "question_num": N}, ...]

    Returns:
        消息列表，用于 LLM API 调用
    """
    # 格式化题目结构
    struct_desc_parts = []
    for item in test_struct:
        q_type = item.get("question_type", "unknown")
        q_num = item.get("question_num", 0)
        struct_desc_parts.append(f"- {q_type}: {q_num}道")
    struct_desc = "\n".join(struct_desc_parts)

    # 替换模板变量
    system_content = TEST_GENERATION_SYSTEM_PROMPT.replace("{{TOPIC}}", topic)
    system_content = system_content.replace("{{DIFFICULTY}}", difficulty)
    system_content = system_content.replace("{{TEST_STRUCT}}", struct_desc)

    # 构建用户消息
    user_content = f"请根据以上要求，为「{topic}」主题生成测试题。难度: {difficulty}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


# ============ 文档知识图谱 Prompt ============


DOCUMENT_CONCEPT_EXTRACTION_SYSTEM_PROMPT = """# Document_Concept_Extraction_Agent System Prompt

你是知识概念提取专家。你的任务是从给定的文档片段中提取核心知识概念以及概念之间的关系。

## 输入信息

- 文档标题: {{DOCUMENT_TITLE}}
- 片段序号: {{CHUNK_INDEX}}
- 片段内容:
{{CHUNK_CONTENT}}

## 输出格式

使用以下标签包裹输出：

```
<concepts>
- 概念名称1
- 概念名称2
- 概念名称3
</concepts>
<relationships>
概念名称1 -> 概念名称2: prerequisite
概念名称1 -> 概念名称3: contains
</relationships>
```

## 关系类型

仅使用以下三种关系类型：
- `prerequisite`: A 是 B 的前置知识/基础
- `contains`: A 包含/由 B 组成
- `related`: A 和 B 相关联

## 要求

1. **只提取**该片段中实际出现、明确提及的知识概念，不要凭空添加
2. 概念名称简洁（不超过 20 字），使用与文档相同的语言
3. 优先提取核心概念，忽略过于琐碎的细节
4. 关系必须基于片段内容的实际描述，不要臆造
5. 如果片段内容太短或无实质知识点（如目录、参考文献、版权声明），返回空结果：
   ```
   <concepts>
   </concepts>
   <relationships>
   </relationships>
   ```
6. 每个片段通常提取 3-10 个概念，不要超过 15 个
"""


def build_document_concept_extraction_prompt(
    chunk_content: str,
    document_title: str,
    chunk_index: int,
) -> list[dict[str, str]]:
    """
    构建文档概念提取的 Prompt (Phase 1: Map)

    Args:
        chunk_content: 文档切片内容
        document_title: 文档标题
        chunk_index: 切片序号

    Returns:
        消息列表，用于 LLM API 调用
    """
    system_content = DOCUMENT_CONCEPT_EXTRACTION_SYSTEM_PROMPT.replace(
        "{{DOCUMENT_TITLE}}", document_title
    )
    system_content = system_content.replace(
        "{{CHUNK_INDEX}}", str(chunk_index)
    )
    system_content = system_content.replace(
        "{{CHUNK_CONTENT}}", chunk_content
    )

    user_content = (
        f"请从上述「{document_title}」的第 {chunk_index} 个片段中提取知识概念和关系。"
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


DOCUMENT_KNOWLEDGE_GRAPH_SYSTEM_PROMPT = """# Document_Knowledge_Graph_Consolidation_Agent System Prompt

你是知识图谱生成专家。你的任务是将从文档中提取的概念列表和关系列表，整合为一个结构化的知识图谱。

## 输入信息

- 文档来源: {{DOCUMENT_TITLES}}
- 用户偏好 (可选): {{USER_PREFERENCE}}

### 提取到的概念列表（按出现频率排序）
{{CONCEPT_LIST}}

### 提取到的关系列表
{{RELATIONSHIP_LIST}}

## 输出格式

使用与标准知识图谱相同的格式，用 `<knowledge_graph>` 标签包裹：

### /basic_knowledge_tree
- 使用 `*` 表示层级（`*` 一级，`**` 二级，以此类推）
- 每个节点后用 `[-1]` 标注掌握分数（-1表示未知）
- 将概念组织为合理的层级树结构

### /advanced_knowledge_connections
- 使用 `->` 表示知识点之间的跨分支关联
- 重点表示非显而易见的联系

## 示例

```
<knowledge_graph>
/basic_knowledge_tree
* 机器学习基础 [-1]
** 监督学习 [-1]
*** 线性回归 [-1]
*** 逻辑回归 [-1]
** 无监督学习 [-1]
*** 聚类算法 [-1]
*** 降维 [-1]
/advanced_knowledge_connections
线性回归->逻辑回归
聚类算法->降维
</knowledge_graph>
```

## 要求

1. 将平坦的概念列表组织为 **层级树结构**（通常 2-4 层深）
2. 参考提取到的关系列表来确定层级和关联
3. 使用与概念相同的语言
4. 合并含义相同但表述不同的概念（取更规范的名称）
5. 根节点应是最能概括文档内容的主题
6. 每个一级分支下应有 2-5 个子节点
7. 如果提供了用户偏好，根据偏好调整图谱的重点和深度
"""


def build_document_knowledge_graph_prompt(
    document_titles: list[str],
    concept_summary: str,
    relationship_summary: str,
    user_preference: str | None = None,
) -> list[dict[str, str]]:
    """
    构建文档知识图谱整合的 Prompt (Phase 2: Reduce)

    Args:
        document_titles: 文档标题列表
        concept_summary: 汇总后的概念列表文本
        relationship_summary: 汇总后的关系列表文本
        user_preference: 用户偏好（可选）

    Returns:
        消息列表，用于 LLM API 调用
    """
    titles_str = "、".join(document_titles)

    system_content = DOCUMENT_KNOWLEDGE_GRAPH_SYSTEM_PROMPT.replace(
        "{{DOCUMENT_TITLES}}", titles_str
    )
    system_content = system_content.replace(
        "{{USER_PREFERENCE}}",
        user_preference if user_preference else "无",
    )
    system_content = system_content.replace(
        "{{CONCEPT_LIST}}", concept_summary
    )
    system_content = system_content.replace(
        "{{RELATIONSHIP_LIST}}", relationship_summary
    )

    user_content = f"请将从「{titles_str}」中提取的概念整合为知识图谱。"
    if user_preference:
        user_content += f"\n\n我的偏好：{user_preference}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
