"""Quota checking functions."""

import logging
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Conversation,
    Message,
    MessageRole,
    Space,
    SpaceDocument,
    SubscriptionTier,
    User,
)
from quota.config import TierLimits, get_tier_limits
from quota.exceptions import (
    DailyMessageQuotaExceeded,
    ModelNotAllowedForTier,
    SpaceCountQuotaExceeded,
    StorageQuotaExceeded,
)


def get_effective_tier(user: User) -> SubscriptionTier:
    """Resolve the user's effective subscription tier.

    Expired paid subscriptions are downgraded to FREE at query time.
    """
    tier = user.subscription_tier
    if tier == SubscriptionTier.FREE:
        return tier

    expires_at = user.subscription_expires_at
    if expires_at is None:
        # No expiry set — treat as active (e.g. ALPHA lifetime users)
        return tier

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        return SubscriptionTier.FREE

    return tier


def get_user_tier_limits(user: User) -> TierLimits:
    """Get effective tier limits, accounting for expiration."""
    return get_tier_limits(get_effective_tier(user))


async def get_daily_message_count(db: AsyncSession, user_id: UUID) -> int:
    """Count user messages sent today (UTC)."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    result = await db.execute(
        select(func.count())
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == user_id,
            Message.role == MessageRole.USER,
            Message.created_at >= today_start,
        )
    )
    return result.scalar_one()


async def check_daily_message_quota(db: AsyncSession, user: User) -> None:
    """Raise DailyMessageQuotaExceeded if the user's daily limit is reached."""
    limits = get_user_tier_limits(user)
    if limits.daily_messages is None:
        return  # unlimited

    used = await get_daily_message_count(db, user.id)
    if used >= limits.daily_messages:
        tier = get_effective_tier(user)
        logger.info("Daily message quota exceeded: user=%s tier=%s used=%d limit=%d", user.id, tier.value, used, limits.daily_messages)
        raise DailyMessageQuotaExceeded(
            used=used,
            limit=limits.daily_messages,
            tier=tier.value,
        )


async def get_space_count(db: AsyncSession, user_id: UUID) -> int:
    """Count user's learning spaces."""
    result = await db.execute(
        select(func.count()).select_from(Space).where(Space.user_id == user_id)
    )
    return result.scalar_one()


async def check_space_count_quota(db: AsyncSession, user: User) -> None:
    """Raise SpaceCountQuotaExceeded if the user's space limit is reached."""
    limits = get_user_tier_limits(user)
    if limits.max_spaces is None:
        return  # unlimited

    used = await get_space_count(db, user.id)
    if used >= limits.max_spaces:
        tier = get_effective_tier(user)
        logger.info("Space count quota exceeded: user=%s tier=%s used=%d limit=%d", user.id, tier.value, used, limits.max_spaces)
        raise SpaceCountQuotaExceeded(
            used=used,
            limit=limits.max_spaces,
            tier=tier.value,
        )


def check_model_access(user: User, model_id: str | None) -> None:
    """Raise ModelNotAllowedForTier if the user cannot use the requested model.

    Skips check when model_id is None (will use default).
    """
    if model_id is None:
        return

    limits = get_user_tier_limits(user)
    if model_id not in limits.allowed_model_ids:
        tier = get_effective_tier(user)
        raise ModelNotAllowedForTier(
            model_id=model_id,
            tier=tier.value,
            allowed_models=list(limits.allowed_model_ids),
        )


async def get_space_storage_used(db: AsyncSession, space_id: UUID) -> int:
    """Sum file_size of all documents in a space."""
    result = await db.execute(
        select(func.coalesce(func.sum(SpaceDocument.file_size), 0)).where(
            SpaceDocument.space_id == space_id
        )
    )
    return result.scalar_one()


async def check_storage_quota(
    db: AsyncSession,
    user: User,
    space_id: UUID,
    new_file_size: int,
) -> None:
    """Raise StorageQuotaExceeded if adding new_file_size exceeds the limit."""
    limits = get_user_tier_limits(user)
    used = await get_space_storage_used(db, space_id)
    if used + new_file_size > limits.storage_per_space_bytes:
        tier = get_effective_tier(user)
        raise StorageQuotaExceeded(
            used_bytes=used,
            limit_bytes=limits.storage_per_space_bytes,
            tier=tier.value,
            new_file_bytes=new_file_size,
        )
