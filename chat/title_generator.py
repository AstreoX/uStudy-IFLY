"""Auto-generate conversation titles using a lightweight LLM."""

import logging
import re

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

_TITLE_SYSTEM_PROMPT = (
    "根据以下用户消息，生成一个简洁的对话标题（不超过20个字）。"
    "只输出标题文本，不要加引号或其他标点包裹。"
)


async def generate_title(user_message: str) -> str:
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

    async with httpx.AsyncClient(timeout=settings.title_generation_timeout) as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.title_generation_model,
                "messages": [
                    {"role": "system", "content": _TITLE_SYSTEM_PROMPT},
                    {"role": "user", "content": truncated_message},
                ],
                "temperature": 0.3,
                "max_tokens": 50,
            },
        )
        response.raise_for_status()

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError(f"Unexpected API response: no choices")
    raw_title = choices[0].get("message", {}).get("content", "").strip()

    # Remove <think>...</think> blocks first (some models include reasoning)
    cleaned = re.sub(r"<think>.*?</think>", "", raw_title, flags=re.DOTALL).strip()
    # Strip surrounding quotes / brackets / whitespace
    cleaned = re.sub(r'^["\'""\u300c\u300e]+|["\'""\u300d\u300f]+$', "", cleaned).strip()

    return cleaned[:200] if cleaned else fallback_title(user_message)


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
