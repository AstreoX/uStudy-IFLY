"""Quiz API 端点集成测试"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agents.router import router
from agents.schemas import AgentTaskStatusEnum
from auth.dependencies import get_current_user
from db.database import get_db
from db.models import AgentTask, AgentTaskStatus, AgentTaskType, Space, User


@pytest.fixture
def app() -> FastAPI:
    """创建测试用 FastAPI 应用"""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


class TestGenerateQuizEndpoint:
    """POST /api/agents/quiz 测试"""

    @pytest_asyncio.fixture
    async def authenticated_client(
        self, app: FastAPI, db_session: AsyncSession, test_user: User
    ):
        """创建已认证的测试客户端"""
        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_success_202(
        self,
        authenticated_client: AsyncClient,
        test_space: Space,
    ):
        """成功返回 202"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            response = await authenticated_client.post(
                "/api/agents/quiz",
                params={"space_id": str(test_space.id)},
                json={
                    "topic": "Python 基础",
                    "difficulty_level": "medium",
                    "test_struct": [
                        {"question_type": "single_choice", "question_num": 3},
                    ],
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert data["task_type"] == "generate_quiz"

    @pytest.mark.asyncio
    async def test_missing_space_id(self, authenticated_client: AsyncClient):
        """缺少 space_id 返回 422"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            json={
                "topic": "Python 基础",
                "difficulty_level": "medium",
                "test_struct": [
                    {"question_type": "single_choice", "question_num": 3},
                ],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_space_id(self, authenticated_client: AsyncClient):
        """无效 space_id 返回 404"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            params={"space_id": str(uuid4())},
            json={
                "topic": "Python 基础",
                "difficulty_level": "medium",
                "test_struct": [
                    {"question_type": "single_choice", "question_num": 3},
                ],
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "SPACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_no_permission(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        test_space: Space,
    ):
        """无权限返回 403"""
        # 创建另一个用户
        other_user = User(
            id=uuid4(),
            email="no_permission@test.com",
            nickname="No Permission User",
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
            response = await client.post(
                "/api/agents/quiz",
                params={"space_id": str(test_space.id)},
                json={
                    "topic": "Python 基础",
                    "difficulty_level": "medium",
                    "test_struct": [
                        {"question_type": "single_choice", "question_num": 3},
                    ],
                },
            )

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "SPACE_ACCESS_DENIED"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_unauthorized(
        self, app: FastAPI, db_session: AsyncSession, test_space: Space
    ):
        """未认证返回 401"""
        app.dependency_overrides[get_db] = lambda: db_session

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/agents/quiz",
                params={"space_id": str(test_space.id)},
                json={
                    "topic": "Python 基础",
                    "difficulty_level": "medium",
                    "test_struct": [
                        {"question_type": "single_choice", "question_num": 3},
                    ],
                },
            )

        assert response.status_code == 401

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_invalid_difficulty(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """无效难度返回 422"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            params={"space_id": str(test_space.id)},
            json={
                "topic": "Python 基础",
                "difficulty_level": "invalid",
                "test_struct": [
                    {"question_type": "single_choice", "question_num": 3},
                ],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_question_type(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """无效题型返回 422"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            params={"space_id": str(test_space.id)},
            json={
                "topic": "Python 基础",
                "difficulty_level": "medium",
                "test_struct": [
                    {"question_type": "invalid_type", "question_num": 3},
                ],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_question_num_too_small(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """数量太小返回 422"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            params={"space_id": str(test_space.id)},
            json={
                "topic": "Python 基础",
                "difficulty_level": "medium",
                "test_struct": [
                    {"question_type": "single_choice", "question_num": 0},
                ],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_question_num_too_large(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """数量太大返回 422"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            params={"space_id": str(test_space.id)},
            json={
                "topic": "Python 基础",
                "difficulty_level": "medium",
                "test_struct": [
                    {"question_type": "single_choice", "question_num": 100},
                ],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_test_struct_empty(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """空 test_struct 返回 422"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            params={"space_id": str(test_space.id)},
            json={
                "topic": "Python 基础",
                "difficulty_level": "medium",
                "test_struct": [],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_response_format(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """响应格式验证"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            response = await authenticated_client.post(
                "/api/agents/quiz",
                params={"space_id": str(test_space.id)},
                json={
                    "topic": "Python 基础",
                    "difficulty_level": "easy",
                    "test_struct": [
                        {"question_type": "single_choice", "question_num": 2},
                        {"question_type": "true_false", "question_num": 1},
                    ],
                },
            )

        data = response.json()

        # 验证响应包含所有必需字段
        assert "task_id" in data
        assert "status" in data
        assert "task_type" in data
        assert "created_at" in data

        # 验证字段类型
        assert isinstance(data["task_id"], str)
        assert data["status"] in ["pending", "running", "done", "failed"]
        assert data["task_type"] == "generate_quiz"

    @pytest.mark.asyncio
    async def test_all_question_types(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """所有题型"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            response = await authenticated_client.post(
                "/api/agents/quiz",
                params={"space_id": str(test_space.id)},
                json={
                    "topic": "综合测试",
                    "difficulty_level": "hard",
                    "test_struct": [
                        {"question_type": "single_choice", "question_num": 3},
                        {"question_type": "multiple_choice", "question_num": 2},
                        {"question_type": "true_false", "question_num": 4},
                        {"question_type": "short_answer", "question_num": 1},
                    ],
                },
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_all_difficulty_levels(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """所有难度级别"""
        for difficulty in ["easy", "medium", "hard"]:
            with patch("asyncio.create_task") as mock_create_task:
                mock_task = MagicMock()
                mock_task.add_done_callback = MagicMock()
                mock_create_task.return_value = mock_task

                response = await authenticated_client.post(
                    "/api/agents/quiz",
                    params={"space_id": str(test_space.id)},
                    json={
                        "topic": "测试",
                        "difficulty_level": difficulty,
                        "test_struct": [
                            {"question_type": "single_choice", "question_num": 1},
                        ],
                    },
                )

            assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_missing_topic(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """缺少 topic 返回 422"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            params={"space_id": str(test_space.id)},
            json={
                "difficulty_level": "medium",
                "test_struct": [
                    {"question_type": "single_choice", "question_num": 3},
                ],
            },
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_topic(
        self, authenticated_client: AsyncClient, test_space: Space
    ):
        """空 topic 返回 422"""
        response = await authenticated_client.post(
            "/api/agents/quiz",
            params={"space_id": str(test_space.id)},
            json={
                "topic": "",
                "difficulty_level": "medium",
                "test_struct": [
                    {"question_type": "single_choice", "question_num": 3},
                ],
            },
        )

        assert response.status_code == 422


class TestGetTaskStatusEndpoint:
    """GET /api/agents/tasks/{task_id} 测试"""

    @pytest_asyncio.fixture
    async def authenticated_client(
        self, app: FastAPI, db_session: AsyncSession, test_user: User
    ):
        """创建已认证的测试客户端"""
        async def mock_get_user():
            return test_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = mock_get_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

        app.dependency_overrides.clear()

    @pytest_asyncio.fixture
    async def completed_task(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ) -> AgentTask:
        """创建已完成的任务"""
        quiz_id = uuid4()
        task = AgentTask(
            id=uuid4(),
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_QUIZ,
            status=AgentTaskStatus.DONE,
            input_data={"topic": "测试"},
            output_data={
                "quiz_id": str(quiz_id),
                "expected_count": 5,
                "question_count": 5,
            },
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()
        return task

    @pytest.mark.asyncio
    async def test_success(
        self, authenticated_client: AsyncClient, completed_task: AgentTask
    ):
        """成功查询"""
        response = await authenticated_client.get(
            f"/api/agents/tasks/{completed_task.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == str(completed_task.id)
        assert data["status"] == "done"

    @pytest.mark.asyncio
    async def test_task_not_found(self, authenticated_client: AsyncClient):
        """任务不存在返回 404"""
        response = await authenticated_client.get(f"/api/agents/tasks/{uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "TASK_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_unauthorized(
        self, app: FastAPI, db_session: AsyncSession, completed_task: AgentTask
    ):
        """未认证返回 401"""
        app.dependency_overrides[get_db] = lambda: db_session

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/agents/tasks/{completed_task.id}")

        assert response.status_code == 401

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_response_includes_quiz_id(
        self, authenticated_client: AsyncClient, completed_task: AgentTask
    ):
        """响应包含 quiz_id"""
        response = await authenticated_client.get(
            f"/api/agents/tasks/{completed_task.id}"
        )

        data = response.json()
        assert "quiz_id" in data
        assert data["quiz_id"] is not None

    @pytest.mark.asyncio
    async def test_response_includes_counts(
        self, authenticated_client: AsyncClient, completed_task: AgentTask
    ):
        """响应包含数量信息"""
        response = await authenticated_client.get(
            f"/api/agents/tasks/{completed_task.id}"
        )

        data = response.json()
        assert "question_count" in data
        assert data["question_count"] == 5

    @pytest.mark.asyncio
    async def test_response_format(
        self, authenticated_client: AsyncClient, completed_task: AgentTask
    ):
        """响应格式验证"""
        response = await authenticated_client.get(
            f"/api/agents/tasks/{completed_task.id}"
        )

        data = response.json()

        # 验证响应包含所有字段
        expected_fields = [
            "task_id",
            "status",
            "task_type",
            "space_id",
            "error_message",
            "node_count",
            "edge_count",
            "quiz_id",
            "question_count",
            "created_at",
            "started_at",
            "completed_at",
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_user_cannot_access_others_task(
        self,
        app: FastAPI,
        db_session: AsyncSession,
        completed_task: AgentTask,
    ):
        """用户不能访问他人的任务"""
        # 创建另一个用户
        other_user = User(
            id=uuid4(),
            email="other_task@test.com",
            nickname="Other Task User",
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
            response = await client.get(f"/api/agents/tasks/{completed_task.id}")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "TASK_NOT_FOUND"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_invalid_task_id_format(self, authenticated_client: AsyncClient):
        """无效的 task_id 格式返回 422"""
        response = await authenticated_client.get("/api/agents/tasks/invalid-uuid")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_pending_task_status(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """查询 PENDING 状态任务"""
        task = AgentTask(
            id=uuid4(),
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_QUIZ,
            status=AgentTaskStatus.PENDING,
            input_data={"topic": "测试"},
        )
        db_session.add(task)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/agents/tasks/{task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["started_at"] is None
        assert data["completed_at"] is None

    @pytest.mark.asyncio
    async def test_failed_task_status(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """查询 FAILED 状态任务"""
        task = AgentTask(
            id=uuid4(),
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_QUIZ,
            status=AgentTaskStatus.FAILED,
            input_data={"topic": "测试"},
            error_message="生成失败",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/agents/tasks/{task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "生成失败"
