"""Auth 业务逻辑"""

from uuid import UUID

from sqlalchemy import select
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
from core.jwt import (
    create_access_token,
    create_refresh_token,
    revoke_all_user_tokens,
    rotate_refresh_token,
)
from core.security import hash_password, verify_password
from db.models import User, VerificationCodePurpose


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


async def register(db: AsyncSession, request: RegisterRequest) -> User:
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
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def login(db: AsyncSession, request: LoginRequest) -> TokenResponse:
    """
    邮箱登录

    Args:
        db: 数据库 session
        request: 登录请求

    Returns:
        TokenResponse 包含 access 和 refresh token

    Raises:
        InvalidCredentialsError: 邮箱或密码错误
    """
    await check_login_allowed(request.email)

    # 查找用户
    user = await get_user_by_email(db, request.email)
    if not user:
        await record_login_failure(request.email)
        raise InvalidCredentialsError()

    # 检查密码（Apple 用户无密码）
    if not user.password_hash:
        await record_login_failure(request.email)
        raise InvalidCredentialsError()

    if not verify_password(request.password, user.password_hash):
        await record_login_failure(request.email)
        raise InvalidCredentialsError()

    await clear_login_failures(request.email)

    # 生成 token
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=await create_refresh_token(user.id, db),
    )


async def apple_login(db: AsyncSession, request: AppleLoginRequest) -> TokenResponse:
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
    )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=await create_refresh_token(user.id, db),
    )


async def register_with_code(
    db: AsyncSession, request: RegisterWithCodeRequest
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
    )
    db.add(user)
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
