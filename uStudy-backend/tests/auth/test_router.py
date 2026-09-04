"""Auth Router 测试"""

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import auth.service as auth_service
from datetime import datetime, timedelta, timezone
from auth.apple import AppleTokenPayload
from auth.exceptions import AppleAuthError
from auth.schemas import RegisterRequest
from auth.service import register
from auth.verification import create_verification_token
from config import get_settings
from core.jwt import create_access_token, create_refresh_token
from core.security import hash_password
from db.database import get_db
from db.models import SubscriptionTier, User, VerificationCode, VerificationCodePurpose
from auth.router import router as auth_router


app = FastAPI()
app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path in {
        "/api/auth/register",
        "/api/auth/register-with-code",
        "/api/auth/reset-password",
    }:
        for error in exc.errors():
            if any(field in ("password", "new_password") for field in error.get("loc", [])):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": {
                            "code": "WEAK_PASSWORD",
                            "message": error.get("msg", "密码强度不足"),
                        }
                    },
                )
    return await request_validation_exception_handler(request, exc)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """创建测试客户端"""

    settings = get_settings()
    original_registration = settings.public_registration_enabled
    original_auth_email = settings.auth_email_enabled
    original_apple_login = settings.apple_login_enabled
    original_email = settings.email_enabled
    settings.public_registration_enabled = True
    settings.auth_email_enabled = True
    settings.apple_login_enabled = True
    settings.email_enabled = False

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    settings.public_registration_enabled = original_registration
    settings.auth_email_enabled = original_auth_email
    settings.apple_login_enabled = original_apple_login
    settings.email_enabled = original_email


class TestRegisterEndpoint:
    """POST /api/auth/register 测试"""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """注册成功返回 tokens"""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "Password123",
                "nickname": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """无效邮箱返回 422"""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "invalid_email",
                "password": "Password123",
                "nickname": "User",
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """重复邮箱返回 409"""
        # 先注册一个用户
        request = RegisterRequest(
            email="existing@example.com",
            password="Password123",
            nickname="Existing",
        )
        await register(db_session, request)

        # 再次注册相同邮箱
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "existing@example.com",
                "password": "Password456",
                "nickname": "Duplicate",
            },
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """密码太短返回 400"""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "12345",
                "nickname": "User",
            },
        )
        assert response.status_code == 400


class TestLoginEndpoint:
    """POST /api/auth/login 测试"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, db_session: AsyncSession):
        """登录成功返回 tokens"""
        # 先注册用户
        request = RegisterRequest(
            email="login@example.com",
            password="Password123",
            nickname="Login User",
        )
        await register(db_session, request)

        # 登录
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "login@example.com",
                "password": "Password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """错误密码返回 401"""
        request = RegisterRequest(
            email="wrongpw@example.com",
            password="Correctpw1",
            nickname="User",
        )
        await register(db_session, request)

        response = await client.post(
            "/api/auth/login",
            json={
                "email": "wrongpw@example.com",
                "password": "Wrongpw1",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """用户不存在返回 401"""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_username(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        db_session.add(
            User(
                username="exp001",
                email="exp001@experiment.invalid",
                nickname="Experiment 001",
                password_hash=hash_password("Password123"),
                subscription_tier=SubscriptionTier.ALPHA,
                subscription_expires_at=None,
            )
        )
        await db_session.commit()

        response = await client.post(
            "/api/auth/login",
            json={"identifier": "EXP001", "password": "Password123"},
        )
        assert response.status_code == 200
        assert response.json()["access_token"]


class TestExperimentFeatureFlags:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("path", "payload"),
        [
            (
                "/api/auth/register",
                {
                    "email": "disabled@example.com",
                    "password": "Password123",
                    "nickname": "Disabled",
                },
            ),
            (
                "/api/auth/send-code",
                {"email": "disabled@example.com", "purpose": "registration"},
            ),
            (
                "/api/auth/verify-code",
                {
                    "email": "disabled@example.com",
                    "code": "123456",
                    "purpose": "registration",
                },
            ),
            (
                "/api/auth/reset-password",
                {
                    "email": "disabled@example.com",
                    "verification_token": "disabled-token",
                    "new_password": "Password123",
                },
            ),
        ],
    )
    async def test_public_account_features_return_404(
        self, client: AsyncClient, path: str, payload: dict
    ):
        get_settings().public_registration_enabled = False
        response = await client.post(path, json=payload)
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "FEATURE_DISABLED"

    @pytest.mark.asyncio
    async def test_apple_login_remains_disabled(self, client: AsyncClient):
        get_settings().apple_login_enabled = False
        response = await client.post(
            "/api/auth/apple",
            json={"id_token": "disabled.token"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "FEATURE_DISABLED"

    @pytest.mark.asyncio
    async def test_auth_email_flow_can_be_disabled_independently(
        self, client: AsyncClient
    ):
        get_settings().auth_email_enabled = False
        response = await client.post(
            "/api/auth/send-code",
            json={"email": "disabled@example.com", "purpose": "registration"},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "FEATURE_DISABLED"


class TestRefreshEndpoint:
    """POST /api/auth/refresh 测试"""

    @pytest.mark.asyncio
    async def test_refresh_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """刷新成功返回新 tokens"""
        request = RegisterRequest(
            email="refresh@example.com",
            password="Password123",
            nickname="Refresh User",
        )
        user = await register(db_session, request)
        refresh = await create_refresh_token(user.id, db_session)

        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """无效 token 返回 401"""
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid.token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_access_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """使用 access token 刷新返回 401"""
        request = RegisterRequest(
            email="accessrefresh@example.com",
            password="Password123",
            nickname="Access Refresh User",
        )
        user = await register(db_session, request)
        access = create_access_token(str(user.id))

        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": access},
        )
        assert response.status_code == 401


class TestAppleEndpoint:
    """POST /api/auth/apple 测试"""

    @pytest.mark.asyncio
    async def test_apple_login_success(self, client: AsyncClient, monkeypatch):
        """Apple 登录成功返回 tokens"""

        async def fake_verify(_: str) -> AppleTokenPayload:
            return AppleTokenPayload(
                apple_id="apple_user_id_123",
                email="apple@example.com",
                email_verified=True,
            )

        monkeypatch.setattr(auth_service, "verify_apple_token", fake_verify)

        response = await client.post(
            "/api/auth/apple",
            json={"id_token": "mock.token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_apple_login_invalid_token(self, client: AsyncClient, monkeypatch):
        """Apple 登录无效 token 返回 401"""

        async def fake_verify(_: str) -> AppleTokenPayload:
            raise AppleAuthError("Invalid Apple token")

        monkeypatch.setattr(auth_service, "verify_apple_token", fake_verify)

        response = await client.post(
            "/api/auth/apple",
            json={"id_token": "invalid.token"},
        )
        assert response.status_code == 401


class TestMeEndpoint:
    """GET /api/auth/me 测试"""

    @pytest.mark.asyncio
    async def test_me_authenticated(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """已认证用户获取个人信息"""
        request = RegisterRequest(
            email="me@example.com",
            password="Password123",
            nickname="Me User",
        )
        user = await register(db_session, request)
        token = create_access_token(str(user.id))

        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"
        assert data["nickname"] == "Me User"

    @pytest.mark.asyncio
    async def test_me_unauthenticated(self, client: AsyncClient):
        """未认证返回 401"""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client: AsyncClient):
        """无效 token 返回 401"""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401


class TestVerificationEndpoints:
    """验证码相关接口测试"""

    @pytest.mark.asyncio
    async def test_send_code_registration_success(
        self, client: AsyncClient, monkeypatch
    ):
        class DummyProvider:
            async def send_verification_email(self, to: str, code: str) -> bool:
                return True

        from auth import router as auth_router

        monkeypatch.setattr(auth_router, "get_email_provider", lambda *_: DummyProvider())

        response = await client.post(
            "/api/auth/send-code",
            json={"email": "new@example.com", "purpose": "registration"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_verify_code_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        code = "123456"
        verification = VerificationCode(
            email="verify@example.com",
            code=code,
            purpose=VerificationCodePurpose.REGISTRATION,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db_session.add(verification)
        await db_session.commit()

        response = await client.post(
            "/api/auth/verify-code",
            json={
                "email": "verify@example.com",
                "code": code,
                "purpose": "registration",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "verification_token" in data


class TestRegisterWithCodeEndpoint:
    """验证码注册接口测试"""

    @pytest.mark.asyncio
    async def test_register_with_code_success(
        self, client: AsyncClient
    ):
        token = create_verification_token(
            "code@example.com", VerificationCodePurpose.REGISTRATION
        )

        response = await client.post(
            "/api/auth/register-with-code",
            json={
                "email": "code@example.com",
                "verification_token": token,
                "password": "Password123",
                "nickname": "Code User",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


class TestResetPasswordEndpoint:
    """重置密码接口测试"""

    @pytest.mark.asyncio
    async def test_reset_password_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        request = RegisterRequest(
            email="resetrouter@example.com",
            password="Password123",
            nickname="Reset Router",
        )
        await register(db_session, request)

        token = create_verification_token(
            "resetrouter@example.com", VerificationCodePurpose.PASSWORD_RESET
        )

        response = await client.post(
            "/api/auth/reset-password",
            json={
                "email": "resetrouter@example.com",
                "verification_token": token,
                "new_password": "NewPassword123",
            },
        )
        assert response.status_code == 200
