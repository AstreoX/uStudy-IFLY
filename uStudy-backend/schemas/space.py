"""Space Schema 定义"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SpaceBase(BaseModel):
    """空间基础字段"""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")


class SpaceCreate(SpaceBase):
    """空间创建请求"""

    pass


class SpaceUpdate(BaseModel):
    """空间更新请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class SpaceResponse(SpaceBase):
    """空间响应（API 返回）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
