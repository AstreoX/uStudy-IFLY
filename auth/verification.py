"""验证码业务逻辑"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.email_service import EmailProvider
from auth.exceptions import (
    CodeExpiredError,
    InvalidCodeError,
    RateLimitError,
    TokenExpiredError,
    TokenInvalidError,
    TooManyAttemptsError,
)
from config import get_settings
from db.models import VerificationCode, VerificationCodePurpose

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_code() -> str:
    length = settings.verification_code_length
    return ''.join(random.choices('0123456789', k=length))


async def send_verification_code(
    db: AsyncSession,
    email: str,
    purpose: VerificationCodePurpose,
    email_provider: EmailProvider,
) -> bool:
    """发送验证码"""
    cutoff = _now() - timedelta(seconds=settings.verification_code_rate_limit_seconds)
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.created_at > cutoff,
        )
        .order_by(VerificationCode.created_at.desc())
    )
    if result.scalar_one_or_none():
        raise RateLimitError("请60秒后再试")

    # 使旧验证码失效
    await db.execute(
        update(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
        )
        .values(is_used=True)
    )

    code = _generate_code()
    verification = VerificationCode(
        email=email,
        code=code,
        purpose=purpose,
        expires_at=_now() + timedelta(minutes=settings.verification_code_expire_minutes),
    )
    db.add(verification)
    await db.commit()

    await email_provider.send_verification_email(email, code)
    return True


async def verify_code(
    db: AsyncSession,
    email: str,
    code: str,
    purpose: VerificationCodePurpose,
) -> str:
    """验证验证码并返回 verification_token"""
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.is_used.is_(False),
            VerificationCode.expires_at > _now(),
        )
        .order_by(VerificationCode.created_at.desc())
    )
    verification = result.scalar_one_or_none()

    if not verification:
        raise CodeExpiredError("验证码已过期或不存在")

    if verification.attempts >= settings.verification_code_max_attempts:
        raise TooManyAttemptsError("尝试次数过多，请重新获取验证码")

    if verification.code != code:
        verification.attempts += 1
        await db.commit()
        remaining = settings.verification_code_max_attempts - verification.attempts
        raise InvalidCodeError(f"验证码错误，还剩 {remaining} 次机会")

    verification.is_used = True
    await db.commit()

    return create_verification_token(email, purpose)


def create_verification_token(
    email: str,
    purpose: VerificationCodePurpose,
) -> str:
    payload = {
        "email": email,
        "purpose": purpose.value,
        "exp": _now() + timedelta(minutes=settings.verification_token_expire_minutes),
        "jti": str(uuid4()),
        "iat": _now(),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_verification_token(token: str, expected_purpose: VerificationCodePurpose) -> dict:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("验证链接已过期，请重新获取验证码") from exc
    except JWTError as exc:
        raise TokenInvalidError("无效的验证链接") from exc

    if payload.get("purpose") != expected_purpose.value:
        raise TokenInvalidError("Token purpose mismatch")

    return payload
