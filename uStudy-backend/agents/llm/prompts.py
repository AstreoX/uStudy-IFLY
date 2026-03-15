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
** 数据结构的定义与分类 [-1]
*** 逻辑结构与物理结构 [-1]
*** 抽象数据类型（ADT）[-1]
** 时间复杂度与空间复杂度 [-1]
*** 大O表示法 [-1]
*** 最坏情况 / 平均情况 / 最好情况 [-1]
* 线性结构 [-1]
** 数组 [-1]
*** 顺序存储 [-1]
*** 动态数组 [-1]
** 链表 [-1]
*** 单链表 [-1]
*** 双链表 [-1]
*** 循环链表 [-1]
** 栈 [-1]
*** 顺序栈 [-1]
*** 链式栈 [-1]
** 队列 [-1]
*** 顺序队列 [-1]
*** 循环队列 [-1]
*** 链式队列 [-1]
*** 双端队列 [-1]
* 非线性结构 [-1]
** 树结构 [-1]
*** 树的基本概念 [-1]
*** 二叉树 [-1]
**** 满二叉树 [-1]
**** 完全二叉树 [-1]
**** 二叉搜索树 [-1]
*** 平衡二叉树（AVL）[-1]
*** 堆 [-1]
**** 大根堆 [-1]
**** 小根堆 [-1]
** 图结构 [-1]
*** 图的基本概念 [-1]
*** 图的存储方式 [-1]
**** 邻接矩阵 [-1]
**** 邻接表 [-1]
*** 图的遍历 [-1]
**** 深度优先遍历（DFS）[-1]
**** 广度优先遍历（BFS）[-1]
* 查找结构 [-1]
** 顺序查找 [-1]
** 二分查找 [-1]
** 哈希表 [-1]
*** 哈希函数 [-1]
*** 冲突处理 [-1]
**** 链地址法 [-1]
**** 开放定址法 [-1]
* 排序算法 [-1]
** 插入排序 [-1]
*** 直接插入排序 [-1]
** 交换排序 [-1]
*** 冒泡排序 [-1]
*** 快速排序 [-1]
** 选择排序 [-1]
*** 简单选择排序 [-1]
*** 堆排序 [-1]
** 归并排序 [-1]
* 数据结构应用 [-1]
** 表达式求值 [-1]
** 内存管理模型 [-1]
** 文件系统结构 [-1]
/advanced_knowledge_connections
数组->顺序存储
数组->堆
栈->表达式求值
队列->广度优先遍历（BFS）
二叉树->二叉搜索树
二叉搜索树->二分查找
平衡二叉树（AVL）->二叉搜索树
图的遍历->深度优先遍历（DFS）
图的遍历->广度优先遍历（BFS）
哈希函数->冲突处理
堆->堆排序
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
"""


def build_node_expand_prompt(
    node_label: str,
    parent_label: str | None,
    existing_children: list[str],
) -> list[dict]:
    """
    构建节点扩展 Prompt

    Args:
        node_label: 当前节点名称
        parent_label: 父节点名称（可选）
        existing_children: 已有子节点名称列表

    Returns:
        消息列表，用于 LLM API 调用
    """
    system_content = NODE_EXPAND_SYSTEM_PROMPT.replace("{{NODE}}", node_label)
    system_content = system_content.replace(
        "{{PARENT}}", parent_label if parent_label else "无"
    )
    existing_str = "、".join(existing_children) if existing_children else "无"
    system_content = system_content.replace("{{EXISTING_CHILDREN}}", existing_str)

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
