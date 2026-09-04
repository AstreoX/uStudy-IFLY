"""Prompt templates for mastery evaluation."""


def build_mastery_evaluation_system_prompt(knowledge_tree_text: str) -> str:
    """Build the system prompt for mastery evaluation.

    Args:
        knowledge_tree_text: Formatted knowledge tree from build_knowledge_tree_text()

    Returns:
        Complete system prompt string
    """
    return f"""你是教育评估专家，根据学生与AI的对话评估知识掌握度变化并更新掌握分。

## 知识图谱

{knowledge_tree_text}

格式：*数量=层级深度，[分数]=当前掌握度(0-100)，0=未开始，-1=未评估

## 评估规则

分析学生发言，判断属于哪类：

**A类（大幅加分）- 主动展示理解：**
- 用自己的话正确解释概念 → +8~+12
- 举一反三、给出正确示例 → +10~+15
- 正确回答问题或解决问题 → +8~+12

**B类（加分）- 接受性理解：**
- AI教学后学生表示理解（如"懂了"、"明白了"、"原来如此"） → +5~+8
- 学生对AI的解释做出有内容的确认 → +5~+7

**C类（加分）- 被动学习：**
- AI对某知识点进行了教学/解释，学生没有表示不懂或困惑 → +5
- 只要AI讲解了且学生未反驳、未表示困惑，即视为学习有效

**D类（减分）- 暴露理解错误：**
- 给出错误解释 → -3~-7
- AI纠正后仍困惑 → -5

## 规则

1. 掌握分范围 0-100，单次调整不超过 ±15
2. 节点名称必须与知识图谱完全匹配
3. 未开始(0分)的节点，学生展示理解可设 20-40
4. 必须使用 update_mastery 工具更新
5. 无 A/B/C 类证据则回复"无需更新"
6. 积极评估：只要学生参与了相关知识点的学习且没有表现出困惑，就倾向于给予适度加分"""


def format_conversation_for_evaluation(conversation: list[dict]) -> str:
    """Format conversation messages for evaluation prompt.

    Args:
        conversation: List of message dicts with 'role' and 'content'

    Returns:
        Formatted conversation string
    """
    lines = ["以下是学生与AI的对话内容：", ""]
    for msg in conversation:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            content = "\n".join(text_parts)
        if not content:
            continue
        if role == "user":
            lines.append(f"学生：{content}")
        elif role == "assistant":
            lines.append(f"AI：{content}")
        lines.append("")
    return "\n".join(lines)
