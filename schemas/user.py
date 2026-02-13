"""User Schema 定义"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from db.models import SubscriptionTier


class UserBase(BaseModel):
    """用户基础字段"""

    email: EmailStr
    nickname: str = Field(..., min_length=1, max_length=100)


class UserCreate(UserBase):
    """用户创建请求"""

    password: str = Field(..., min_length=6, max_length=128)


class UserUpdate(BaseModel):
    """用户更新请求"""

    nickname: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=6, max_length=128)


class UserResponse(UserBase):
    """用户响应（API 返回）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    avatar_url: Optional[str] = None
    subscription_tier: SubscriptionTier
    created_at: datetime


class UserInDB(UserResponse):
    """数据库完整用户模型（内部使用）"""

    password_hash: Optional[str]
    apple_id: Optional[str]
    subscription_expires_at: Optional[datetime]
    updated_at: datetime
