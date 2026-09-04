"""MCP service Pydantic schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class McpToolSchema(BaseModel):
    """Single MCP tool info."""

    name: str
    description: str = ""


class McpServiceCreate(BaseModel):
    """Request schema for creating an MCP service."""

    name: str
    url: str
    api_key: str | None = None


class McpServiceUpdate(BaseModel):
    """Partial update schema for MCP service."""

    name: str | None = None
    url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None


class McpServiceResponse(BaseModel):
    """Response schema for a single MCP service."""

    id: UUID
    name: str
    url: str
    has_api_key: bool
    enabled: bool
    tools_count: int
    tools: list[McpToolSchema]
    last_connected_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class McpServiceListResponse(BaseModel):
    """Response schema for listing MCP services."""

    services: list[McpServiceResponse]


class TestConnectionRequest(BaseModel):
    """Request schema for testing MCP connection."""

    url: str
    api_key: str | None = None


class TestConnectionResponse(BaseModel):
    """Response schema for connection test."""

    success: bool
    tools: list[McpToolSchema] = []
    error: str | None = None
