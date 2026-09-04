"""MCP service API router."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from mcp.schemas import (
    McpServiceCreate,
    McpServiceListResponse,
    McpServiceResponse,
    McpServiceUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)
from mcp.service import McpService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp-services", tags=["mcp-services"])


@router.get("", response_model=McpServiceListResponse)
async def list_mcp_services(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> McpServiceListResponse:
    """List all MCP services for the current user."""
    services = await McpService.list_services(user.id, db)
    return McpServiceListResponse(services=services)


@router.post("", response_model=McpServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_service(
    data: McpServiceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> McpServiceResponse:
    """Create a new MCP service configuration."""
    return await McpService.create_service(user.id, data, db)


@router.patch("/{service_id}", response_model=McpServiceResponse)
async def update_mcp_service(
    service_id: UUID,
    data: McpServiceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> McpServiceResponse:
    """Update an existing MCP service configuration."""
    result = await McpService.update_service(user.id, service_id, data, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "MCP 服务不存在"},
        )
    return result


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_service(
    service_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an MCP service configuration."""
    deleted = await McpService.delete_service(user.id, service_id, db)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "MCP 服务不存在"},
        )


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_mcp_connection(
    data: TestConnectionRequest,
    user: User = Depends(get_current_user),
) -> TestConnectionResponse:
    """Test connection to an MCP server and discover available tools."""
    return await McpService.test_connection(data.url, data.api_key)
