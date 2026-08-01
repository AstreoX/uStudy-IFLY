"""Activation code business logic."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ActivationCode, SubscriptionTier, User
from quota.service import get_effective_tier

from .exceptions import CodeAlreadyUsedError, InvalidCodeError, TierDowngradeError

# Tier rank for upgrade/downgrade comparison
_TIER_RANK = {
    SubscriptionTier.FREE: 0,
    SubscriptionTier.BASIC: 1,
    SubscriptionTier.PREMIUM: 2,
    SubscriptionTier.ALPHA: 3,
    SubscriptionTier.ULTRA: 3,
}


async def activate_code(
    db: AsyncSession,
    user_id: UUID,
    code: str,
) -> User:
    """
    验证并使用激活码，支持多等级激活。

    Args:
        db: 数据库会话
        user_id: 用户 ID
        code: 激活码

    Returns:
        更新后的用户对象

    Raises:
        InvalidCodeError: 激活码不存在
        CodeAlreadyUsedError: 激活码已被使用
        TierDowngradeError: 激活码等级低于当前订阅等级
    """
    # 1. 查找激活码
    code_upper = code.upper().strip()
    result = await db.execute(
        select(ActivationCode).where(ActivationCode.code == code_upper)
    )
    activation_code = result.scalar_one_or_none()

    if not activation_code:
        raise InvalidCodeError()

    # 2. 检查是否已被使用
    if activation_code.used_by is not None:
        raise CodeAlreadyUsedError()

    # 3. 获取用户并检查当前等级
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise InvalidCodeError("用户不存在")

    # 4. 比较等级
    effective_tier = get_effective_tier(user)
    target_rank = _TIER_RANK.get(activation_code.target_tier, 0)
    current_rank = _TIER_RANK.get(effective_tier, 0)

    if target_rank < current_rank:
        raise TierDowngradeError()

    # 5. 计算过期时间
    now = datetime.now(timezone.utc)

    if (
        target_rank == current_rank
        and user.subscription_expires_at is not None
        and user.subscription_expires_at > now
    ):
        # 同等级且未过期：从当前到期时间延长
        base = user.subscription_expires_at
    else:
        # 升级或无有效订阅：从现在开始
        base = now

    expires_at = base + timedelta(days=activation_code.validity_days)

    # 6. 更新用户等级
    user.subscription_tier = activation_code.target_tier
    user.subscription_expires_at = expires_at

    # 7. 标记激活码为已使用
    activation_code.used_by = user_id
    activation_code.used_at = now

    await db.commit()
    await db.refresh(user)

    return user
