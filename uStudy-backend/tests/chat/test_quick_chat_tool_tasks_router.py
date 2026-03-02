"""Quick chat async create-space tool router tests."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from auth.dependencies import (
    get_current_user,
    require_active_subscription,
)
from chat.router import router
from chat.service import ChatService
from chat.tools.base import ToolResult
from chat.tools.learning_space_executor import LearningSpaceToolExecutor
from db.database import get_db


@pytest_asyncio.fixture
async def quick_chat_client(monkeypatch):
    """Build app client with auth/db dependencies overridden."""
    fake_user = SimpleNamespace(id=uuid4())

    async def override_get_current_user():
        return fake_user

    async def override_require_active_subscription():
        return fake_user

    async def override_get_db():
        yield None

    async def mock_validate_conversation_access(
        self, user_id, conversation_id, require_space=False
    ):
        return None

    monkeypatch.setattr(
        ChatService,
        "validate_conversation_access",
        mock_validate_conversation_access,
    )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_active_subscription] = (
        override_require_active_subscription
    )
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


class TestQuickChatToolConfirm:
    """Tests for tool confirm endpoint status branching."""

    @pytest.mark.asyncio
    async def test_confirm_create_space_returns_accepted_for_async_action(
        self, quick_chat_client: AsyncClient, monkeypatch
    ):
        conversation_id = uuid4()
        tool_call_id = "call_create_1"
        captured = {}

        async def mock_execute(self, tool_name, arguments, tool_call_id=None):
            captured["tool_name"] = tool_name
            captured["tool_call_id"] = tool_call_id
            return ToolResult(
                success=True,
                data={
                    "action": "async_create_learning_space",
                    "tool_call_id": tool_call_id,
                    "space_id": str(uuid4()),
                },
                message="学习空间创建请求已受理，正在后台生成知识图谱…",
            )

        monkeypatch.setattr(LearningSpaceToolExecutor, "execute", mock_execute)

        response = await quick_chat_client.post(
            f"/api/quick-chat/conversations/{conversation_id}/tools/{tool_call_id}/confirm",
            json={
                "tool_name": "create_learning_space",
                "arguments": {
                    "name": "Python",
                    "learning_preferences": {
                        "preset_preferences": ["quick"],
                    },
                },
                "confirmed": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "accepted"
        assert body["success"] is True
        assert body["data"]["action"] == "async_create_learning_space"
        assert captured["tool_name"] == "create_learning_space"
        assert captured["tool_call_id"] == tool_call_id

    @pytest.mark.asyncio
    async def test_confirm_create_space_existing_task_returns_accepted(
        self, quick_chat_client: AsyncClient, monkeypatch
    ):
        conversation_id = uuid4()
        tool_call_id = "call_create_2"

        async def mock_execute(self, tool_name, arguments, tool_call_id=None):
            return ToolResult(
                success=False,
                data={
                    "action": "existing_running_task",
                    "existing_task_id": str(uuid4()),
                    "existing_tool_call_id": "call_existing_1",
                    "existing_stage": "kg_running",
                },
                message="当前对话已有一个学习空间创建任务正在进行中",
            )

        monkeypatch.setattr(LearningSpaceToolExecutor, "execute", mock_execute)

        response = await quick_chat_client.post(
            f"/api/quick-chat/conversations/{conversation_id}/tools/{tool_call_id}/confirm",
            json={
                "tool_name": "create_learning_space",
                "arguments": {
                    "name": "Java",
                    "learning_preferences": {
                        "preset_preferences": ["solid"],
                    },
                },
                "confirmed": True,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "accepted"
        assert body["success"] is False
        assert body["data"]["action"] == "existing_running_task"


class TestQuickChatToolTaskEndpoints:
    """Tests for async tool task endpoints."""

    @pytest.mark.asyncio
    async def test_list_tasks_endpoint(
        self, quick_chat_client: AsyncClient, monkeypatch
    ):
        conversation_id = uuid4()

        async def mock_list_tool_tasks(self):
            return ToolResult(
                success=True,
                data={
                    "tasks": [
                        {
                            "tool_call_id": "call_1",
                            "status": "running",
                            "stage": "kg_running",
                        }
                    ],
                    "count": 1,
                },
                message="任务列表获取成功",
            )

        monkeypatch.setattr(
            LearningSpaceToolExecutor,
            "list_tool_tasks",
            mock_list_tool_tasks,
        )

        response = await quick_chat_client.get(
            f"/api/quick-chat/conversations/{conversation_id}/tools/tasks"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["count"] == 1
        assert body["data"]["tasks"][0]["tool_call_id"] == "call_1"

    @pytest.mark.asyncio
    async def test_get_task_status_endpoint(
        self, quick_chat_client: AsyncClient, monkeypatch
    ):
        conversation_id = uuid4()
        tool_call_id = "call_status_1"

        async def mock_get_tool_task_status(self, task_tool_call_id):
            assert task_tool_call_id == tool_call_id
            return ToolResult(
                success=True,
                data={
                    "tool_call_id": tool_call_id,
                    "status": "running",
                    "stage": "kg_running",
                    "can_bind": False,
                },
                message="任务状态获取成功",
            )

        monkeypatch.setattr(
            LearningSpaceToolExecutor,
            "get_tool_task_status",
            mock_get_tool_task_status,
        )

        response = await quick_chat_client.get(
            f"/api/quick-chat/conversations/{conversation_id}/tools/{tool_call_id}/status"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["stage"] == "kg_running"

    @pytest.mark.asyncio
    async def test_bind_task_endpoint_failure_payload(
        self, quick_chat_client: AsyncClient, monkeypatch
    ):
        conversation_id = uuid4()
        tool_call_id = "call_bind_1"

        async def mock_bind_tool_task(self, task_tool_call_id):
            assert task_tool_call_id == tool_call_id
            return ToolResult(
                success=False,
                data={
                    "tool_call_id": tool_call_id,
                    "status": "failed",
                    "stage": "binding_failed",
                    "error_stage": "binding",
                    "error_code": "BINDING_FAILED",
                    "error_message": "绑定学习空间失败",
                },
                message="绑定学习空间失败",
            )

        monkeypatch.setattr(
            LearningSpaceToolExecutor,
            "bind_tool_task",
            mock_bind_tool_task,
        )

        response = await quick_chat_client.post(
            f"/api/quick-chat/conversations/{conversation_id}/tools/{tool_call_id}/bind"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["data"]["error_stage"] == "binding"
