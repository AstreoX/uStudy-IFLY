"""TestGenerationAgent 集成测试"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.test_generation_agent import MAX_LLM_ITERATIONS, TestGenerationAgent
from db.models import Question, QuestionType, Quiz


class TestGenerateWithMockLLM:
    """生成流程测试 (Mock LLM)"""

    @pytest_asyncio.fixture
    async def agent(self, db_session: AsyncSession) -> TestGenerationAgent:
        """创建 Agent 实例"""
        return TestGenerationAgent(db_session)

    @pytest.mark.asyncio
    async def test_successful_generation(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_multiple_tools_response,
        db_session: AsyncSession,
    ):
        """完整成功流程"""
        test_struct = [
            {"question_type": "single_choice", "question_num": 1},
            {"question_type": "true_false", "question_num": 1},
            {"question_type": "multiple_choice", "question_num": 1},
        ]

        # Mock LLM client
        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_multiple_tools_response

            expected, actual = await agent.generate(
                quiz_id=test_quiz.id,
                topic="Python 基础",
                difficulty="medium",
                test_struct=test_struct,
            )

        assert expected == 3
        assert actual == 3

        # 验证数据库记录
        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        questions = result.scalars().all()
        assert len(questions) == 3

    @pytest.mark.asyncio
    async def test_llm_calls_multiple_tools(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_multiple_tools_response,
        db_session: AsyncSession,
    ):
        """LLM 单次调用多个工具"""
        test_struct = [
            {"question_type": "single_choice", "question_num": 1},
            {"question_type": "true_false", "question_num": 1},
            {"question_type": "multiple_choice", "question_num": 1},
        ]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_multiple_tools_response

            await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        # LLM 只被调用一次（因为一次调用就生成了所有题目）
        assert mock_complete.call_count == 1

    @pytest.mark.asyncio
    async def test_early_completion(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_single_tool_response,
        db_session: AsyncSession,
    ):
        """提前达到目标数量"""
        test_struct = [{"question_type": "single_choice", "question_num": 1}]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_single_tool_response

            expected, actual = await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        assert expected == 1
        assert actual == 1
        # 达到目标后应停止调用
        assert mock_complete.call_count == 1

    @pytest.mark.asyncio
    async def test_llm_stops_early(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_single_tool_response,
        mock_llm_stop_early_response,
        db_session: AsyncSession,
    ):
        """LLM 提前停止 (题目不足)"""
        test_struct = [{"question_type": "single_choice", "question_num": 5}]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            # 先返回一道题，然后 stop
            mock_complete.side_effect = [
                mock_llm_single_tool_response,
                mock_llm_stop_early_response,
            ]

            expected, actual = await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        assert expected == 5
        assert actual == 1  # 只生成了 1 道题

    @pytest.mark.asyncio
    async def test_max_iterations_reached(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_single_tool_response,
        db_session: AsyncSession,
    ):
        """达到最大迭代次数"""
        # 请求大量题目
        test_struct = [{"question_type": "single_choice", "question_num": 100}]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            # 每次只返回 1 道题
            mock_complete.return_value = mock_llm_single_tool_response

            expected, actual = await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        # 达到最大迭代次数
        assert mock_complete.call_count == MAX_LLM_ITERATIONS
        assert actual == MAX_LLM_ITERATIONS  # 每次迭代生成 1 题

    @pytest.mark.asyncio
    async def test_tool_execution_failure_continues(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        db_session: AsyncSession,
    ):
        """工具执行失败继续"""
        test_struct = [{"question_type": "single_choice", "question_num": 2}]

        # 创建包含无效工具调用的响应
        mock_response = MagicMock()
        mock_response.content = None
        mock_response.finish_reason = "tool_calls"

        # 第一个调用无效（索引超出范围），第二个有效
        invalid_call = MagicMock()
        invalid_call.id = "call_invalid"
        invalid_call.name = "create_single_choice_question"
        invalid_call.arguments = {
            "question_stem": "测试题",
            "options": ["A", "B"],
            "correct_answer_index": 10,  # 无效索引
        }

        valid_call = MagicMock()
        valid_call.id = "call_valid"
        valid_call.name = "create_single_choice_question"
        valid_call.arguments = {
            "question_stem": "有效测试题",
            "options": ["A", "B", "C", "D"],
            "correct_answer_index": 0,
        }

        mock_response.tool_calls = [invalid_call, valid_call]

        # 第二次调用返回另一道有效题目
        mock_response2 = MagicMock()
        mock_response2.content = None
        mock_response2.finish_reason = "tool_calls"
        mock_response2.tool_calls = [valid_call]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.side_effect = [mock_response, mock_response2]

            expected, actual = await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        # 应该有 2 道有效题目（第一次调用的有效题 + 第二次调用的题）
        assert actual == 2

    @pytest.mark.asyncio
    async def test_partial_success(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_single_tool_response,
        mock_llm_stop_early_response,
        db_session: AsyncSession,
    ):
        """部分成功场景"""
        test_struct = [{"question_type": "single_choice", "question_num": 3}]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            # 只生成 2 题后停止
            mock_complete.side_effect = [
                mock_llm_single_tool_response,
                mock_llm_single_tool_response,
                mock_llm_stop_early_response,
            ]

            expected, actual = await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        assert expected == 3
        assert actual == 2

    @pytest.mark.asyncio
    async def test_progress_message_format(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        db_session: AsyncSession,
    ):
        """进度消息格式正确"""
        test_struct = [{"question_type": "single_choice", "question_num": 2}]

        mock_response = MagicMock()
        mock_response.content = None
        mock_response.finish_reason = "tool_calls"

        tool_call = MagicMock()
        tool_call.id = "call_1"
        tool_call.name = "create_single_choice_question"
        tool_call.arguments = {
            "question_stem": "测试题",
            "options": ["A", "B", "C", "D"],
            "correct_answer_index": 0,
        }
        mock_response.tool_calls = [tool_call]

        captured_messages = []

        async def capture_messages(*args, **kwargs):
            if "messages" in kwargs:
                captured_messages.extend(kwargs["messages"])
            return mock_response

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            side_effect=capture_messages,
        ):
            await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        # 检查工具结果消息包含进度信息
        tool_messages = [m for m in captured_messages if m.get("role") == "tool"]
        if tool_messages:
            content = tool_messages[0]["content"]
            assert "成功创建" in content
            assert "single_choice" in content
            assert "/" in content  # 进度格式 x/y

    @pytest.mark.asyncio
    async def test_no_tools_response_continues(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_no_tools_response,
        mock_llm_single_tool_response,
        mock_llm_stop_early_response,
        db_session: AsyncSession,
    ):
        """LLM 不调用工具时继续"""
        test_struct = [{"question_type": "single_choice", "question_num": 1}]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            # 第一次不调用工具，第二次调用，第三次 stop
            mock_complete.side_effect = [
                mock_llm_no_tools_response,
                mock_llm_single_tool_response,
            ]

            expected, actual = await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        assert actual == 1


class TestDatabasePersistence:
    """数据库持久化测试"""

    @pytest_asyncio.fixture
    async def agent(self, db_session: AsyncSession) -> TestGenerationAgent:
        """创建 Agent 实例"""
        return TestGenerationAgent(db_session)

    @pytest.mark.asyncio
    async def test_quiz_total_updated(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_multiple_tools_response,
        db_session: AsyncSession,
    ):
        """Quiz.total_questions 更新"""
        test_struct = [
            {"question_type": "single_choice", "question_num": 1},
            {"question_type": "true_false", "question_num": 1},
            {"question_type": "multiple_choice", "question_num": 1},
        ]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_multiple_tools_response

            await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        # 刷新 quiz 对象
        await db_session.refresh(test_quiz)
        assert test_quiz.total_questions == 3

    @pytest.mark.asyncio
    async def test_questions_inserted(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_multiple_tools_response,
        db_session: AsyncSession,
    ):
        """Question 记录插入"""
        test_struct = [
            {"question_type": "single_choice", "question_num": 1},
            {"question_type": "true_false", "question_num": 1},
            {"question_type": "multiple_choice", "question_num": 1},
        ]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_multiple_tools_response

            await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        questions = result.scalars().all()

        assert len(questions) == 3
        for q in questions:
            assert q.quiz_id == test_quiz.id

    @pytest.mark.asyncio
    async def test_question_types_correct(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_multiple_tools_response,
        db_session: AsyncSession,
    ):
        """题型正确保存"""
        test_struct = [
            {"question_type": "single_choice", "question_num": 1},
            {"question_type": "true_false", "question_num": 1},
            {"question_type": "multiple_choice", "question_num": 1},
        ]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_multiple_tools_response

            await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        questions = result.scalars().all()

        types = {q.question_type for q in questions}
        assert QuestionType.SINGLE_CHOICE in types
        assert QuestionType.TRUE_FALSE in types
        assert QuestionType.MULTIPLE_CHOICE in types

    @pytest.mark.asyncio
    async def test_question_content_saved(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_single_tool_response,
        db_session: AsyncSession,
    ):
        """题目内容正确保存"""
        test_struct = [{"question_type": "single_choice", "question_num": 1}]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_single_tool_response

            await agent.generate(
                quiz_id=test_quiz.id,
                topic="Python 基础",
                difficulty="medium",
                test_struct=test_struct,
            )

        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        question = result.scalar_one()

        assert question.question_stem == "Python 中哪个关键字用于定义函数？"
        assert question.options == ["def", "func", "function", "define"]
        assert question.correct_answer == {"index": 0}

    @pytest.mark.asyncio
    async def test_order_index_sequential(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_multiple_tools_response,
        db_session: AsyncSession,
    ):
        """order_index 顺序正确"""
        test_struct = [
            {"question_type": "single_choice", "question_num": 1},
            {"question_type": "true_false", "question_num": 1},
            {"question_type": "multiple_choice", "question_num": 1},
        ]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_multiple_tools_response

            await agent.generate(
                quiz_id=test_quiz.id,
                topic="测试",
                difficulty="easy",
                test_struct=test_struct,
            )

        result = await db_session.execute(
            select(Question)
            .where(Question.quiz_id == test_quiz.id)
            .order_by(Question.order_index)
        )
        questions = result.scalars().all()

        for idx, q in enumerate(questions):
            assert q.order_index == idx


class TestShortAnswerQuestions:
    """简答题生成测试"""

    @pytest_asyncio.fixture
    async def agent(self, db_session: AsyncSession) -> TestGenerationAgent:
        return TestGenerationAgent(db_session)

    @pytest.mark.asyncio
    async def test_short_answer_generation(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        mock_llm_short_answer_response,
        db_session: AsyncSession,
    ):
        """简答题生成"""
        test_struct = [{"question_type": "short_answer", "question_num": 1}]

        with patch.object(
            agent.llm_client,
            "complete_with_tools",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = mock_llm_short_answer_response

            expected, actual = await agent.generate(
                quiz_id=test_quiz.id,
                topic="Python",
                difficulty="medium",
                test_struct=test_struct,
            )

        assert actual == 1

        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        question = result.scalar_one()

        assert question.question_type == QuestionType.SHORT_ANSWER
        assert question.options is None
        assert "reference" in question.correct_answer
