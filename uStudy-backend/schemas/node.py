"""Node Schema 定义"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NodeBase(BaseModel):
    """节点基础字段"""

    label: str = Field(..., min_length=1, max_length=200)
    mastery: int = Field(default=0, ge=0, le=100)


class NodeCreate(NodeBase):
    """节点创建请求"""

    pass


class NodeUpdate(BaseModel):
    """节点更新请求"""

    label: Optional[str] = Field(None, min_length=1, max_length=200)
    mastery: Optional[int] = Field(None, ge=0, le=100)


class NodeResponse(NodeBase):
    """节点响应（API 返回）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    space_id: UUID
