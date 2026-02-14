"""Auth 依赖注入"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.service import get_user_by_id
from core.jwt import decode_token
from db.database import get_db
from db.models import SubscriptionTier, User

logger = logging.getLogger(__name__)

# HTTP Bearer token 提取
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI 依赖：从 Authorization header 提取并验证用户

    Usage:
        @app.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return user

    Raises:
        HTTPException 401: token 无效或用户不存在
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "身份验证失败"},
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        logger.warning("Auth failed: No credentials provided")
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials)
    except JWTError as e:
        logger.warning(f"Auth failed: JWT decode error - {e}")
        raise credentials_exception

    # 验证 token 类型
    if payload.get("type") != "access":
        logger.warning(f"Auth failed: Wrong token type - {payload.get('type')}")
        raise credentials_exception

    # 获取用户 ID
    user_id = payload.get("sub")
    if not user_id:
        logger.warning("Auth failed: No user_id in token")
        raise credentials_exception

    # 查找用户
    user = await get_user_by_id(db, UUID(user_id))
    if not user:
        logger.warning(f"Auth failed: User not found - {user_id}")
        raise credentials_exception

    return user


async def require_active_subscription(
    user: User = Depends(get_current_user),
) -> User:
    """要求用户拥有有效订阅（非 FREE 且未过期）"""
    if user.subscription_tier == SubscriptionTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SUBSCRIPTION_REQUIRED",
                "message": "此功能需要激活订阅，请使用激活码升级账户",
            },
        )
    if (
        user.subscription_expires_at is not None
        and user.subscription_expires_at < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SUBSCRIPTION_EXPIRED",
                "message": "订阅已过期，请重新激活",
            },
        )
    return user


# 类型别名，方便在路由中使用
CurrentUser = Annotated[User, Depends(get_current_user)]
