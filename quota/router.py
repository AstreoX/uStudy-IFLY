"""Quota API Router"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from quota.config import get_tier_limits
from quota.schemas import QuotaStatusResponse, QuotaUsage
from quota.service import (
    get_daily_message_count,
    get_effective_tier,
    get_space_count,
)

router = APIRouter(
    prefix="/api/quota",
    tags=["quota"],
)


@router.get(
    "/status",
    response_model=QuotaStatusResponse,
    summary="获取当前配额使用情况",
    description="返回用户各维度的配额用量（每日消息、空间数、模型、存储）",
)
async def get_quota_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotaStatusResponse:
    """Return current quota usage for the authenticated user."""
    tier = get_effective_tier(user)
    limits = get_tier_limits(tier)

    daily_used = await get_daily_message_count(db, user.id)
    space_used = await get_space_count(db, user.id)

    return QuotaStatusResponse(
        tier=tier.value,
        daily_messages=QuotaUsage(
            used=daily_used,
            limit=limits.daily_messages,
            remaining=(
                limits.daily_messages - daily_used
                if limits.daily_messages is not None
                else None
            ),
        ),
        space_count=QuotaUsage(
            used=space_used,
            limit=limits.max_spaces,
            remaining=(
                max(0, limits.max_spaces - space_used)
                if limits.max_spaces is not None
                else None
            ),
        ),
        allowed_models=list(limits.allowed_model_ids),
        storage_per_space_bytes=limits.storage_per_space_bytes,
    )
