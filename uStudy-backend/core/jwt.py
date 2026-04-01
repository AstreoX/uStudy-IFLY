"""JWT Token 工具模块"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
    TokenReuseError,
)
from config import get_settings
from db.models import RefreshToken

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    创建 Access Token

    Args:
        subject: 通常是 user_id
        expires_delta: 自定义过期时间，默认使用配置值

    Returns:
        JWT token 字符串
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


async def create_refresh_token(
    user_id: UUID,
    db: AsyncSession,
    device_info: str | None = None,
) -> str:
    """
    创建 Refresh Token（存储哈希，支持轮换）

    Args:
        user_id: 用户 ID
        db: 数据库 session
        device_info: 可选设备信息

    Returns:
        Refresh token 字符串（明文）
    """
    await _enforce_device_limit(user_id, db)
    token, refresh_obj = await _create_refresh_token_record(
        user_id=user_id,
        db=db,
        device_info=device_info,
    )
    await db.commit()
    return token


async def _create_refresh_token_record(
    user_id: UUID,
    db: AsyncSession,
    device_info: str | None = None,
    family_id: UUID | None = None,
) -> tuple[str, RefreshToken]:
    token = f"{uuid4()}{secrets.token_urlsafe(32)}"
    token_hash = _hash_token(token)
    refresh_obj = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        device_info=device_info,
        expires_at=_now() + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_obj)
    await db.flush()
    # For new logins (family_id=None), use the token's own id as family root
    refresh_obj.family_id = family_id or refresh_obj.id
    await db.flush()
    return token, refresh_obj


async def rotate_refresh_token(
    old_token: str,
    db: AsyncSession,
) -> tuple[str, str]:
    """
    轮换 refresh token，返回新的 access_token 和 refresh_token
    """
    old_hash = _hash_token(old_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == old_hash)
    )
    old_refresh = result.scalar_one_or_none()

    if not old_refresh:
        raise InvalidTokenError("无效的 refresh token")

    if old_refresh.revoked_at is not None:
        # Family-scoped revocation: only kill the affected device's session
        if old_refresh.family_id is not None:
            await _revoke_token_family(old_refresh.family_id, db)
        else:
            # Legacy token without family_id — fall back to revoking all
            await revoke_all_user_tokens(old_refresh.user_id, db)
        raise TokenReuseError("检测到 token 重复使用，已撤销该设备会话，请重新登录")

    if _normalize_datetime(old_refresh.expires_at) < _now():
        raise TokenExpiredError("登录已过期，请重新登录")

    old_refresh.revoked_at = _now()

    new_token, new_refresh = await _create_refresh_token_record(
        user_id=old_refresh.user_id,
        db=db,
        device_info=old_refresh.device_info,
        family_id=old_refresh.family_id,
    )
    old_refresh.replaced_by = new_refresh.id

    access_token = create_access_token(str(old_refresh.user_id))
    await db.commit()
    return access_token, new_token


async def _revoke_token_family(family_id: UUID, db: AsyncSession) -> None:
    """Revoke all tokens in a token family (single device session)."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


async def _enforce_device_limit(user_id: UUID, db: AsyncSession) -> None:
    """Evict oldest device sessions if user exceeds max_concurrent_devices."""
    max_devices = settings.max_concurrent_devices

    # Get distinct active families ordered by most recent token creation
    result = await db.execute(
        select(
            RefreshToken.family_id,
            func.max(RefreshToken.created_at).label("latest"),
        )
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > _now(),
            RefreshToken.family_id.is_not(None),
        )
        .group_by(RefreshToken.family_id)
        .order_by(func.max(RefreshToken.created_at).desc())
    )
    families = result.all()

    # Keep (max_devices - 1) to make room for the new login
    if len(families) >= max_devices:
        families_to_revoke = families[max_devices - 1 :]
        for family_row in families_to_revoke:
            await _revoke_token_family(family_row.family_id, db)


async def revoke_all_user_tokens(user_id: UUID, db: AsyncSession) -> None:
    """撤销用户所有 refresh token"""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    await db.commit()


def decode_token(token: str) -> dict[str, Any]:
    """
    解码并验证 JWT Token

    Args:
        token: JWT token 字符串

    Returns:
        Token payload 字典

    Raises:
        JWTError: token 无效或已过期
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
