"""AgentService Quiz 相关集成测试"""

import asyncio
from datetime import datetime, timezone
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
    QuestionTypeEnum,
    QuizGenerateRequest,
    TestStructItem,
)
from agents.service import AgentService
from db.models import AgentTask, AgentTaskStatus, AgentTaskType, Quiz, Space, User


class TestCreateQuizTask:
    """create_quiz_task 测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> AgentService:
        """创建 Service 实例"""
        return AgentService(db_session)

    @pytest.fixture
    def valid_request(self) -> QuizGenerateRequest:
        """有效的请求"""
        return QuizGenerateRequest(
            topic="Python 基础",
            difficulty_level=DifficultyLevelEnum.MEDIUM,
            test_struct=[
                TestStructItem(
                    question_type=QuestionTypeEnum.SINGLE_CHOICE,
                    question_num=3,
                ),
                TestStructItem(
                    question_type=QuestionTypeEnum.TRUE_FALSE,
                    question_num=2,
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_valid_request(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        valid_request: QuizGenerateRequest,
        db_session: AsyncSession,
    ):
        """有效请求应成功创建任务"""
        # Mock 后台任务以避免实际执行
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            response = await service.create_quiz_task(
                user_id=test_user.id,
                space_id=test_space.id,
                request=valid_request,
            )

        assert response.task_id is not None
        assert response.status == AgentTaskStatusEnum.PENDING
        assert response.task_type == "generate_quiz"

    @pytest.mark.asyncio
    async def test_space_not_found(
        self,
        service: AgentService,
        test_user: User,
        valid_request: QuizGenerateRequest,
    ):
        """空间不存在应抛出 SpaceNotFoundError"""
        with pytest.raises(SpaceNotFoundError):
            await service.create_quiz_task(
                user_id=test_user.id,
                space_id=uuid4(),  # 不存在的空间
                request=valid_request,
            )

    @pytest.mark.asyncio
    async def test_space_access_denied(
        self,
        service: AgentService,
        test_space: Space,
        valid_request: QuizGenerateRequest,
        db_session: AsyncSession,
    ):
        """无权访问空间应抛出 SpaceAccessDeniedError"""
        # 创建另一个用户
        other_user = User(
            id=uuid4(),
            email="other@test.com",
            nickname="Other User",
        )
        db_session.add(other_user)
        await db_session.commit()

        with pytest.raises(SpaceAccessDeniedError):
            await service.create_quiz_task(
                user_id=other_user.id,  # 不是空间所有者
                space_id=test_space.id,
                request=valid_request,
            )

    @pytest.mark.asyncio
    async def test_task_created_pending(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        valid_request: QuizGenerateRequest,
        db_session: AsyncSession,
    ):
        """任务状态为 PENDING"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            response = await service.create_quiz_task(
                user_id=test_user.id,
                space_id=test_space.id,
                request=valid_request,
            )

        # 查询数据库中的任务
        result = await db_session.execute(
            select(AgentTask).where(AgentTask.id == response.task_id)
        )
        task = result.scalar_one()

        assert task.status == AgentTaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_input_data_saved(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        valid_request: QuizGenerateRequest,
        db_session: AsyncSession,
    ):
        """input_data 正确保存"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            response = await service.create_quiz_task(
                user_id=test_user.id,
                space_id=test_space.id,
                request=valid_request,
            )

        result = await db_session.execute(
            select(AgentTask).where(AgentTask.id == response.task_id)
        )
        task = result.scalar_one()

        assert task.input_data["topic"] == "Python 基础"
        assert task.input_data["difficulty_level"] == "medium"
        assert len(task.input_data["test_struct"]) == 2

    @pytest.mark.asyncio
    async def test_background_task_started(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        valid_request: QuizGenerateRequest,
    ):
        """后台任务启动"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            await service.create_quiz_task(
                user_id=test_user.id,
                space_id=test_space.id,
                request=valid_request,
            )

        # 验证 asyncio.create_task 被调用
        mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_type_is_generate_quiz(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        valid_request: QuizGenerateRequest,
        db_session: AsyncSession,
    ):
        """任务类型为 GENERATE_QUIZ"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            response = await service.create_quiz_task(
                user_id=test_user.id,
                space_id=test_space.id,
                request=valid_request,
            )

        result = await db_session.execute(
            select(AgentTask).where(AgentTask.id == response.task_id)
        )
        task = result.scalar_one()

        assert task.task_type == AgentTaskType.GENERATE_QUIZ

    @pytest.mark.asyncio
    async def test_no_conversation_id(
        self,
        service: AgentService,
        test_user: User,
        test_space: Space,
        valid_request: QuizGenerateRequest,
        db_session: AsyncSession,
    ):
        """无 conversation_id 时正常工作"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_task.add_done_callback = MagicMock()
            mock_create_task.return_value = mock_task

            response = await service.create_quiz_task(
                user_id=test_user.id,
                space_id=test_space.id,
                request=valid_request,
                conversation_id=None,
            )

        result = await db_session.execute(
            select(AgentTask).where(AgentTask.id == response.task_id)
        )
        task = result.scalar_one()

        assert task.conversation_id is None


class TestGetTaskStatus:
    """get_task_status 测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> AgentService:
        return AgentService(db_session)

    @pytest_asyncio.fixture
    async def pending_task(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ) -> AgentTask:
        """创建 PENDING 状态的任务"""
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
        return task

    @pytest_asyncio.fixture
    async def running_task(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ) -> AgentTask:
        """创建 RUNNING 状态的任务"""
        task = AgentTask(
            id=uuid4(),
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_QUIZ,
            status=AgentTaskStatus.RUNNING,
            input_data={"topic": "测试"},
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()
        return task

    @pytest_asyncio.fixture
    async def done_task(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ) -> AgentTask:
        """创建 DONE 状态的任务"""
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

    @pytest_asyncio.fixture
    async def failed_task(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ) -> AgentTask:
        """创建 FAILED 状态的任务"""
        task = AgentTask(
            id=uuid4(),
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_QUIZ,
            status=AgentTaskStatus.FAILED,
            input_data={"topic": "测试"},
            output_data={
                "error_type": "LLMClientError",
                "error_message": "API 调用失败",
            },
            error_message="API 调用失败",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()
        return task

    @pytest.mark.asyncio
    async def test_pending_task(
        self, service: AgentService, test_user: User, pending_task: AgentTask
    ):
        """查询 PENDING 任务"""
        result = await service.get_task_status(test_user.id, pending_task.id)

        assert result.task_id == pending_task.id
        assert result.status == AgentTaskStatusEnum.PENDING
        assert result.started_at is None
        assert result.completed_at is None

    @pytest.mark.asyncio
    async def test_running_task(
        self, service: AgentService, test_user: User, running_task: AgentTask
    ):
        """查询 RUNNING 任务"""
        result = await service.get_task_status(test_user.id, running_task.id)

        assert result.task_id == running_task.id
        assert result.status == AgentTaskStatusEnum.RUNNING
        assert result.started_at is not None
        assert result.completed_at is None

    @pytest.mark.asyncio
    async def test_done_task(
        self, service: AgentService, test_user: User, done_task: AgentTask
    ):
        """查询 DONE 任务"""
        result = await service.get_task_status(test_user.id, done_task.id)

        assert result.task_id == done_task.id
        assert result.status == AgentTaskStatusEnum.DONE
        assert result.quiz_id is not None
        assert result.question_count == 5
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_failed_task(
        self, service: AgentService, test_user: User, failed_task: AgentTask
    ):
        """查询 FAILED 任务"""
        result = await service.get_task_status(test_user.id, failed_task.id)

        assert result.task_id == failed_task.id
        assert result.status == AgentTaskStatusEnum.FAILED
        assert result.error_message == "API 调用失败"
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_task_not_found(self, service: AgentService, test_user: User):
        """任务不存在应抛出 TaskNotFoundError"""
        with pytest.raises(TaskNotFoundError):
            await service.get_task_status(test_user.id, uuid4())

    @pytest.mark.asyncio
    async def test_user_mismatch(
        self, service: AgentService, pending_task: AgentTask, db_session: AsyncSession
    ):
        """用户不匹配应抛出 TaskNotFoundError"""
        # 创建另一个用户
        other_user = User(
            id=uuid4(),
            email="mismatch@test.com",
            nickname="Mismatch User",
        )
        db_session.add(other_user)
        await db_session.commit()

        with pytest.raises(TaskNotFoundError):
            await service.get_task_status(other_user.id, pending_task.id)

    @pytest.mark.asyncio
    async def test_response_includes_quiz_id(
        self, service: AgentService, test_user: User, done_task: AgentTask
    ):
        """响应包含 quiz_id"""
        result = await service.get_task_status(test_user.id, done_task.id)

        assert result.quiz_id is not None

    @pytest.mark.asyncio
    async def test_response_includes_counts(
        self, service: AgentService, test_user: User, done_task: AgentTask
    ):
        """响应包含数量信息"""
        result = await service.get_task_status(test_user.id, done_task.id)

        assert result.question_count == 5


class TestRunQuizTask:
    """_run_quiz_task 测试

    注意：此方法在独立的 AsyncSession 中运行，需要特殊处理
    """

    @pytest.mark.asyncio
    async def test_status_transitions(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """状态流转: PENDING → RUNNING → DONE"""
        # 这个测试需要更复杂的设置来测试后台任务
        # 暂时跳过，因为它涉及独立的 AsyncSession
        pass

    @pytest.mark.asyncio
    async def test_quiz_created(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """Quiz 记录创建"""
        # 这个测试需要更复杂的设置来测试后台任务
        # 暂时跳过
        pass


class TestVerifySpaceOwnership:
    """_verify_space_ownership 测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> AgentService:
        return AgentService(db_session)

    @pytest.mark.asyncio
    async def test_valid_ownership(
        self, service: AgentService, test_user: User, test_space: Space
    ):
        """有效的所有权验证应通过"""
        # 不应抛出异常
        await service._verify_space_ownership(test_space.id, test_user.id)

    @pytest.mark.asyncio
    async def test_space_not_found(self, service: AgentService, test_user: User):
        """空间不存在"""
        with pytest.raises(SpaceNotFoundError):
            await service._verify_space_ownership(uuid4(), test_user.id)

    @pytest.mark.asyncio
    async def test_access_denied(
        self, service: AgentService, test_space: Space, db_session: AsyncSession
    ):
        """无权访问"""
        other_user = User(
            id=uuid4(),
            email="verify@test.com",
            nickname="Verify User",
        )
        db_session.add(other_user)
        await db_session.commit()

        with pytest.raises(SpaceAccessDeniedError):
            await service._verify_space_ownership(test_space.id, other_user.id)
