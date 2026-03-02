"""Activation code schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ActivateCodeRequest(BaseModel):
    """激活码请求"""

    code: str = Field(..., min_length=10, max_length=20, description="激活码")


class ActivateCodeResponse(BaseModel):
    """激活码响应"""

    success: bool
    subscription_tier: str
    subscription_expires_at: datetime
    message: str
