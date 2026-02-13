"""Async usage recorder for fire-and-forget API usage tracking."""

import asyncio
import logging
from uuid import UUID

from db.database import get_scoped_session
from usage.models import ApiUsageLog, UsageType

logger = logging.getLogger(__name__)

# Maintain references to background tasks to prevent garbage collection
_background_tasks: set[asyncio.Task] = set()

# Model pricing (input, output) per 1M tokens in USD
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-chat": (0.14, 0.28),
    "google/gemini-flash-1.5": (0.075, 0.30),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "google/gemini-3-flash-preview": (0.10, 0.40),
    "openai/text-embedding-3-small": (0.02, 0),
    "openai/text-embedding-3-large": (0.13, 0),
}

DEFAULT_PRICING: tuple[float, float] = (0.10, 0.30)


def _estimate_cost_cents(model: str, prompt_tokens: int, completion_tokens: int) -> int:
    """Estimate cost in cents based on model pricing."""
    rates = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_cost = (prompt_tokens / 1_000_000) * rates[0] * 100
    output_cost = (completion_tokens / 1_000_000) * rates[1] * 100
    return round(input_cost + output_cost)


async def record_usage_async(
    user_id: UUID,
    usage_type: UsageType,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    space_id: UUID | None = None,
    conversation_id: UUID | None = None,
    request_metadata: dict | None = None,
) -> None:
    """
    Async record API usage (fire-and-forget).

    Does not block main flow. Logs error on failure.
    Uses get_scoped_session() for short-lived DB connection.
    """
    try:
        async with get_scoped_session() as db:
            log = ApiUsageLog(
                user_id=user_id,
                space_id=space_id,
                conversation_id=conversation_id,
                usage_type=usage_type,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                estimated_cost_cents=_estimate_cost_cents(
                    model, prompt_tokens, completion_tokens
                ),
                request_metadata=request_metadata,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to record usage: {e}", exc_info=True)


def schedule_usage_recording(
    user_id: UUID,
    usage_type: UsageType,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    space_id: UUID | None = None,
    conversation_id: UUID | None = None,
    request_metadata: dict | None = None,
) -> None:
    """
    Schedule async usage recording (does not block current coroutine).

    This is a fire-and-forget function. The usage will be recorded
    in the background without blocking the main request flow.

    Task references are kept in _background_tasks to prevent GC.
    """
    task = asyncio.create_task(
        record_usage_async(
            user_id=user_id,
            usage_type=usage_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            space_id=space_id,
            conversation_id=conversation_id,
            request_metadata=request_metadata,
        )
    )
    # Keep reference to prevent garbage collection
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
