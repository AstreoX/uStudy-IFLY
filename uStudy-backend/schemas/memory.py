"""Long-Term Memory Schema"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryEntryBase(BaseModel):
    """单条记忆条目"""

    id: int
    content: str
    created_at: str


class LongTermMemoryResponse(BaseModel):
    """长期记忆响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    entries: list[MemoryEntryBase]
    next_entry_id: int
    created_at: datetime
    updated_at: datetime


class MemoryWriteRequest(BaseModel):
    """写入记忆请求（用于 API）"""

    content: str = Field(..., min_length=1, max_length=500)


class MemoryDeleteRequest(BaseModel):
    """删除记忆请求（用于 API）"""

    entry_id: Optional[int] = Field(None, description="要删除的条目序号")
    clear_all: bool = Field(False, description="是否清空所有记忆")
