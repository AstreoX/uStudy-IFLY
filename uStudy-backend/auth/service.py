"""Auth 业务逻辑"""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.apple import get_or_create_apple_user, verify_apple_token
from auth.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenInvalidError,
)
from auth.schemas import (
    AppleLoginRequest,
    LoginRequest,
    RegisterWithCodeRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    ResetPasswordRequest,
)
from auth.security import check_login_allowed, clear_login_failures, record_login_failure
from auth.verification import verify_verification_token
from config import get_settings
from core.jwt import (
    create_access_token,
    create_refresh_token,
    revoke_all_user_tokens,
    rotate_refresh_token,
)
from core.security import hash_password, verify_password
from db.models import SubscriptionTier, User, VerificationCodePurpose
from experiment.default_course import ensure_default_space_membership


def _registration_tier() -> SubscriptionTier:
    """Public signups receive full, non-expiring access in the experiment app."""
    if get_settings().app_env == "experiment":
        return SubscriptionTier.ALPHA
    return SubscriptionTier.FREE


async def _apply_optional_registration_benefits(
    db: AsyncSession,
    user: User,
    *,
    invite_code: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Attach a newly registered user to the fixed experiment course."""
    await ensure_default_space_membership(db, user.id)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    通过邮箱查找用户

    Args:
        db: 数据库 session
        email: 用户邮箱

    Returns:
        User 对象或 None
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    """Look up an account by case-insensitive username or email address."""
    normalized = identifier.strip().lower()
    result = await db.execute(
        select(User)
        .where(
            or_(
                func.lower(User.username) == normalized,
                func.lower(User.email) == normalized,
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """
    通过 ID 查找用户

    Args:
        db: 数据库 session
        user_id: 用户 ID

    Returns:
        User 对象或 None
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register(
    db: AsyncSession,
    request: RegisterRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    """
    邮箱注册

    Args:
        db: 数据库 session
        request: 注册请求

    Returns:
        创建的 User 对象

    Raises:
        EmailAlreadyExistsError: 邮箱已存在
    """
    # 检查邮箱是否已存在
    existing_user = await get_user_by_email(db, request.email)
    if existing_user:
        raise EmailAlreadyExistsError(request.email)

    # 创建用户
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        nickname=request.nickname,
        subscription_tier=_registration_tier(),
        subscription_expires_at=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await _apply_optional_registration_benefits(
        db,
        user,
        invite_code=request.invite_code,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    await db.refresh(user)

    return user


async def login(db: AsyncSession, request: LoginRequest) -> TokenResponse:
    """
    账号名或邮箱登录

    Args:
        db: 数据库 session
        request: 登录请求

    Returns:
        TokenResponse 包含 access 和 refresh token

    Raises:
        InvalidCredentialsError: 账号或密码错误
    """
    identifier = request.identifier.strip().lower()
    await check_login_allowed(identifier)

    # 查找用户
    user = await get_user_by_identifier(db, identifier)
    if not user:
        await record_login_failure(identifier)
        raise InvalidCredentialsError()

    # 检查密码（Apple 用户无密码）
    if not user.password_hash:
        await record_login_failure(identifier)
        raise InvalidCredentialsError()

    if not verify_password(request.password, user.password_hash):
        await record_login_failure(identifier)
        raise InvalidCredentialsError()

    await clear_login_failures(identifier)
    await ensure_default_space_membership(db, user.id)
    await db.commit()

    # 生成 token
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=await create_refresh_token(user.id, db),
    )


async def apple_login(
    db: AsyncSession,
    request: AppleLoginRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TokenResponse:
    """
    Apple 登录

    Args:
        db: 数据库 session
        request: Apple 登录请求

    Returns:
        TokenResponse 包含 access 和 refresh token
    """
    payload = await verify_apple_token(request.id_token)
    user = await get_or_create_apple_user(
        db,
        apple_id=payload.apple_id,
        email=payload.email,
        email_verified=payload.email_verified,
        invite_code=request.invite_code,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=await create_refresh_token(user.id, db),
    )


async def register_with_code(
    db: AsyncSession,
    request: RegisterWithCodeRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TokenResponse:
    payload = verify_verification_token(
        request.verification_token, VerificationCodePurpose.REGISTRATION
    )
    if payload.get("email") != request.email:
        raise TokenInvalidError("Token email mismatch")

    existing_user = await get_user_by_email(db, request.email)
    if existing_user:
        raise EmailAlreadyExistsError(request.email)

    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        nickname=request.nickname,
        subscription_tier=_registration_tier(),
        subscription_expires_at=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await _apply_optional_registration_benefits(
        db,
        user,
        invite_code=request.invite_code,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=await create_refresh_token(user.id, db),
    )


async def reset_password(
    db: AsyncSession, request: ResetPasswordRequest
) -> None:
    payload = verify_verification_token(
        request.verification_token, VerificationCodePurpose.PASSWORD_RESET
    )
    if payload.get("email") != request.email:
        raise TokenInvalidError("Token email mismatch")

    user = await get_user_by_email(db, request.email)
    if not user:
        # 保护隐私，不透露邮箱是否存在
        return

    user.password_hash = hash_password(request.new_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await revoke_all_user_tokens(user.id, db)


async def update_nickname(db: AsyncSession, user: User, nickname: str) -> User:
    """
    更新用户昵称

    Args:
        db: 数据库 session
        user: 当前用户
        nickname: 新昵称

    Returns:
        更新后的 User 对象
    """
    user.nickname = nickname
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def refresh_token(db: AsyncSession, request: RefreshRequest) -> TokenResponse:
    """
    刷新 Token

    Args:
        db: 数据库 session
        request: 刷新请求

    Returns:
        TokenResponse 包含新的 access 和 refresh token

    Raises:
        InvalidTokenError: token 无效或用户不存在
    """
    try:
        access, refresh = await rotate_refresh_token(request.refresh_token, db)
    except InvalidTokenError:
        raise

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
    )
