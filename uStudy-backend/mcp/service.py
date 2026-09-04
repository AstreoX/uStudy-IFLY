"""MCP service business logic."""

import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserMcpService
from mcp.encryption import decrypt_api_key, encrypt_api_key
from mcp.schemas import (
    McpServiceCreate,
    McpServiceResponse,
    McpServiceUpdate,
    McpToolSchema,
    TestConnectionResponse,
)

logger = logging.getLogger(__name__)

# MCP protocol constants
MCP_INITIALIZE_TIMEOUT = 10  # seconds
MCP_JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2025-03-26"


class McpService:
    """Service for managing user MCP server configurations."""

    @staticmethod
    async def list_services(user_id: UUID, db: AsyncSession) -> list[McpServiceResponse]:
        """List all MCP services for a user."""
        result = await db.execute(
            select(UserMcpService)
            .where(UserMcpService.user_id == user_id)
            .order_by(UserMcpService.created_at.desc())
        )
        services = result.scalars().all()
        return [McpService._to_response(s) for s in services]

    @staticmethod
    async def create_service(
        user_id: UUID, data: McpServiceCreate, db: AsyncSession
    ) -> McpServiceResponse:
        """Create a new MCP service configuration."""
        service = UserMcpService(
            user_id=user_id,
            name=data.name,
            url=data.url.rstrip("/"),
            api_key_encrypted=encrypt_api_key(data.api_key) if data.api_key else None,
        )
        db.add(service)
        await db.commit()
        await db.refresh(service)
        return McpService._to_response(service)

    @staticmethod
    async def update_service(
        user_id: UUID, service_id: UUID, data: McpServiceUpdate, db: AsyncSession
    ) -> McpServiceResponse | None:
        """Update an existing MCP service configuration."""
        service = await McpService._get_user_service(user_id, service_id, db)
        if not service:
            return None

        update_data = data.model_dump(exclude_none=True)

        # Handle api_key separately (encrypt before storing)
        if "api_key" in update_data:
            api_key_val = update_data.pop("api_key")
            service.api_key_encrypted = (
                encrypt_api_key(api_key_val) if api_key_val else None
            )

        for key, value in update_data.items():
            if key == "url":
                value = value.rstrip("/")
            setattr(service, key, value)

        await db.commit()
        await db.refresh(service)
        return McpService._to_response(service)

    @staticmethod
    async def delete_service(
        user_id: UUID, service_id: UUID, db: AsyncSession
    ) -> bool:
        """Delete an MCP service configuration."""
        service = await McpService._get_user_service(user_id, service_id, db)
        if not service:
            return False
        await db.delete(service)
        await db.commit()
        return True

    @staticmethod
    async def test_connection(url: str, api_key: str | None = None) -> TestConnectionResponse:
        """Test connection to an MCP server and discover available tools."""
        url = url.rstrip("/")

        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=MCP_INITIALIZE_TIMEOUT) as client:
                # Step 1: Initialize
                init_payload = {
                    "jsonrpc": MCP_JSONRPC_VERSION,
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {
                            "name": "uStudy",
                            "version": "1.0.0",
                        },
                    },
                }
                init_resp = await client.post(url, json=init_payload, headers=headers)
                init_resp.raise_for_status()
                init_data = init_resp.json()

                # Validate initialize response
                if "error" in init_data:
                    error_msg = init_data["error"].get("message", "Unknown error")
                    return TestConnectionResponse(
                        success=False, error=f"初始化失败: {error_msg}"
                    )

                # Step 2: Send initialized notification
                initialized_payload = {
                    "jsonrpc": MCP_JSONRPC_VERSION,
                    "method": "notifications/initialized",
                }
                await client.post(url, json=initialized_payload, headers=headers)

                # Step 3: List tools
                tools_payload = {
                    "jsonrpc": MCP_JSONRPC_VERSION,
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                }
                tools_resp = await client.post(url, json=tools_payload, headers=headers)
                tools_resp.raise_for_status()
                tools_data = tools_resp.json()

                if "error" in tools_data:
                    error_msg = tools_data["error"].get("message", "Unknown error")
                    return TestConnectionResponse(
                        success=False, error=f"获取工具列表失败: {error_msg}"
                    )

                raw_tools = tools_data.get("result", {}).get("tools", [])
                tools = [
                    McpToolSchema(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                    )
                    for t in raw_tools
                ]

                return TestConnectionResponse(success=True, tools=tools)

        except httpx.TimeoutException:
            return TestConnectionResponse(success=False, error="连接超时，请检查服务地址")
        except httpx.ConnectError:
            return TestConnectionResponse(
                success=False, error="无法连接到服务器，请检查地址是否正确"
            )
        except httpx.HTTPStatusError as e:
            return TestConnectionResponse(
                success=False, error=f"服务器返回错误: {e.response.status_code}"
            )
        except Exception as e:
            logger.warning(f"MCP connection test failed: {e}")
            return TestConnectionResponse(success=False, error=f"连接失败: {str(e)}")

    @staticmethod
    async def _get_user_service(
        user_id: UUID, service_id: UUID, db: AsyncSession
    ) -> UserMcpService | None:
        """Get a specific MCP service belonging to a user."""
        result = await db.execute(
            select(UserMcpService).where(
                UserMcpService.id == service_id,
                UserMcpService.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _to_response(service: UserMcpService) -> McpServiceResponse:
        """Convert ORM model to response schema."""
        tools = service.tools_cache or []
        return McpServiceResponse(
            id=service.id,
            name=service.name,
            url=service.url,
            has_api_key=service.api_key_encrypted is not None,
            enabled=service.enabled,
            tools_count=len(tools),
            tools=[McpToolSchema(**t) for t in tools],
            last_connected_at=service.last_connected_at,
            created_at=service.created_at,
        )
