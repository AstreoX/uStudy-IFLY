"""Auth Schema 测试"""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from auth.schemas import (
    AppleLoginRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)
from db.models import SubscriptionTier


class TestRegisterRequest:
    """RegisterRequest Schema 测试"""

    def test_valid_register_request(self):
        """有效的注册请求"""
        req = RegisterRequest(
            email="test@example.com",
            password="Secure123",
            nickname="Test User",
        )
        assert req.email == "test@example.com"
        assert req.password == "Secure123"
        assert req.nickname == "Test User"

    def test_invalid_email_format(self):
        """无效邮箱格式"""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="not_an_email",
                password="Secure123",
                nickname="Test",
            )
        assert "email" in str(exc_info.value).lower()

    def test_password_min_length(self):
        """密码最小长度 8"""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="test@example.com",
                password="12345",
                nickname="Test",
            )
        assert "password" in str(exc_info.value).lower()

    def test_password_max_length(self):
        """密码最大长度 128"""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="test@example.com",
                password="a" * 129,
                nickname="Test",
            )
        assert "password" in str(exc_info.value).lower()

    def test_nickname_min_length(self):
        """昵称最小长度 1"""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="test@example.com",
                password="Secure123",
                nickname="",
            )
        assert "nickname" in str(exc_info.value).lower()

    def test_nickname_max_length(self):
        """昵称最大长度 100"""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="test@example.com",
                password="Secure123",
                nickname="a" * 101,
            )
        assert "nickname" in str(exc_info.value).lower()


class TestLoginRequest:
    """LoginRequest Schema 测试"""

    def test_valid_login_request(self):
        """有效的登录请求"""
        req = LoginRequest(
            email="user@example.com",
            password="password123",
        )
        assert req.email == "user@example.com"
        assert req.password == "password123"

    def test_invalid_email(self):
        """无效邮箱"""
        with pytest.raises(ValidationError):
            LoginRequest(
                email="invalid",
                password="password123",
            )


class TestAppleLoginRequest:
    """AppleLoginRequest Schema 测试"""

    def test_valid_apple_login_request(self):
        """有效的 Apple 登录请求"""
        req = AppleLoginRequest(
            id_token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test",
        )
        assert req.id_token.startswith("eyJ")

    def test_empty_id_token(self):
        """空 id_token"""
        with pytest.raises(ValidationError) as exc_info:
            AppleLoginRequest(id_token="")
        assert "id_token" in str(exc_info.value).lower()


class TestRefreshRequest:
    """RefreshRequest Schema 测试"""

    def test_valid_refresh_request(self):
        """有效的刷新请求"""
        req = RefreshRequest(refresh_token="some.jwt.token")
        assert req.refresh_token == "some.jwt.token"

    def test_empty_refresh_token(self):
        """空 refresh_token"""
        with pytest.raises(ValidationError) as exc_info:
            RefreshRequest(refresh_token="")
        assert "refresh_token" in str(exc_info.value).lower()


class TestTokenResponse:
    """TokenResponse Schema 测试"""

    def test_token_response_fields(self):
        """Token 响应包含所有字段"""
        resp = TokenResponse(
            access_token="access.jwt.token",
            refresh_token="refresh.jwt.token",
            token_type="bearer",
        )
        assert resp.access_token == "access.jwt.token"
        assert resp.refresh_token == "refresh.jwt.token"
        assert resp.token_type == "bearer"

    def test_token_type_default(self):
        """token_type 默认值为 bearer"""
        resp = TokenResponse(
            access_token="access.token",
            refresh_token="refresh.token",
        )
        assert resp.token_type == "bearer"


class TestUserProfile:
    """UserProfile Schema 测试"""

    def test_user_profile_from_dict(self):
        """从字典创建 UserProfile"""
        profile_data = {
            "id": uuid4(),
            "email": "profile@example.com",
            "nickname": "Profile User",
            "subscription_tier": SubscriptionTier.PREMIUM,
            "subscription_expires_at": datetime.now(),
        }
        profile = UserProfile.model_validate(profile_data)
        assert profile.email == "profile@example.com"
        assert profile.subscription_tier == SubscriptionTier.PREMIUM

    def test_user_profile_free_tier(self):
        """免费用户 Profile"""
        profile_data = {
            "id": uuid4(),
            "email": "free@example.com",
            "nickname": "Free User",
            "subscription_tier": SubscriptionTier.FREE,
            "subscription_expires_at": None,
        }
        profile = UserProfile.model_validate(profile_data)
        assert profile.subscription_tier == SubscriptionTier.FREE
        assert profile.subscription_expires_at is None
