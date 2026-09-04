"""Apple Sign-In 验证模块"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from jose import JWTError, jwk, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.exceptions import AppleAuthError
from config import get_settings
from db.models import User

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
DEFAULT_JWKS_TTL_SECONDS = 24 * 60 * 60

_JWKS_CACHE: dict[str, Any] = {"jwks": None, "expires_at": None}
_JWKS_LOCK = asyncio.Lock()


@dataclass
class AppleTokenPayload:
    """Apple Token 解析后的 payload"""

    apple_id: str  # sub claim
    email: str | None  # 可能为 None（用户选择隐藏邮箱）
    email_verified: bool


def _parse_cache_control_max_age(cache_control: str | None) -> int | None:
    if not cache_control:
        return None
    match = re.search(r"max-age=(\d+)", cache_control)
    if not match:
        return None
    return int(match.group(1))


def _cache_expired() -> bool:
    expires_at = _JWKS_CACHE.get("expires_at")
    if not expires_at:
        return True
    return datetime.now(timezone.utc) >= expires_at


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    if isinstance(value, int):
        return value == 1
    return False


def _parse_audiences(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_nickname(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    if not local:
        return "Apple User"
    return local[:100]


async def _fetch_apple_jwks() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(APPLE_JWKS_URL)
        response.raise_for_status()
        data = response.json()

    max_age = _parse_cache_control_max_age(response.headers.get("Cache-Control"))
    ttl_seconds = max_age if max_age is not None else DEFAULT_JWKS_TTL_SECONDS

    _JWKS_CACHE["jwks"] = data
    _JWKS_CACHE["expires_at"] = datetime.now(timezone.utc) + timedelta(
        seconds=ttl_seconds
    )
    return data


async def get_apple_jwks() -> dict[str, Any]:
    """获取 Apple JWKS（带简单缓存）"""
    if not _cache_expired() and _JWKS_CACHE["jwks"]:
        return _JWKS_CACHE["jwks"]

    async with _JWKS_LOCK:
        if not _cache_expired() and _JWKS_CACHE["jwks"]:
            return _JWKS_CACHE["jwks"]
        try:
            return await _fetch_apple_jwks()
        except httpx.HTTPError as exc:
            if _JWKS_CACHE["jwks"]:
                return _JWKS_CACHE["jwks"]
            raise AppleAuthError("Failed to fetch Apple public keys") from exc


async def verify_apple_token(id_token: str) -> AppleTokenPayload:
    """
    验证 Apple id_token

    真实流程：
    1. 获取 Apple 公钥（JWKS）
    2. 校验 JWT 签名、aud、iss、exp
    3. 提取 sub (apple_id) 和 email
    """
    settings = get_settings()
    audiences = _parse_audiences(settings.apple_client_id)
    if not audiences:
        raise AppleAuthError("APPLE_CLIENT_ID not configured")

    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise AppleAuthError("Invalid Apple token header") from exc

    kid = unverified_header.get("kid")
    alg = unverified_header.get("alg")
    if not kid or alg != "RS256":
        raise AppleAuthError("Invalid Apple token header")

    jwks = await get_apple_jwks()
    key_dict = next(
        (key for key in jwks.get("keys", []) if key.get("kid") == kid), None
    )
    if not key_dict:
        raise AppleAuthError("Apple public key not found")

    try:
        public_key = jwk.construct(key_dict)
        payload = jwt.decode(
            id_token,
            public_key.to_pem(),
            algorithms=["RS256"],
            audience=audiences if len(audiences) > 1 else audiences[0],
            issuer=APPLE_ISSUER,
        )
    except JWTError as exc:
        raise AppleAuthError("Invalid Apple token") from exc

    apple_id = payload.get("sub")
    if not apple_id:
        raise AppleAuthError("Apple token missing sub")

    email = payload.get("email")
    email_verified = _coerce_bool(payload.get("email_verified"))

    return AppleTokenPayload(
        apple_id=str(apple_id),
        email=email,
        email_verified=email_verified,
    )


async def get_or_create_apple_user(
    db: AsyncSession,
    apple_id: str,
    email: str | None,
    email_verified: bool | None = None,
    invite_code: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    """
    查找或创建 Apple 用户

    优先使用 apple_id 查找；若不存在则使用 email 关联已有账号或创建新用户。
    """
    if not apple_id:
        raise AppleAuthError("Apple ID missing")

    result = await db.execute(select(User).where(User.apple_id == apple_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    if not email:
        raise AppleAuthError("Apple token missing email for new user")

    if email_verified is False:
        raise AppleAuthError("Apple email not verified")

    # 若邮箱已存在，则绑定到该账户
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.apple_id and existing.apple_id != apple_id:
            raise AppleAuthError("Email already linked to another Apple ID")
        if not existing.apple_id:
            existing.apple_id = apple_id
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
        return existing

    nickname = _default_nickname(email)
    user = User(
        email=email,
        apple_id=apple_id,
        nickname=nickname,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppleAuthError("Email already registered") from exc

    await db.refresh(user)
    await db.commit()
    await db.refresh(user)

    return user
