"""Auth Service 测试"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import auth.service as auth_service
from auth.apple import AppleTokenPayload
from auth.exceptions import (
    AccountLockedError,
    AppleAuthError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenInvalidError,
    TokenReuseError,
)
from auth.schemas import (
    AppleLoginRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterWithCodeRequest,
    ResetPasswordRequest,
)
from auth.security import clear_login_failures
from auth.service import (
    apple_login,
    get_user_by_email,
    get_user_by_id,
    get_user_by_identifier,
    login,
    refresh_token,
    register,
    register_with_code,
    reset_password,
)
from auth.verification import create_verification_token
from core.jwt import create_access_token, create_refresh_token
from core.security import hash_password
from db.models import SubscriptionTier, User, VerificationCodePurpose


class TestRegister:
    """register 函数测试"""

    @pytest.mark.asyncio
    async def test_register_creates_user(self, db_session: AsyncSession):
        """注册创建新用户"""
        request = RegisterRequest(
            email="newuser@example.com",
            password="Secure123",
            nickname="New User",
        )
        user = await register(db_session, request)

        assert user.email == "newuser@example.com"
        assert user.nickname == "New User"
        assert user.password_hash is not None
        assert user.id is not None
        assert user.subscription_tier == SubscriptionTier.ALPHA
        assert user.subscription_expires_at is None

    @pytest.mark.asyncio
    async def test_register_hashes_password(self, db_session: AsyncSession):
        """注册时密码被哈希"""
        request = RegisterRequest(
            email="hash@example.com",
            password="Plaintext1",
            nickname="Hash User",
        )
        user = await register(db_session, request)

        assert user.password_hash != "plaintext"
        assert user.password_hash.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_register_duplicate_email_raises(self, db_session: AsyncSession):
        """重复邮箱注册抛出异常"""
        request1 = RegisterRequest(
            email="duplicate@example.com",
            password="Password1",
            nickname="User 1",
        )
        await register(db_session, request1)

        request2 = RegisterRequest(
            email="duplicate@example.com",
            password="Password2",
            nickname="User 2",
        )
        with pytest.raises(EmailAlreadyExistsError):
            await register(db_session, request2)


class TestLogin:
    """login 函数测试"""

    @pytest.mark.asyncio
    async def test_login_returns_tokens(self, db_session: AsyncSession):
        """登录返回 token 对"""
        # 先注册用户
        request = RegisterRequest(
            email="login@example.com",
            password="Password123",
            nickname="Login User",
        )
        await register(db_session, request)

        # 登录
        login_req = LoginRequest(
            email="login@example.com",
            password="Password123",
        )
        token_resp = await login(db_session, login_req)

        assert token_resp.access_token is not None
        assert token_resp.refresh_token is not None
        assert token_resp.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_email_raises(self, db_session: AsyncSession):
        """错误邮箱登录抛出异常"""
        login_req = LoginRequest(
            email="nonexistent@example.com",
            password="password123",
        )
        with pytest.raises(InvalidCredentialsError):
            await login(db_session, login_req)

    @pytest.mark.asyncio
    async def test_login_wrong_password_raises(self, db_session: AsyncSession):
        """错误密码登录抛出异常"""
        # 先注册用户
        request = RegisterRequest(
            email="wrongpw@example.com",
            password="CorrectPassword1",
            nickname="Wrong PW User",
        )
        await register(db_session, request)

        # 用错误密码登录
        login_req = LoginRequest(
            email="wrongpw@example.com",
            password="wrongpassword",
        )
        with pytest.raises(InvalidCredentialsError):
            await login(db_session, login_req)

    @pytest.mark.asyncio
    async def test_login_apple_user_without_password_raises(
        self, db_session: AsyncSession
    ):
        """Apple 用户（无密码）邮箱登录抛出异常"""
        # 创建 Apple 用户（无密码）
        user = User(
            email="apple@example.com",
            apple_id="apple_id_123",
            nickname="Apple User",
        )
        db_session.add(user)
        await db_session.commit()

        # 尝试邮箱登录
        login_req = LoginRequest(
            email="apple@example.com",
            password="anypassword",
        )
        with pytest.raises(InvalidCredentialsError):
            await login(db_session, login_req)

    @pytest.mark.asyncio
    async def test_login_by_username_is_case_insensitive(
        self, db_session: AsyncSession
    ):
        user = User(
            username="exp001",
            email="exp001@experiment.invalid",
            password_hash=hash_password("Password123"),
            nickname="Experiment 001",
            subscription_tier=SubscriptionTier.ALPHA,
            subscription_expires_at=None,
        )
        db_session.add(user)
        await db_session.commit()

        found = await get_user_by_identifier(db_session, "EXP001")
        assert found is not None
        assert found.username == "exp001"

        token_resp = await login(
            db_session,
            LoginRequest(identifier="EXP001", password="Password123"),
        )
        assert token_resp.access_token
        assert token_resp.refresh_token


class TestRefreshToken:
    """refresh_token 函数测试"""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self, db_session: AsyncSession):
        """刷新返回新 token 对"""
        # 创建用户
        request = RegisterRequest(
            email="refresh@example.com",
            password="Password123",
            nickname="Refresh User",
        )
        user = await register(db_session, request)

        # 创建 refresh token
        old_refresh = await create_refresh_token(user.id, db_session)

        # 刷新
        refresh_req = RefreshRequest(refresh_token=old_refresh)
        token_resp = await refresh_token(db_session, refresh_req)

        assert token_resp.access_token is not None
        assert token_resp.refresh_token is not None

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_raises(self, db_session: AsyncSession):
        """无效 refresh token 抛出异常"""
        refresh_req = RefreshRequest(refresh_token="invalid.token.here")
        with pytest.raises(InvalidTokenError):
            await refresh_token(db_session, refresh_req)

    @pytest.mark.asyncio
    async def test_refresh_access_token_raises(self, db_session: AsyncSession):
        """使用 access token 刷新抛出异常"""
        request = RegisterRequest(
            email="accesstype@example.com",
            password="Password123",
            nickname="Access Type User",
        )
        user = await register(db_session, request)

        # 用 access token 尝试刷新
        access = create_access_token(str(user.id))
        refresh_req = RefreshRequest(refresh_token=access)

        with pytest.raises(InvalidTokenError):
            await refresh_token(db_session, refresh_req)

    @pytest.mark.asyncio
    async def test_refresh_token_reuse_raises(self, db_session: AsyncSession):
        """重复使用 refresh token 抛出异常"""
        request = RegisterRequest(
            email="reuse@example.com",
            password="Password123",
            nickname="Reuse User",
        )
        user = await register(db_session, request)

        old_refresh = await create_refresh_token(user.id, db_session)
        refresh_req = RefreshRequest(refresh_token=old_refresh)
        await refresh_token(db_session, refresh_req)

        with pytest.raises(TokenReuseError):
            await refresh_token(db_session, refresh_req)


class TestGetUserByEmail:
    """get_user_by_email 函数测试"""

    @pytest.mark.asyncio
    async def test_get_existing_user(self, db_session: AsyncSession):
        """获取存在的用户"""
        request = RegisterRequest(
            email="getuser@example.com",
            password="Password123",
            nickname="Get User",
        )
        await register(db_session, request)

        user = await get_user_by_email(db_session, "getuser@example.com")
        assert user is not None
        assert user.email == "getuser@example.com"

    @pytest.mark.asyncio
    async def test_get_nonexistent_user_returns_none(self, db_session: AsyncSession):
        """获取不存在的用户返回 None"""
        user = await get_user_by_email(db_session, "nonexistent@example.com")
        assert user is None


class TestGetUserById:
    """get_user_by_id 函数测试"""

    @pytest.mark.asyncio
    async def test_get_existing_user_by_id(self, db_session: AsyncSession):
        """通过 ID 获取存在的用户"""
        request = RegisterRequest(
            email="byid@example.com",
            password="Password123",
            nickname="By ID User",
        )
        created_user = await register(db_session, request)

        user = await get_user_by_id(db_session, created_user.id)
        assert user is not None
        assert user.id == created_user.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_user_by_id_returns_none(
        self, db_session: AsyncSession
    ):
        """通过 ID 获取不存在的用户返回 None"""
        fake_id = uuid4()
        user = await get_user_by_id(db_session, fake_id)
        assert user is None


class TestAppleLogin:
    """apple_login 函数测试"""

    @pytest.mark.asyncio
    async def test_apple_login_creates_user(
        self, db_session: AsyncSession, monkeypatch
    ):
        """Apple 登录创建新用户"""

        async def fake_verify(_: str) -> AppleTokenPayload:
            return AppleTokenPayload(
                apple_id="apple_id_123",
                email="apple@example.com",
                email_verified=True,
            )

        monkeypatch.setattr(auth_service, "verify_apple_token", fake_verify)

        token_resp = await apple_login(
            db_session, AppleLoginRequest(id_token="mock.token")
        )

        assert token_resp.access_token is not None
        assert token_resp.refresh_token is not None

        user = await get_user_by_email(db_session, "apple@example.com")
        assert user is not None
        assert user.apple_id == "apple_id_123"

    @pytest.mark.asyncio
    async def test_apple_login_links_existing_email(
        self, db_session: AsyncSession, monkeypatch
    ):
        """Apple 登录绑定已有邮箱用户"""
        request = RegisterRequest(
            email="linked@example.com",
            password="Password123",
            nickname="Linked User",
        )
        user = await register(db_session, request)
        assert user.apple_id is None

        async def fake_verify(_: str) -> AppleTokenPayload:
            return AppleTokenPayload(
                apple_id="apple_link_id",
                email="linked@example.com",
                email_verified=True,
            )

        monkeypatch.setattr(auth_service, "verify_apple_token", fake_verify)

        await apple_login(db_session, AppleLoginRequest(id_token="mock.token"))

        updated = await get_user_by_email(db_session, "linked@example.com")
        assert updated is not None
        assert updated.apple_id == "apple_link_id"

    @pytest.mark.asyncio
    async def test_apple_login_missing_email_raises(
        self, db_session: AsyncSession, monkeypatch
    ):
        """Apple 登录缺少 email 抛出异常"""

        async def fake_verify(_: str) -> AppleTokenPayload:
            return AppleTokenPayload(
                apple_id="apple_id_456",
                email=None,
                email_verified=True,
            )

        monkeypatch.setattr(auth_service, "verify_apple_token", fake_verify)

        with pytest.raises(AppleAuthError):
            await apple_login(db_session, AppleLoginRequest(id_token="mock.token"))


class TestRegisterWithCode:
    """register_with_code 测试"""

    @pytest.mark.asyncio
    async def test_register_with_code_success(self, db_session: AsyncSession):
        token = create_verification_token(
            "codeuser@example.com", VerificationCodePurpose.REGISTRATION
        )
        request = RegisterWithCodeRequest(
            email="codeuser@example.com",
            verification_token=token,
            password="Password123",
            nickname="Code User",
        )

        resp = await register_with_code(db_session, request)
        assert resp.access_token is not None
        assert resp.refresh_token is not None
        user = await get_user_by_email(db_session, "codeuser@example.com")
        assert user is not None
        assert user.subscription_tier == SubscriptionTier.ALPHA
        assert user.subscription_expires_at is None

    @pytest.mark.asyncio
    async def test_register_with_code_email_mismatch(self, db_session: AsyncSession):
        token = create_verification_token(
            "other@example.com", VerificationCodePurpose.REGISTRATION
        )
        request = RegisterWithCodeRequest(
            email="codeuser@example.com",
            verification_token=token,
            password="Password123",
            nickname="Code User",
        )
        with pytest.raises(TokenInvalidError):
            await register_with_code(db_session, request)


class TestResetPassword:
    """reset_password 测试"""

    @pytest.mark.asyncio
    async def test_reset_password_success(self, db_session: AsyncSession):
        request = RegisterRequest(
            email="reset@example.com",
            password="Password123",
            nickname="Reset User",
        )
        user = await register(db_session, request)

        token = create_verification_token(
            "reset@example.com", VerificationCodePurpose.PASSWORD_RESET
        )
        reset_req = ResetPasswordRequest(
            email="reset@example.com",
            verification_token=token,
            new_password="NewPassword123",
        )
        await reset_password(db_session, reset_req)

        login_req = LoginRequest(
            email="reset@example.com",
            password="NewPassword123",
        )
        resp = await login(db_session, login_req)
        assert resp.access_token is not None
        assert resp.refresh_token is not None


class TestLoginLockout:
    """登录锁定测试"""

    @pytest.mark.asyncio
    async def test_login_lockout_after_failures(self, db_session: AsyncSession):
        request = RegisterRequest(
            email="lockout@example.com",
            password="Password123",
            nickname="Lock User",
        )
        await register(db_session, request)

        login_req = LoginRequest(
            email="lockout@example.com",
            password="wrongpw",
        )

        for _ in range(5):
            with pytest.raises(InvalidCredentialsError):
                await login(db_session, login_req)

        with pytest.raises(AccountLockedError):
            await login(db_session, login_req)

        await clear_login_failures("lockout@example.com")
