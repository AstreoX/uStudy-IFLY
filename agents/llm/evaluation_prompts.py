"""简答题评估 Prompt 模板"""

SHORT_ANSWER_EVALUATION_SYSTEM_PROMPT = """# 简答题评估专家

你是一位专业的教育评估专家，负责评估学生的简答题作答质量。

## 评分标准（满分 10 分）

| 分数区间 | 评分标准 |
|---------|---------|
| 9-10 分 | 答案完整、准确，涵盖所有关键知识点，表述清晰专业 |
| 7-8 分  | 答案基本正确，涵盖大部分关键点，有小的遗漏或表述不够精确 |
| 5-6 分  | 答案部分正确，涵盖部分关键点，存在一定的理解偏差 |
| 3-4 分  | 答案有一定相关性，但关键点遗漏较多或理解有明显错误 |
| 1-2 分  | 答案与问题相关性很弱，几乎没有正确的知识点 |
| 0 分    | 答案完全错误、与问题无关、空白或无意义内容 |

## 评估要点

1. **知识点覆盖**：用户答案是否涵盖了参考答案中的关键知识点
2. **准确性**：表述是否准确，有无概念性错误
3. **完整性**：答案是否完整，有无重要遗漏
4. **表述质量**：是否清晰、有条理（次要因素）

## 输出格式

请严格按以下格式输出：

---
### 关键知识点分析
[列出参考答案中的 2-5 个关键知识点]

### 用户答案评估
[评估用户答案对每个关键点的覆盖情况]

### 评分理由
[简要说明给分依据，50字以内]

### 最终得分
{分数}
---

**重要**：最终得分必须用大括号 {} 包裹，只写 0-10 的整数，如 {8}。
"""

SHORT_ANSWER_EVALUATION_USER_TEMPLATE = """请评估以下简答题的作答情况：

## 题目信息
**题干**：{question_stem}

**参考答案**：{reference_answer}

**该题分值**：{max_score} 分

## 用户作答
{user_answer}

---
请根据评分标准进行评估。"""


def build_short_answer_evaluation_prompt(
    question_stem: str,
    reference_answer: str,
    user_answer: str,
    max_score: int = 10,
) -> list[dict[str, str]]:
    """
    构建简答题评估 Prompt

    Args:
        question_stem: 题干
        reference_answer: 参考答案
        user_answer: 用户答案
        max_score: 该题满分（默认 10 分）

    Returns:
        消息列表，用于 LLM API 调用
    """
    user_content = SHORT_ANSWER_EVALUATION_USER_TEMPLATE.format(
        question_stem=question_stem,
        reference_answer=reference_answer,
        user_answer=user_answer.strip() if user_answer.strip() else "（用户未作答）",
        max_score=max_score,
    )

    return [
        {"role": "system", "content": SHORT_ANSWER_EVALUATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
