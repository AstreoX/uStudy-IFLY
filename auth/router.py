"""Auth 路由"""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from auth.exceptions import (
    AccountLockedError,
    AppleAuthError,
    CodeExpiredError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidCodeError,
    InvalidTokenError,
    RateLimitError,
    TokenExpiredError,
    TokenInvalidError,
    TokenReuseError,
    TooManyAttemptsError,
)
from auth.schemas import (
    AppleLoginRequest,
    LoginRequest,
    RegisterWithCodeRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendCodeRequest,
    TokenResponse,
    UserProfile,
    VerifyCodeRequest,
    VerifyCodeResponse,
)
from auth.email_service import get_email_provider
from auth.registration_notification import send_registration_notification
from auth.service import (
    apple_login,
    get_user_by_email,
    get_user_by_id,
    login,
    refresh_token,
    register,
    register_with_code,
    reset_password,
)
from auth.verification import send_verification_code, verify_code
from config import get_settings
from core.audit import log_auth_event
from core.jwt import create_access_token, create_refresh_token, decode_token
from db.database import get_db
from db.models import User
from jose import JWTError
from uuid import UUID

router = APIRouter(prefix="/api/auth", tags=["auth"])

# HTTP Bearer token 提取
security = HTTPBearer(auto_error=False)


async def get_current_user_from_header(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Authorization header 提取并验证用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    # 验证 token 类型
    if payload.get("type") != "access":
        raise credentials_exception

    # 获取用户 ID
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    # 查找用户
    user = await get_user_by_id(db, UUID(user_id))
    if not user:
        raise credentials_exception

    return user


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="邮箱注册",
)
async def register_endpoint(
    request: RegisterRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    邮箱注册新用户

    - 检查邮箱是否已存在
    - 创建用户并哈希密码
    - 返回 access_token 和 refresh_token
    """
    try:
        user = await register(db, request)
        await log_auth_event(
            event_type="register",
            email=request.email,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=True,
        )
        asyncio.create_task(
            send_registration_notification(
                settings=get_settings(),
                user_email=user.email,
                user_nickname=user.nickname or "",
                registration_method="email",
            )
        )
        return TokenResponse(
            access_token=create_access_token(str(user.id)),
            refresh_token=await create_refresh_token(user.id, db),
        )
    except EmailAlreadyExistsError:
        await log_auth_event(
            event_type="register",
            email=request.email,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=False,
            details={"reason": "email_exists"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "该邮箱已被注册"},
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="邮箱登录",
)
async def login_endpoint(
    request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    邮箱登录

    - 验证邮箱和密码
    - 返回 access_token 和 refresh_token
    """
    try:
        result = await login(db, request)
        await log_auth_event(
            event_type="login_success",
            email=request.email,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=True,
        )
        return result
    except AccountLockedError as exc:
        await log_auth_event(
            event_type="login_failed",
            email=request.email,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=False,
            details={"reason": "locked"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_LOCKED", "message": str(exc)},
        )
    except InvalidCredentialsError:
        await log_auth_event(
            event_type="login_failed",
            email=request.email,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误"},
        )


@router.post(
    "/apple",
    response_model=TokenResponse,
    summary="Apple 登录",
)
async def apple_login_endpoint(
    request: AppleLoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Apple Sign-In 登录

    - 验证 Apple id_token
    - 提取 apple_id
    - 如果用户存在则登录，否则注册新用户
    - 返回 access_token 和 refresh_token

    """
    try:
        result = await apple_login(db, request)
        await log_auth_event(
            event_type="apple_login",
            email="apple_user",
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=True,
        )
        return result
    except AppleAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="刷新 Token",
)
async def refresh_endpoint(
    request: RefreshRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    刷新 Token

    - 验证 refresh_token
    - 返回新的 access_token 和 refresh_token
    """
    try:
        result = await refresh_token(db, request)
        email = None
        try:
            payload = decode_token(result.access_token)
            user_id = payload.get("sub")
            if user_id:
                try:
                    user_uuid = UUID(str(user_id))
                except ValueError:
                    user_uuid = None
                if user_uuid:
                    user = await get_user_by_id(db, user_uuid)
                    email = user.email if user else None
        except JWTError:
            email = None

        await log_auth_event(
            event_type="token_refresh",
            email=email or "unknown",
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=True,
        )
        return result
    except TokenReuseError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_REUSE", "message": str(exc)},
        )
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_EXPIRED", "message": str(exc)},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Invalid refresh token"},
        )


@router.get(
    "/me",
    response_model=UserProfile,
    summary="获取当前用户信息",
)
async def get_me(
    user: Annotated[User, Depends(get_current_user_from_header)],
) -> UserProfile:
    """
    获取当前登录用户信息

    需要在 Authorization header 中提供有效的 Bearer token
    """
    return UserProfile.model_validate(user)


@router.post(
    "/send-code",
    summary="发送验证码",
)
async def send_code_endpoint(
    request: SendCodeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # registration 时检查邮箱是否已注册
    if request.purpose.value == "registration":
        existing = await get_user_by_email(db, request.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "EMAIL_EXISTS", "message": "该邮箱已被注册"},
            )

    if request.purpose.value == "password_reset":
        user_exists = await get_user_by_email(db, request.email)
        if not user_exists:
            return {"success": True}

    try:
        email_provider = get_email_provider(get_settings())
        await send_verification_code(
            db=db,
            email=request.email,
            purpose=request.purpose,
            email_provider=email_provider,
        )
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE_LIMITED", "message": str(exc)},
        )

    return {"success": True}


@router.post(
    "/verify-code",
    response_model=VerifyCodeResponse,
    summary="验证验证码",
)
async def verify_code_endpoint(
    request: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
) -> VerifyCodeResponse:
    try:
        token = await verify_code(
            db=db,
            email=request.email,
            code=request.code,
            purpose=request.purpose,
        )
    except InvalidCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CODE", "message": str(exc)},
        )
    except CodeExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CODE_EXPIRED", "message": str(exc)},
        )
    except TooManyAttemptsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TOO_MANY_ATTEMPTS", "message": str(exc)},
        )

    return VerifyCodeResponse(verification_token=token)


@router.post(
    "/register-with-code",
    response_model=TokenResponse,
    summary="验证码注册",
)
async def register_with_code_endpoint(
    request: RegisterWithCodeRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    try:
        result = await register_with_code(db, request)
        await log_auth_event(
            event_type="register",
            email=request.email,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=True,
        )
        asyncio.create_task(
            send_registration_notification(
                settings=get_settings(),
                user_email=request.email,
                user_nickname=request.nickname or "",
                registration_method="code",
            )
        )
        return result
    except EmailAlreadyExistsError:
        await log_auth_event(
            event_type="register",
            email=request.email,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=False,
            details={"reason": "email_exists"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_EXISTS", "message": "该邮箱已被注册"},
        )
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TOKEN_EXPIRED", "message": str(exc)},
        )
    except TokenInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TOKEN", "message": str(exc)},
        )


@router.post(
    "/reset-password",
    summary="重置密码",
)
async def reset_password_endpoint(
    request: ResetPasswordRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        await reset_password(db, request)
        await log_auth_event(
            event_type="password_reset",
            email=request.email,
            ip_address=http_request.client.host if http_request else None,
            user_agent=http_request.headers.get("user-agent") if http_request else None,
            success=True,
        )
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TOKEN_EXPIRED", "message": str(exc)},
        )
    except TokenInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TOKEN", "message": str(exc)},
        )

    return {"success": True}
