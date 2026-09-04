"""简答题评估器"""

import logging
import re
from dataclasses import dataclass

from agents.llm import LLMClient
from agents.llm.evaluation_prompts import build_short_answer_evaluation_prompt
from config import get_settings
from usage.metering import UsageContext
from usage.models import UsageType

logger = logging.getLogger(__name__)


@dataclass
class ShortAnswerEvaluationResult:
    """简答题评估结果"""

    score: int  # 得分 (0-10)
    max_score: int  # 满分
    ai_evaluation: str  # AI 评估完整文本


def extract_score_from_evaluation(ai_response: str | None, max_score: int = 10) -> int:
    """
    从 AI 响应中提取分数

    Args:
        ai_response: AI 返回的完整评估文本
        max_score: 该题满分（默认 10）

    Returns:
        提取的分数（0 到 max_score 之间的整数）
    """
    if not ai_response:
        return 0

    # 匹配 {数字} 格式，取最后一个匹配（即最终得分）
    matches = re.findall(r"\{(\d+)\}", ai_response)
    if matches:
        score = int(matches[-1])
        return min(max(score, 0), max_score)  # 确保在有效范围内
    return 0  # 解析失败默认 0 分


async def evaluate_short_answer(
    question_stem: str,
    reference_answer: str,
    user_answer: str,
    max_score: int = 10,
    user_id=None,
    space_id=None,
) -> ShortAnswerEvaluationResult:
    """
    评估单道简答题

    Args:
        question_stem: 题干
        reference_answer: 参考答案
        user_answer: 用户答案
        max_score: 满分（默认 10）

    Returns:
        ShortAnswerEvaluationResult 包含得分和 AI 评估文本
    """
    # 1. 构建 Prompt
    messages = build_short_answer_evaluation_prompt(
        question_stem=question_stem,
        reference_answer=reference_answer,
        user_answer=user_answer,
        max_score=max_score,
    )

    # 2. 调用 OpenRouter LLM API。
    # 评估固定使用 quiz_evaluation_model，避免落到全局默认对话模型。
    client = LLMClient(
        model_override=get_settings().quiz_evaluation_model or None,
        usage_context=UsageContext(
            user_id=user_id,
            usage_type=UsageType.AGENT_LLM,
            source_module="quiz",
            source_operation="short_answer_evaluation",
            billable=bool(user_id),
            space_id=space_id,
        ),
    )
    try:
        ai_response = await client.complete(
            messages=messages,
            temperature=0.3,  # 评估任务用较低温度，保证一致性
            max_tokens=1024,
        )
    except Exception as exc:
        logger.warning("Short answer evaluation failed: %s", exc, exc_info=True)
        ai_response = None

    if not ai_response:
        logger.warning("Short answer evaluation returned empty content")
        ai_response = "AI 评分服务暂时不可用，未返回有效评语。该题暂按 0 分处理，请稍后重试。"

    # 3. 提取分数
    score = extract_score_from_evaluation(ai_response, max_score)

    # 4. 返回结果
    return ShortAnswerEvaluationResult(
        score=score,
        max_score=max_score,
        ai_evaluation=ai_response,
    )
