"""Chat Schemas - Pydantic models for request/response"""

from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from attachments.schemas import AttachmentResponse


# ============ Request Schemas ============


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation"""

    content: str = Field(..., min_length=1, max_length=10000, description="消息内容")
    attachment_ids: Optional[list[UUID]] = Field(
        default=None, max_length=9, description="附件ID列表（最多9个）"
    )
    model_id: Optional[str] = Field(
        default=None, max_length=50, description="模型ID，不指定则使用默认模型"
    )
    panel_screenshot: Optional[str] = Field(
        default=None, max_length=500000, description="左面板截图 (base64 data URI, 双栏同步模式)"
    )
    thinking: Optional[bool] = Field(
        default=None, description="是否启用深度思考模式（True=开启, False=关闭, None=使用默认）"
    )


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation"""

    title: str = Field(..., min_length=1, max_length=200, description="对话标题")


class UpdateConversationRequest(BaseModel):
    """Request for updating conversation"""

    space_id: Optional[UUID] = Field(None, description="绑定的学习空间ID")
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="对话标题")


class UpdateConversationTodoStatusRequest(BaseModel):
    """Request for updating a conversation-scoped todo completion state."""

    completed: bool = Field(..., description="是否标记为已完成")


class ToolCallFunction(BaseModel):
    """Tool call function payload (LLM tool_call format)"""

    name: str = Field(..., min_length=1, description="工具名称")
    arguments: Union[str, dict[str, Any]] = Field(
        ..., description="工具参数（JSON字符串或对象）"
    )

    model_config = {"extra": "ignore"}


class ToolCallRequest(BaseModel):
    """Tool call request payload (LLM tool_call format)"""

    id: Optional[str] = Field(None, description="tool_call id")
    type: Optional[str] = Field(None, description="tool_call type")
    function: ToolCallFunction

    model_config = {"extra": "ignore"}


# ============ Response Schemas ============


class MessageResponse(BaseModel):
    """Response model for a single message"""

    id: UUID
    role: str
    content: str
    attachments: list[AttachmentResponse] = []
    tool_calls: Optional[list[dict[str, Any]]] = None
    citations: Optional[list[dict[str, Any]]] = None
    response_status: str = "completed"
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    """Response model for a conversation"""

    id: UUID
    user_id: UUID
    space_id: Optional[UUID]
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    """Response model for conversation with messages"""

    conversation: ConversationResponse
    messages: list[MessageResponse]


class AgentTodoItemResponse(BaseModel):
    """Normalized conversation-scoped agent todo item."""

    id: UUID
    conversation_id: UUID
    task_id: str
    title: str
    details: Optional[str] = None
    status: str
    sort_order: int
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ConversationTodoListResponse(BaseModel):
    """Todo list for a conversation."""

    conversation_id: UUID
    todos: list[AgentTodoItemResponse]


class ConversationListResponse(BaseModel):
    """Response model for listing conversations"""

    conversations: list[ConversationResponse]
    total: int


class MessageSnippet(BaseModel):
    """A message with a snippet of matching context"""

    id: UUID
    role: str
    snippet: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSearchItem(BaseModel):
    """A conversation result in a search response"""

    id: UUID
    title: str
    space_id: Optional[UUID]
    updated_at: datetime
    created_at: datetime
    matching_messages: list[MessageSnippet]

    model_config = {"from_attributes": True}


class ConversationSearchResponse(BaseModel):
    """Response for conversation search"""

    items: list[ConversationSearchItem]
    total: int
    page: int
    page_size: int
    query: str


class ToolCallExecuteResponse(BaseModel):
    """Response for executing a tool call"""

    raw_tool_output: str = Field(..., description="发送给AI的原始工具返回内容")
    parsed: Optional[dict[str, Any]] = Field(None, description="结构化结果")


class ClientToolResultRequest(BaseModel):
    """Request from frontend submitting a client-side tool execution result"""

    tool_call_id: str = Field(..., min_length=1, description="工具调用 ID")
    success: bool = Field(..., description="工具执行是否成功")
    result: Optional[dict[str, Any]] = Field(None, description="执行结果数据")
    error: Optional[str] = Field(None, max_length=500, description="错误消息")


class ClientToolResultResponse(BaseModel):
    """Response for client tool result submission"""

    received: bool = Field(..., description="是否成功接收")
    message: str = Field(..., description="处理消息")


class StopStreamResponse(BaseModel):
    """Response for user-requested stream stop"""

    stopped: bool = Field(..., description="是否成功进入终止态")
    is_streaming: bool = Field(..., description="当前是否仍在流式生成")
    is_stopped: bool = Field(..., description="当前是否已被用户终止")
    partial_content: Optional[str] = Field(None, description="已生成的部分文本")
    partial_thinking: Optional[str] = Field(None, description="已生成的思考内容")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="已产生的工具调用")
    updated_at: Optional[float] = Field(None, description="最近更新时间戳")


class RollbackResponse(BaseModel):
    """Response for rolling back the last user message round"""

    deleted_count: int = Field(..., description="删除的消息数量")
