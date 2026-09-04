"""Shared provider-neutral driver for one streamed tool-capable LLM turn.

Provider SSE parsing belongs exclusively to :class:`LLMClient`.  Consumers such as
the normal chat orchestrator and the presentation capability gateway use this small
adapter so they observe the exact same event contract.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from agents.llm.client import LLMClient
from usage.metering import UsageContext


async def stream_tool_completion(
    client: LLMClient,
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 65536,
    enable_thinking: bool | None = None,
    usage_context: UsageContext | None = None,
    idempotency_key: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Yield the canonical thinking/content/tool/done event stream.

    This deliberately performs no provider parsing or buffering.  In particular,
    Qwen ``reasoning_content`` is already normalized to ``thinking`` by LLMClient.
    """

    async for event in client.stream_complete_with_tools(
        messages=messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
        usage_context=usage_context,
        idempotency_key=idempotency_key,
    ):
        yield event
