"""Auth Schema 定义"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator

from db.models import SubscriptionTier, VerificationCodePurpose


class PasswordMixin:
    @field_validator("password", mode="before", check_fields=False)
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码长度至少8位")
        if not any(char.isupper() for char in value):
            raise ValueError("密码需包含大写字母")
        if not any(char.islower() for char in value):
            raise ValueError("密码需包含小写字母")
        if not any(char.isdigit() for char in value):
            raise ValueError("密码需包含数字")
        return value


class RegisterRequest(BaseModel, PasswordMixin):
    """邮箱注册请求"""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    nickname: str = Field(..., min_length=1, max_length=100)
    invite_code: Optional[str] = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    """Username/password login request with legacy email input compatibility."""

    identifier: str = Field(
        ...,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("identifier", "email"),
    )
    password: str = Field(..., min_length=1)

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("账号不能为空")
        return normalized


class AppleLoginRequest(BaseModel):
    """Apple 登录请求"""

    id_token: str = Field(..., min_length=1)
    invite_code: Optional[str] = Field(default=None, max_length=32)


class RefreshRequest(BaseModel):
    """刷新 Token 请求"""

    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token 响应"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class SendCodeRequest(BaseModel):
    email: EmailStr
    purpose: VerificationCodePurpose


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    purpose: VerificationCodePurpose


class VerifyCodeResponse(BaseModel):
    verification_token: str
    expires_in: int = 300


class RegisterWithCodeRequest(BaseModel, PasswordMixin):
    email: EmailStr
    verification_token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)
    nickname: str = Field(..., min_length=2, max_length=50)
    invite_code: Optional[str] = Field(default=None, max_length=32)


class ResetPasswordRequest(BaseModel, PasswordMixin):
    email: EmailStr
    verification_token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password", mode="before")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return cls.validate_password(value)


class UserProfile(BaseModel):
    """用户信息"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: Optional[str] = None
    email: str
    nickname: str
    avatar_url: Optional[str] = None
    subscription_tier: SubscriptionTier
    subscription_expires_at: Optional[datetime]


class UpdateNicknameRequest(BaseModel):
    """更新昵称请求"""

    nickname: str = Field(..., min_length=2, max_length=20)
