"""API contracts for teacher presentation projects and the sandbox gateway."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ProjectResponse(BaseModel):
    id: UUID
    space_id: UUID
    conversation_id: UUID
    title: str
    current_revision_id: UUID | None
    published_document_id: UUID | None
    active_run_id: UUID | None = None
    status: str = "idle"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssetResponse(BaseModel):
    id: UUID
    project_id: UUID
    revision_id: UUID | None
    kind: str
    filename: str
    mime_type: str | None
    file_size: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)
    source_ids: list[UUID] = Field(default_factory=list, max_length=50)
    expected_revision_id: UUID | None = None


class RevisionResponse(BaseModel):
    id: UUID
    project_id: UUID
    parent_revision_id: UUID | None
    revision_number: int
    status: str
    summary: str | None
    manifest: dict[str, Any] | None
    preview_manifest: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class RunResponse(BaseModel):
    id: UUID
    project_id: UUID
    revision_id: UUID
    manager_run_id: str | None
    status: str
    error_message: str | None
    attempt_count: int = 1
    last_heartbeat_at: datetime | None = None
    retry_deadline_at: datetime | None = None
    last_sequence: int = 0
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ConversationMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    llm_context: dict[str, Any] | None
    tool_calls: list[dict[str, Any]] | None
    created_at: datetime
    run_id: UUID | None = None
    run_status: str | None = None
    stream_sequence: int = 0
    streaming: bool = False
    recoverable: bool = False
    run_error: str | None = None
    error_code: str | None = None

    model_config = {"from_attributes": True}


class PublishRequest(BaseModel):
    confirmed: bool
    title: str | None = Field(default=None, min_length=1, max_length=255)


class PublicationResponse(BaseModel):
    publication_id: UUID
    document_id: UUID
    revision_id: UUID
    title: str
    created_at: datetime


class GatewayEvent(BaseModel):
    sequence: int | None = Field(default=None, ge=1)
    type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, str] = Field(default_factory=dict)


class GatewayEventBatch(BaseModel):
    events: list[GatewayEvent] = Field(min_length=1, max_length=100)


class GatewayToolRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class GatewayLLMRequest(BaseModel):
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    temperature: float = Field(default=0.4, ge=0, le=2)
    max_tokens: int = Field(default=32768, ge=1, le=65536)
    enable_thinking: bool | None = True
    scope: dict[str, str] = Field(default_factory=dict)


class GatewayLLMResponse(BaseModel):
    content: str | None
    tool_calls: list[dict[str, Any]]
    finish_reason: str
    usage: dict[str, int] | None


TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})
ALLOWED_SOURCE_KINDS = frozenset({"source", "template"})
GatewayToolName = Literal[
    "get_course_graph_overview",
    "list_documents",
    "search_keywords",
    "read_document",
    "view_document_page",
    "get_class_knowledge_summary",
    "generate_image",
    "publish_presentation_to_space",
]
