"""Activation code business logic."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ActivationCode, SubscriptionTier, User

from .exceptions import CodeAlreadyUsedError, InvalidCodeError, UserAlreadyActivatedError


async def activate_code(
    db: AsyncSession,
    user_id: UUID,
    code: str,
) -> User:
    """
    验证并使用激活码。

    Args:
        db: 数据库会话
        user_id: 用户 ID
        code: 激活码

    Returns:
        更新后的用户对象

    Raises:
        InvalidCodeError: 激活码不存在
        CodeAlreadyUsedError: 激活码已被使用
        UserAlreadyActivatedError: 用户已经是 Alpha
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

    if user.subscription_tier == SubscriptionTier.ALPHA:
        raise UserAlreadyActivatedError()

    # 4. 计算过期时间（使用 naive datetime，与数据库字段一致）
    now = datetime.utcnow()
    expires_at = now + timedelta(days=activation_code.validity_days)

    # 5. 更新用户等级
    user.subscription_tier = SubscriptionTier.ALPHA
    user.subscription_expires_at = expires_at

    # 6. 标记激活码为已使用
    activation_code.used_by = user_id
    activation_code.used_at = now

    await db.commit()
    await db.refresh(user)

    return user
