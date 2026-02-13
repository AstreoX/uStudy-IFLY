"""Agent API 端点集成测试"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agents.router import router
from agents.schemas import AgentTaskStatusEnum
from db.database import get_db
from db.models import AgentTask, AgentTaskStatus, AgentTaskType, Space, User


@pytest.fixture
def app() -> FastAPI:
    """创建测试用 FastAPI 应用"""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


class TestAuthenticationIntegration:
    """认证集成测试"""

    @pytest.mark.asyncio
    async def test_unauthorized_without_token(
        self, app: FastAPI, db_session: AsyncSession
    ):
        """测试无 token 返回 401"""
        # 重写依赖
        app.dependency_overrides[get_db] = lambda: db_session

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/knowledge-graph",
                params={"space_id": str(uuid4())},
                json={"topic": "Test Topic"},
            )

            assert response.status_code == 401
            assert response.json()["detail"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(
        self, app: FastAPI, db_session: AsyncSession
    ):
        """测试无效 token 返回 401"""
        app.dependency_overrides[get_db] = lambda: db_session

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/knowledge-graph",
                params={"space_id": str(uuid4())},
                json={"topic": "Test Topic"},
                headers={"Authorization": "Bearer invalid_token"},
            )

            assert response.status_code == 401


class TestPermissionIntegration:
    """权限集成测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="permission@test.com",
            nickname="Permission User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def other_user(self, db_session: AsyncSession) -> User:
        """创建另一个用户"""
        user = User(
            id=uuid4(),
            email="other@test.com",
            nickname="Other User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def test_space(self, db_session: AsyncSession, test_user: User) -> Space:
        """创建测试学习空间"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Permission Space",
            color="#0000FF",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    async def test_access_denied_other_user_space(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
        test_space: Space,
    ):
        """测试访问他人空间返回 403"""
        from agents.router import get_current_user

        # Mock 认证返回 other_user
        async def mock_get_user():
            return other_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/knowledge-graph",
                params={"space_id": str(test_space.id)},
                json={"topic": "Test Topic"},
            )

            assert response.status_code == 403
            assert response.json()["detail"]["code"] == "SPACE_ACCESS_DENIED"

        # 清理
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_space_not_found_404(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
    ):
        """测试空间不存在返回 404"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/knowledge-graph",
                params={"space_id": str(uuid4())},  # 不存在的空间
                json={"topic": "Test Topic"},
            )

            assert response.status_code == 404
            assert response.json()["detail"]["code"] == "SPACE_NOT_FOUND"

        app.dependency_overrides.clear()


class TestTaskCreationIntegration:
    """任务创建集成测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="task@test.com",
            nickname="Task User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def test_space(self, db_session: AsyncSession, test_user: User) -> Space:
        """创建测试学习空间"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Task Space",
            color="#FF00FF",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    async def test_create_task_returns_202(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试创建任务返回 202 + task_id"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        # Mock 后台任务执行
        with patch("agents.service.asyncio.create_task") as mock_create_task:
            mock_create_task.return_value = MagicMock()
            mock_create_task.return_value.add_done_callback = MagicMock()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/agents/knowledge-graph",
                    params={"space_id": str(test_space.id)},
                    json={"topic": "Test Topic"},
                )

                assert response.status_code == 202
                data = response.json()
                assert "task_id" in data
                assert data["status"] == "pending"
                assert data["task_type"] == "generate_knowledge_graph"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_task_status_initially_pending(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试任务初始状态为 pending"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        with patch("agents.service.asyncio.create_task") as mock_create_task:
            mock_create_task.return_value = MagicMock()
            mock_create_task.return_value.add_done_callback = MagicMock()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/agents/knowledge-graph",
                    params={"space_id": str(test_space.id)},
                    json={"topic": "Test Topic"},
                )

                assert response.json()["status"] == "pending"

        app.dependency_overrides.clear()


class TestTaskQueryIntegration:
    """任务查询集成测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="query@test.com",
            nickname="Query User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def test_space(self, db_session: AsyncSession, test_user: User) -> Space:
        """创建测试学习空间"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Query Space",
            color="#FFFF00",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest_asyncio.fixture
    async def test_task(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ) -> AgentTask:
        """创建测试任务"""
        task = AgentTask(
            id=uuid4(),
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            status=AgentTaskStatus.DONE,
            input_data={"topic": "Test", "user_preference": None},
            output_data={"space_id": str(test_space.id), "node_count": 5, "edge_count": 4},
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()
        return task

    @pytest.mark.asyncio
    async def test_get_task_status(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_task: AgentTask,
    ):
        """测试查询任务状态"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/agents/tasks/{test_task.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == str(test_task.id)
            assert data["status"] == "done"
            assert data["node_count"] == 5
            assert data["edge_count"] == 4

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_task_not_found(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
    ):
        """测试任务不存在返回 404"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/agents/tasks/{uuid4()}")

            assert response.status_code == 404
            assert response.json()["detail"]["code"] == "TASK_NOT_FOUND"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_other_user_task_denied(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_task: AgentTask,
    ):
        """测试访问他人任务返回 404（实际上是查不到）"""
        from agents.router import get_current_user

        other_user = User(
            id=uuid4(),
            email="other_query@test.com",
            nickname="Other Query User",
        )
        db_session.add(other_user)
        await db_session.commit()

        async def mock_get_other_user():
            return other_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_other_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # 使用另一个用户查询 test_user 的任务
            response = await client.get(f"/api/agents/tasks/{test_task.id}")

            # 因为查询条件包含 user_id，所以其他用户查不到，返回 404
            assert response.status_code == 404

        app.dependency_overrides.clear()


class TestRequestValidation:
    """请求验证测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="validation@test.com",
            nickname="Validation User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def test_space(self, db_session: AsyncSession, test_user: User) -> Space:
        """创建测试学习空间"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Validation Space",
            color="#00FFFF",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    async def test_missing_space_id(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
    ):
        """测试缺少 space_id 参数"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/knowledge-graph",
                json={"topic": "Test Topic"},
            )

            assert response.status_code == 422  # Validation Error

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_empty_topic(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试空 topic"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/knowledge-graph",
                params={"space_id": str(test_space.id)},
                json={"topic": ""},
            )

            assert response.status_code == 422

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_topic_too_long(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试 topic 过长"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/knowledge-graph",
                params={"space_id": str(test_space.id)},
                json={"topic": "a" * 501},
            )

            assert response.status_code == 422

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_invalid_space_id_format(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_user: User,
    ):
        """测试无效的 space_id 格式"""
        from agents.router import get_current_user

        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/knowledge-graph",
                params={"space_id": "not-a-valid-uuid"},
                json={"topic": "Test Topic"},
            )

            assert response.status_code == 422

        app.dependency_overrides.clear()
