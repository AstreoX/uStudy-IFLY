"""AgentService 单元测试"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.exceptions import SpaceAccessDeniedError, SpaceNotFoundError, TaskNotFoundError
from agents.schemas import (
    AgentTaskStatusEnum,
    DifficultyLevelEnum,
    KnowledgeGraphGenerateRequest,
    QuestionTypeEnum,
    QuizGenerateRequest,
    TestStructItem,
)
from agents.service import AgentService, _truncate_debug_logs
from db.models import AgentTask, AgentTaskStatus, AgentTaskType, Space, User


class TestAgentServiceTaskCreation:
    """任务创建测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> AgentService:
        return AgentService(db_session)

    @pytest.mark.asyncio
    async def test_create_kg_task_success(
        self,
        service: AgentService,
        test_space: Space,
        test_user: User,
        db_session: AsyncSession,
    ):
        """成功创建知识图谱任务"""
        request = KnowledgeGraphGenerateRequest(
            topic="Python 基础",
            user_preference="适合初学者",
        )

        # Mock KnowledgeGraphAgent 避免真正调用 LLM
        with patch("agents.service.KnowledgeGraphAgent") as mock_agent_class:
            mock_agent = AsyncMock()
            mock_agent.generate.return_value = (test_space.id, 10, 9)
            mock_agent_class.return_value = mock_agent

            response = await service.create_knowledge_graph_task(
                user_id=test_user.id,
                space_id=test_space.id,
                request=request,
            )

            # 让后台任务有机会执行
            await asyncio.sleep(0.1)

        assert response.task_id is not None
        assert response.status == AgentTaskStatusEnum.PENDING
        assert response.task_type == AgentTaskType.GENERATE_KNOWLEDGE_GRAPH.value

    @pytest.mark.asyncio
    async def test_create_kg_task_space_not_found(
        self,
        service: AgentService,
        test_user: User,
    ):
        """学习空间不存在"""
        request = KnowledgeGraphGenerateRequest(topic="Python")
        fake_space_id = uuid4()

        with pytest.raises(SpaceNotFoundError):
            await service.create_knowledge_graph_task(
                user_id=test_user.id,
                space_id=fake_space_id,
                request=request,
            )

    @pytest.mark.asyncio
    async def test_create_kg_task_space_access_denied(
        self,
        service: AgentService,
        test_space: Space,
        db_session: AsyncSession,
    ):
        """无权访问学习空间"""
        # 创建另一个用户
        other_user = User(id=uuid4(), email="other@test.com", nickname="Other")
        db_session.add(other_user)
        await db_session.commit()

        request = KnowledgeGraphGenerateRequest(topic="Python")

        with pytest.raises(SpaceAccessDeniedError):
            await service.create_knowledge_graph_task(
                user_id=other_user.id,
                space_id=test_space.id,
                request=request,
            )

    @pytest.mark.asyncio
    async def test_create_quiz_task_success(
        self,
        service: AgentService,
        test_space: Space,
        test_user: User,
    ):
        """成功创建测试生成任务"""
        request = QuizGenerateRequest(
            topic="Python 基础",
            difficulty_level=DifficultyLevelEnum.MEDIUM,
            test_struct=[
                TestStructItem(question_type=QuestionTypeEnum.SINGLE_CHOICE, question_num=3),
                TestStructItem(question_type=QuestionTypeEnum.TRUE_FALSE, question_num=2),
            ],
        )

        with patch("agents.service.TestGenerationAgent") as mock_agent_class:
            mock_agent = AsyncMock()
            mock_agent.generate.return_value = (5, 5, [])
            mock_agent_class.return_value = mock_agent

            response = await service.create_quiz_task(
                user_id=test_user.id,
                space_id=test_space.id,
                request=request,
            )

            await asyncio.sleep(0.1)

        assert response.task_id is not None
        assert response.status == AgentTaskStatusEnum.PENDING
        assert response.task_type == AgentTaskType.GENERATE_QUIZ.value


class TestAgentServiceTaskStatus:
    """任务状态查询测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> AgentService:
        return AgentService(db_session)

    @pytest.mark.asyncio
    async def test_get_task_status_pending(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        db_session: AsyncSession,
    ):
        """获取待处理任务状态"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            status=AgentTaskStatus.PENDING,
            input_data={"topic": "Test"},
        )
        db_session.add(task)
        await db_session.commit()

        result = await service.get_task_status(test_user.id, task.id)

        assert result.status == AgentTaskStatusEnum.PENDING
        assert result.task_id == task.id

    @pytest.mark.asyncio
    async def test_get_task_status_running(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        db_session: AsyncSession,
    ):
        """获取运行中任务状态"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            status=AgentTaskStatus.RUNNING,
            input_data={"topic": "Test"},
        )
        db_session.add(task)
        await db_session.commit()

        result = await service.get_task_status(test_user.id, task.id)

        assert result.status == AgentTaskStatusEnum.RUNNING

    @pytest.mark.asyncio
    async def test_get_task_status_done(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        db_session: AsyncSession,
    ):
        """获取已完成任务状态"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            status=AgentTaskStatus.DONE,
            input_data={"topic": "Test"},
            output_data={
                "space_id": str(test_space.id),
                "node_count": 10,
                "edge_count": 9,
            },
        )
        db_session.add(task)
        await db_session.commit()

        result = await service.get_task_status(test_user.id, task.id)

        assert result.status == AgentTaskStatusEnum.DONE
        assert result.node_count == 10
        assert result.edge_count == 9
        assert result.space_id == test_space.id

    @pytest.mark.asyncio
    async def test_get_task_status_failed(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        db_session: AsyncSession,
    ):
        """获取失败任务状态"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            status=AgentTaskStatus.FAILED,
            input_data={"topic": "Test"},
            error_message="LLM API 调用失败",
        )
        db_session.add(task)
        await db_session.commit()

        result = await service.get_task_status(test_user.id, task.id)

        assert result.status == AgentTaskStatusEnum.FAILED
        assert result.error_message == "LLM API 调用失败"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(
        self,
        service: AgentService,
        test_user: User,
    ):
        """任务不存在"""
        fake_task_id = uuid4()

        with pytest.raises(TaskNotFoundError):
            await service.get_task_status(test_user.id, fake_task_id)

    @pytest.mark.asyncio
    async def test_get_task_status_wrong_user(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        db_session: AsyncSession,
    ):
        """非所有者访问任务"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            status=AgentTaskStatus.PENDING,
            input_data={"topic": "Test"},
        )
        db_session.add(task)
        await db_session.commit()

        # 用另一个用户 ID 访问
        other_user_id = uuid4()

        with pytest.raises(TaskNotFoundError):
            await service.get_task_status(other_user_id, task.id)

    @pytest.mark.asyncio
    async def test_get_task_status_with_quiz_data(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        db_session: AsyncSession,
    ):
        """获取带 Quiz 数据的任务状态"""
        quiz_id = uuid4()
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_QUIZ,
            status=AgentTaskStatus.DONE,
            input_data={"topic": "Test"},
            output_data={
                "quiz_id": str(quiz_id),
                "expected_count": 5,
                "question_count": 5,
                "debug_logs": [{"iteration": 1}],
            },
        )
        db_session.add(task)
        await db_session.commit()

        result = await service.get_task_status(test_user.id, task.id)

        assert result.quiz_id == quiz_id
        assert result.question_count == 5
        assert result.debug_logs is not None


class TestTruncateDebugLogs:
    """调试日志截断测试"""

    def test_truncate_empty_logs(self):
        """空日志不变"""
        assert _truncate_debug_logs([]) == []

    def test_truncate_small_logs(self):
        """小日志不变"""
        logs = [{"iteration": 1, "message": "test"}]
        result = _truncate_debug_logs(logs)
        assert result == logs

    def test_truncate_large_logs(self):
        """大日志截断"""
        # 创建超过 50KB 的日志
        large_log = {"data": "x" * 60000}
        logs = [large_log]

        result = _truncate_debug_logs(logs, max_size=1000)

        # 应该为空或只有截断说明
        assert len(result) <= 2

    def test_truncate_preserves_recent(self):
        """保留最新日志"""
        logs = [
            {"iteration": 1, "data": "old" * 1000},
            {"iteration": 2, "data": "middle" * 1000},
            {"iteration": 3, "data": "new"},
        ]

        result = _truncate_debug_logs(logs, max_size=500)

        # 最新的日志应该被保留
        if len(result) > 1:
            assert any("new" in str(log) for log in result)


class TestAgentServiceSpaceVerification:
    """空间验证测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> AgentService:
        return AgentService(db_session)

    @pytest.mark.asyncio
    async def test_verify_space_ownership_success(
        self,
        service: AgentService,
        test_space: Space,
        test_user: User,
    ):
        """验证空间所有权成功"""
        # 不应该抛出异常
        await service._verify_space_ownership(test_space.id, test_user.id)

    @pytest.mark.asyncio
    async def test_verify_space_ownership_not_found(
        self,
        service: AgentService,
        test_user: User,
    ):
        """空间不存在"""
        fake_space_id = uuid4()

        with pytest.raises(SpaceNotFoundError):
            await service._verify_space_ownership(fake_space_id, test_user.id)

    @pytest.mark.asyncio
    async def test_verify_space_ownership_access_denied(
        self,
        service: AgentService,
        test_space: Space,
    ):
        """无权访问"""
        other_user_id = uuid4()

        with pytest.raises(SpaceAccessDeniedError):
            await service._verify_space_ownership(test_space.id, other_user_id)
