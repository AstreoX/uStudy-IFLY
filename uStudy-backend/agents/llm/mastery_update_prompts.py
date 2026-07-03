"""掌握分更新 Prompt 模板"""

MASTERY_UPDATE_SYSTEM_PROMPT = """# 知识图谱掌握分更新专家

你是一位教育评估专家，负责根据学生的答题情况更新知识图谱中相关节点的掌握分。

## 任务

分析学生的答题结果，判断哪些知识点节点需要更新掌握分，并给出具体的更新值。

## 输入格式说明

- **正确的题目**：只显示题干摘要
- **错误/部分正确的题目**：显示完整题干，需重点分析并降低相关节点掌握分

## 更新策略

| 答题结果 | 掌握分变化 | 说明 |
|----------|-----------|------|
| 完全正确 | +10 ~ +20 | 当前掌握分低时增幅大，高时增幅小 |
| 部分正确 | +5 ~ +10 | 温和提升 |
| 错误 | -5 ~ -15 | 当前掌握分高时降幅大，低时降幅小 |

## 规则

1. **范围限制**：新掌握分必须在 0-100 之间
2. **谨慎关联**：只更新与题目内容**明确相关**的节点，不要过度关联
3. **无关节点不动**：如果知识图谱中的节点与本次测试题目无关，不要包含在更新列表中
4. **增量更新**：基于当前掌握分进行增减，不是直接设置新值
5. **重点关注错题**：错误题目是掌握分下降的主要依据

## 输出格式

请严格按照以下 JSON 格式输出：

```json
{
  "updates": [
    {
      "node_name": "节点名称（必须与提供的节点列表完全匹配）",
      "current_mastery": 50,
      "new_mastery": 65,
      "reason": "简短说明（10字以内）"
    }
  ]
}
```

如果没有任何节点需要更新，输出：

```json
{
  "updates": []
}
```
"""

MASTERY_UPDATE_USER_TEMPLATE = """请根据以下答题情况更新知识图谱节点的掌握分：

## 测试主题
{quiz_topic}

## 当前知识图谱节点
{nodes_list}

## 答题结果

{question_results}

---

请分析哪些节点与上述题目相关，并给出掌握分更新建议。
输出必须是合法的 JSON 格式。
"""

# 错误/部分正确题目的详细模板
QUESTION_RESULT_TEMPLATE = """#### 第 {order} 题（{status_cn}，得分：{score}/{max_score}）
**题干**：{question_stem}
"""

# 正确题目的精简模板
CORRECT_QUESTION_BRIEF = "- 第{order}题：{stem_preview}\n"

STATUS_CN_MAP = {
    "correct": "正确",
    "wrong": "错误",
    "partial": "部分正确",
}


def _truncate_stem(stem: str, max_len: int = 60) -> str:
    """截断题干，保留前 max_len 个字符"""
    if len(stem) <= max_len:
        return stem
    return stem[:max_len] + "..."


def build_mastery_update_prompt(
    quiz_topic: str,
    nodes: list[dict],
    question_results: list[dict],
) -> list[dict[str, str]]:
    """
    构建掌握分更新 Prompt

    优化策略：
    - 正确题目：只保留题干摘要，减少 token 消耗
    - 错误/部分正确题目：保留完整题干，便于 LLM 分析关联节点

    Args:
        quiz_topic: 测试主题
        nodes: 知识图谱节点列表，每项包含:
            - id: 节点 ID
            - label: 节点名称
            - mastery: 当前掌握分（可为 None）
        question_results: 答题结果列表，每项包含:
            - order: 题目序号
            - question_stem: 题干
            - score: 得分
            - max_score: 满分
            - status: correct/wrong/partial

    Returns:
        消息列表，用于 LLM API 调用
    """
    # 格式化节点列表
    nodes_lines = []
    for node in nodes:
        mastery_display = node.get("mastery")
        if mastery_display is None:
            mastery_display = "未知"
        nodes_lines.append(f"- {node['label']}（当前掌握分：{mastery_display}）")
    nodes_list = "\n".join(nodes_lines) if nodes_lines else "（暂无节点）"

    # 分离正确和错误/部分正确的题目
    correct_items = [q for q in question_results if q.get("status") == "correct"]
    wrong_items = [q for q in question_results if q.get("status") != "correct"]

    # 格式化正确题目（精简）
    correct_section = ""
    if correct_items:
        correct_section = f"### 正确的题目（共{len(correct_items)}题，掌握分可适当提升）\n"
        for item in correct_items:
            stem_preview = _truncate_stem(item.get("question_stem", ""))
            correct_section += CORRECT_QUESTION_BRIEF.format(
                order=item.get("order", "?"),
                stem_preview=stem_preview,
            )

    # 格式化错误/部分正确题目（详细）
    wrong_section = ""
    if wrong_items:
        wrong_section = f"### 错误/部分正确的题目（共{len(wrong_items)}题，需降低相关节点掌握分）\n"
        for item in wrong_items:
            status = item.get("status", "wrong")
            status_cn = STATUS_CN_MAP.get(status, status)
            wrong_section += QUESTION_RESULT_TEMPLATE.format(
                order=item.get("order", "?"),
                status_cn=status_cn,
                score=item.get("score", 0),
                max_score=item.get("max_score", 0),
                question_stem=item.get("question_stem", ""),
            )

    question_results_text = correct_section + "\n" + wrong_section

    user_content = MASTERY_UPDATE_USER_TEMPLATE.format(
        quiz_topic=quiz_topic,
        nodes_list=nodes_list,
        question_results=question_results_text,
    )

    return [
        {"role": "system", "content": MASTERY_UPDATE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
