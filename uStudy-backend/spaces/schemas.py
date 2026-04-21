"""学习空间相关 Pydantic Schema"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LearningPreferencesSchema(BaseModel):
    """学习偏好设置"""

    preset_preferences: list[str] = Field(
        default_factory=list,
        description="预设偏好ID列表",
    )
    custom_preference: str | None = Field(
        None,
        max_length=500,
        description="自定义偏好描述",
    )

    @field_validator("preset_preferences")
    @classmethod
    def validate_preset_preferences(cls, v: list[str]) -> list[str]:
        valid_presets = {
            "university", "quick", "solid", "hobby",
            "exam", "work", "research", "practice"
        }
        return [p for p in v if p in valid_presets][:8]


class SpaceCreate(BaseModel):
    """创建学习空间请求"""

    name: str = Field(..., min_length=1, max_length=200, description="学习主题名称")
    description: Optional[str] = Field(None, max_length=1000, description="描述（可选）")
    color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$", description="十六进制颜色")
    learning_preferences: Optional[LearningPreferencesSchema] = Field(
        None, description="学习偏好设置（可选）"
    )


class SpaceUpdate(BaseModel):
    """更新学习空间请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    memory_sharing_enabled: Optional[bool] = Field(
        None, description="是否开启记忆共享（允许其他空间检索本空间记忆）"
    )
    tool_mode: Optional[str] = Field(
        None, description="工具模式：auto / manual"
    )
    enabled_tools: Optional[list[str]] = Field(
        None, description="manual 模式下启用的工具名称数组"
    )

    @field_validator("tool_mode")
    @classmethod
    def validate_tool_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in ("auto", "manual"):
            raise ValueError("tool_mode 必须是 auto 或 manual")
        return v


class SpaceResponse(BaseModel):
    """学习空间响应"""

    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    color: str
    learning_preferences: Optional[dict] = None
    memory_sharing_enabled: bool = False
    tool_mode: str = "auto"
    enabled_tools: Optional[list[str]] = None
    is_collaborative: bool = False
    user_role: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NodeResponse(BaseModel):
    """知识节点响应"""

    id: UUID
    label: str
    mastery: Optional[int] = Field(None, ge=0, le=100, description="掌握度 0-100，null表示未学习")

    model_config = {"from_attributes": True}


class EdgeResponse(BaseModel):
    """知识边响应"""

    id: UUID
    from_node_id: UUID
    to_node_id: UUID
    type: str = Field(..., description="边类型：knowledge_tree | learning_path | advanced")

    model_config = {"from_attributes": True}


class SpaceGraphResponse(BaseModel):
    """学习空间知识图谱响应"""

    nodes: List[NodeResponse]
    edges: List[EdgeResponse]


class LearningPathEventResponse(BaseModel):
    """学习路径扩展事件响应"""

    id: UUID
    new_node_names: list[str]
    trigger_info: dict
    created_at: datetime

    model_config = {"from_attributes": True}
