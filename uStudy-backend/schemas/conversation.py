"""Conversation Schema 定义"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationBase(BaseModel):
    """对话基础字段"""

    title: str = Field(..., min_length=1, max_length=200)


class ConversationCreate(ConversationBase):
    """对话创建请求"""

    space_id: Optional[UUID] = None


class ConversationUpdate(BaseModel):
    """对话更新请求"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)


class ConversationResponse(ConversationBase):
    """对话响应（API 返回）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    space_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
