"""Message Schema 定义"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from db.models import MessageRole


class MessageBase(BaseModel):
    """消息基础字段"""

    role: MessageRole
    content: str = Field(..., min_length=1)


class MessageCreate(MessageBase):
    """消息创建请求"""

    pass


class MessageResponse(MessageBase):
    """消息响应（API 返回）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    created_at: datetime
