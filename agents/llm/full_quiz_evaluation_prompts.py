"""整卷评估 Prompt 模板"""

FULL_QUIZ_EVALUATION_SYSTEM_PROMPT = """# 整卷评估专家

你是一位教育评估专家，负责对学生的测试卷进行简明扼要的评估总结。

## 输出要求

**极简风格**：每条只写核心要点，不超过15个字，不要详细解释或分析。

## 输出格式

请严格按照以下 JSON 格式输出：

```json
{
  "strengths": [
    "掌握了XX概念",
    "XX题型正确率高"
  ],
  "weaknesses": [
    "XX知识点薄弱",
    "XX概念混淆"
  ],
  "suggestions": [
    "复习XX章节",
    "多练习XX题型"
  ]
}
```

## 注意事项

1. **极简**：每条10-15字，只写要点，禁止详细分析
2. **条数**：每项1-3条即可
3. **全对**：缺点写"暂无明显不足"
4. **全错**：优点找闪光点，建议要鼓励
"""

FULL_QUIZ_EVALUATION_USER_TEMPLATE = """请对以下测试答卷进行综合评估：

## 测试基本信息
- **测试主题**：{quiz_topic}
- **难度级别**：{difficulty_level}
- **总分**：{total_score} 分
- **得分**：{actual_score} 分
- **得分率**：{score_percentage}%

## 题目与作答详情

{questions_detail}

---

请根据以上信息，对学生的整体表现进行综合评估。
输出必须是合法的 JSON 格式。
"""

QUESTION_DETAIL_TEMPLATE = """
### 第 {order} 题（{question_type_cn}，{max_score}分）
**题干**：{question_stem}
{options_section}
**正确答案**：{correct_answer_display}
**学生答案**：{user_answer_display}
**得分**：{score}/{max_score}
**判定**：{status}
{ai_comment_section}
"""

QUESTION_TYPE_CN_MAP = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "true_false": "判断题",
    "short_answer": "简答题",
}

STATUS_CN_MAP = {
    "correct": "正确",
    "wrong": "错误",
    "partial": "部分正确",
}


def _format_options(options: list[str] | None) -> str:
    """格式化选项列表"""
    if not options:
        return ""
    option_labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
    lines = []
    for i, opt in enumerate(options):
        label = option_labels[i] if i < len(option_labels) else str(i + 1)
        lines.append(f"  {label}. {opt}")
    return "**选项**：\n" + "\n".join(lines)


def _format_single_choice_answer(
    answer: dict | None, options: list[str] | None
) -> str:
    """格式化单选题答案"""
    if not answer:
        return "（未作答）"
    index = answer.get("index")
    if index is None:
        return "（未作答）"
    labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
    label = labels[index] if index < len(labels) else str(index + 1)
    text = options[index] if options and index < len(options) else ""
    return f"{label}. {text}" if text else label


def _format_multiple_choice_answer(
    answer: dict | None, options: list[str] | None
) -> str:
    """格式化多选题答案"""
    if not answer:
        return "（未作答）"
    indices = answer.get("indices", [])
    if not indices:
        return "（未作答）"
    labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
    parts = []
    for idx in sorted(indices):
        label = labels[idx] if idx < len(labels) else str(idx + 1)
        text = options[idx] if options and idx < len(options) else ""
        parts.append(f"{label}. {text}" if text else label)
    return "、".join(parts)


def _format_true_false_answer(answer: dict | None) -> str:
    """格式化判断题答案"""
    if not answer:
        return "（未作答）"
    value = answer.get("value")
    if value is True:
        return "正确"
    if value is False:
        return "错误"
    return "（未作答）"


def _format_short_answer(answer: dict | None) -> str:
    """格式化简答题答案"""
    if not answer:
        return "（未作答）"
    # 兼容两种字段名：用户答案用 text，参考答案用 reference
    text = (answer.get("text") or answer.get("reference") or "").strip()
    return text if text else "（未作答）"


def _format_answer(
    question_type: str,
    answer: dict | None,
    options: list[str] | None,
) -> str:
    """根据题型格式化答案"""
    if question_type == "single_choice":
        return _format_single_choice_answer(answer, options)
    if question_type == "multiple_choice":
        return _format_multiple_choice_answer(answer, options)
    if question_type == "true_false":
        return _format_true_false_answer(answer)
    if question_type == "short_answer":
        return _format_short_answer(answer)
    return str(answer) if answer else "（未作答）"


def build_full_quiz_evaluation_prompt(
    quiz_topic: str,
    difficulty_level: str,
    total_score: int,
    actual_score: int,
    question_results: list[dict],
) -> list[dict[str, str]]:
    """
    构建整卷评估 Prompt

    Args:
        quiz_topic: 测试主题
        difficulty_level: 难度级别（easy/medium/hard）
        total_score: 总分
        actual_score: 实际得分
        question_results: 逐题结果列表，每项包含:
            - order: 题目序号
            - question_type: 题型
            - question_stem: 题干
            - options: 选项列表（选择题）
            - correct_answer: 正确答案
            - user_answer: 用户答案
            - score: 得分
            - max_score: 满分
            - status: correct/wrong/partial
            - ai_evaluation: 简答题AI评语（可选）

    Returns:
        消息列表，用于 LLM API 调用
    """
    difficulty_cn = {"easy": "简单", "medium": "中等", "hard": "困难"}.get(
        difficulty_level, difficulty_level
    )
    score_percentage = round(actual_score / total_score * 100, 1) if total_score else 0

    questions_detail_parts = []
    for item in question_results:
        question_type = item["question_type"]
        options = item.get("options")

        options_section = _format_options(options) if options else ""
        correct_answer_display = _format_answer(
            question_type, item["correct_answer"], options
        )
        user_answer_display = _format_answer(
            question_type, item["user_answer"], options
        )

        ai_comment_section = ""
        if question_type == "short_answer" and item.get("ai_evaluation"):
            ai_comment_section = f"**AI评语**：{item['ai_evaluation']}"

        detail = QUESTION_DETAIL_TEMPLATE.format(
            order=item["order"],
            question_type_cn=QUESTION_TYPE_CN_MAP.get(question_type, question_type),
            max_score=item["max_score"],
            question_stem=item["question_stem"],
            options_section=options_section,
            correct_answer_display=correct_answer_display,
            user_answer_display=user_answer_display,
            score=item["score"],
            status=STATUS_CN_MAP.get(item["status"], item["status"]),
            ai_comment_section=ai_comment_section,
        )
        questions_detail_parts.append(detail)

    questions_detail = "\n".join(questions_detail_parts)

    user_content = FULL_QUIZ_EVALUATION_USER_TEMPLATE.format(
        quiz_topic=quiz_topic,
        difficulty_level=difficulty_cn,
        total_score=total_score,
        actual_score=actual_score,
        score_percentage=score_percentage,
        questions_detail=questions_detail,
    )

    return [
        {"role": "system", "content": FULL_QUIZ_EVALUATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
