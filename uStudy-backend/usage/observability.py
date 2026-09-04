"""Durable AI provider request observability helpers."""

from __future__ import annotations

import logging
from typing import Any

from db.database import get_scoped_session
from usage.metering import UsageContext
from usage.models import AiRequestLog

logger = logging.getLogger(__name__)


def _usage_int(usage: Any, key: str) -> int | None:
    if not usage:
        return None
    if isinstance(usage, dict):
        value = usage.get(key)
    else:
        value = getattr(usage, key, None)
    return int(value) if value is not None else None


async def record_ai_request_log(
    *,
    model: str,
    request_kind: str,
    status: str,
    latency_ms: int | None,
    base_url: str | None = None,
    usage_context: UsageContext | None = None,
    usage: Any = None,
    error: BaseException | None = None,
    http_status_code: int | None = None,
    ttft_ms: int | None = None,
    last_chunk_gap_ms: int | None = None,
    retry_count: int = 0,
    retry_reason: str | None = None,
    message_count: int | None = None,
    context_chars: int | None = None,
    tool_result_chars: int | None = None,
    source_module: str | None = None,
    source_operation: str | None = None,
) -> None:
    """Persist one AI request log without affecting the caller on failure."""
    error_message = str(error) if error else None
    if error_message and len(error_message) > 2000:
        error_message = error_message[:2000]

    try:
        async with get_scoped_session() as db:
            db.add(
                AiRequestLog(
                    user_id=getattr(usage_context, "user_id", None),
                    space_id=getattr(usage_context, "space_id", None),
                    conversation_id=getattr(usage_context, "conversation_id", None),
                    model=model,
                    base_url=base_url,
                    request_kind=request_kind,
                    source_module=source_module
                    or getattr(usage_context, "source_module", None),
                    source_operation=source_operation
                    or getattr(usage_context, "source_operation", None),
                    status=status,
                    http_status_code=http_status_code,
                    error_type=type(error).__name__ if error else None,
                    error_message=error_message,
                    latency_ms=latency_ms,
                    ttft_ms=ttft_ms,
                    last_chunk_gap_ms=last_chunk_gap_ms,
                    retry_count=max(retry_count, 0),
                    retry_reason=retry_reason,
                    prompt_tokens=_usage_int(usage, "prompt_tokens"),
                    completion_tokens=_usage_int(usage, "completion_tokens"),
                    total_tokens=_usage_int(usage, "total_tokens"),
                    message_count=message_count,
                    context_chars=context_chars,
                    tool_result_chars=tool_result_chars,
                )
            )
            await db.commit()
    except Exception as log_error:
        logger.warning("AI request observability log write failed: %s", log_error)
