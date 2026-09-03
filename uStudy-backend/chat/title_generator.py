"""Auto-generate conversation titles using a lightweight LLM."""

import logging
import re

from agents.llm.client import LLMClient
from config import get_settings
from usage.metering import UsageContext
from usage.models import UsageType

logger = logging.getLogger(__name__)

_TITLE_SYSTEM_PROMPT = (
    "根据以下用户消息，生成一个简洁的对话标题（不超过20个字）。"
    "只输出标题文本，不要加引号或其他标点包裹。"
)


async def generate_title(
    user_message: str,
    *,
    user_id=None,
    conversation_id=None,
) -> str:
    """Call a lightweight LLM to generate a concise conversation title.

    Uses a single httpx POST with a short timeout. No retries — title
    generation is non-critical and should never block the main response.

    Args:
        user_message: The user's first message in the conversation.

    Returns:
        A cleaned title string (max 200 chars).

    Raises:
        Exception: Any network/API error (caller should catch and fallback).
    """
    settings = get_settings()
    truncated_message = user_message[:500]

    logger.info(f"[TitleGen] Calling model={settings.title_generation_model}, input={truncated_message[:60]!r}")

    client = LLMClient(
        model_override=settings.title_generation_model,
        timeout_seconds=settings.title_generation_timeout,
        usage_context=UsageContext(
            user_id=user_id,
            usage_type=UsageType.CHAT_LLM,
            source_module="chat",
            source_operation="title_generation",
            billable=bool(user_id),
            conversation_id=conversation_id,
        ),
    )
    result = await client.complete_result(
        messages=[
            {"role": "system", "content": _TITLE_SYSTEM_PROMPT},
            {"role": "user", "content": truncated_message},
        ],
        temperature=0.3,
        max_tokens=256,
        enable_thinking=False,
        idempotency_key=(
            f"title_generation:{conversation_id}" if conversation_id else None
        )
    )
    raw_title = result.content.strip()

    # 某些 reasoning 模型可能将内容放在 reasoning_content 字段
    if not raw_title:
        raise ValueError("Title generation returned empty content")

    logger.info(f"[TitleGen] Raw response: {raw_title!r}")

    # Remove <think>...</think> blocks first (some models include reasoning)
    cleaned = re.sub(r"<think>.*?</think>", "", raw_title, flags=re.DOTALL).strip()
    # Strip surrounding quotes / brackets / whitespace
    cleaned = re.sub(r'^["\'""\u300c\u300e]+|["\'""\u300d\u300f]+$', "", cleaned).strip()

    if cleaned:
        logger.info(f"[TitleGen] Generated title: {cleaned[:50]!r}")
        return cleaned[:200]
    else:
        logger.warning(f"[TitleGen] Empty after cleaning, falling back to user message")
        return fallback_title(user_message)


def fallback_title(user_message: str, max_length: int = 50) -> str:
    """Truncate the user's first message as a fallback title.

    Args:
        user_message: The user's first message.
        max_length: Maximum title length.

    Returns:
        Truncated string, with "..." appended if it was cut.
    """
    text = user_message.strip().replace("\n", " ")
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
