"""TestGenerationAgent 单元测试"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.test_generation_agent import TestGenerationAgent
from agents.tools.quiz_tools import CreatedQuestion
from db.models import Question, QuestionType, Quiz


class TestCountByType:
    """_count_by_type 方法测试"""

    @pytest_asyncio.fixture
    async def agent(self, db_session: AsyncSession) -> TestGenerationAgent:
        """创建 Agent 实例"""
        return TestGenerationAgent(db_session)

    def test_empty_list(self, agent: TestGenerationAgent):
        """空列表返回空字典"""
        result = agent._count_by_type([])
        assert result == {}

    def test_single_type(self, agent: TestGenerationAgent, question_factory):
        """单一题型"""
        questions = [
            question_factory(question_type=QuestionType.SINGLE_CHOICE),
            question_factory(question_type=QuestionType.SINGLE_CHOICE),
            question_factory(question_type=QuestionType.SINGLE_CHOICE),
        ]

        result = agent._count_by_type(questions)

        assert result == {"single_choice": 3}

    def test_multiple_types(self, agent: TestGenerationAgent, question_factory):
        """多种题型混合"""
        questions = [
            question_factory(question_type=QuestionType.SINGLE_CHOICE),
            question_factory(question_type=QuestionType.MULTIPLE_CHOICE),
            question_factory(question_type=QuestionType.SINGLE_CHOICE),
            question_factory(question_type=QuestionType.TRUE_FALSE),
            question_factory(question_type=QuestionType.SHORT_ANSWER),
            question_factory(question_type=QuestionType.TRUE_FALSE),
        ]

        result = agent._count_by_type(questions)

        assert result == {
            "single_choice": 2,
            "multiple_choice": 1,
            "true_false": 2,
            "short_answer": 1,
        }

    def test_count_accuracy(self, agent: TestGenerationAgent, question_factory):
        """计数准确性"""
        questions = [
            question_factory(question_type=QuestionType.SINGLE_CHOICE)
            for _ in range(10)
        ]
        questions.extend([
            question_factory(question_type=QuestionType.TRUE_FALSE)
            for _ in range(5)
        ])

        result = agent._count_by_type(questions)

        assert result["single_choice"] == 10
        assert result["true_false"] == 5

    def test_all_question_types(self, agent: TestGenerationAgent, question_factory):
        """所有题型都能正确计数"""
        questions = [
            question_factory(question_type=QuestionType.SINGLE_CHOICE),
            question_factory(question_type=QuestionType.MULTIPLE_CHOICE),
            question_factory(question_type=QuestionType.TRUE_FALSE),
            question_factory(question_type=QuestionType.SHORT_ANSWER),
        ]

        result = agent._count_by_type(questions)

        assert len(result) == 4
        assert all(count == 1 for count in result.values())


class TestPersistQuestions:
    """_persist_questions 方法测试"""

    @pytest_asyncio.fixture
    async def agent(self, db_session: AsyncSession) -> TestGenerationAgent:
        """创建 Agent 实例"""
        return TestGenerationAgent(db_session)

    @pytest.mark.asyncio
    async def test_persist_all_success(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        question_factory,
        db_session: AsyncSession,
    ):
        """全部成功持久化"""
        questions = [
            question_factory(
                question_type=QuestionType.SINGLE_CHOICE,
                question_stem=f"题目 {i}",
            )
            for i in range(5)
        ]

        count = await agent._persist_questions(test_quiz.id, questions)

        assert count == 5

        # 验证数据库中的记录
        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        saved_questions = result.scalars().all()
        assert len(saved_questions) == 5

    @pytest.mark.asyncio
    async def test_persist_empty_list(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        db_session: AsyncSession,
    ):
        """空列表返回 0"""
        count = await agent._persist_questions(test_quiz.id, [])

        assert count == 0

        # 验证没有记录被创建
        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        saved_questions = result.scalars().all()
        assert len(saved_questions) == 0

    @pytest.mark.asyncio
    async def test_order_index_correct(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        question_factory,
        db_session: AsyncSession,
    ):
        """order_index 正确设置"""
        questions = [
            question_factory(question_stem=f"题目 {i}")
            for i in range(3)
        ]

        await agent._persist_questions(test_quiz.id, questions)

        result = await db_session.execute(
            select(Question)
            .where(Question.quiz_id == test_quiz.id)
            .order_by(Question.order_index)
        )
        saved_questions = result.scalars().all()

        for idx, q in enumerate(saved_questions):
            assert q.order_index == idx

    @pytest.mark.asyncio
    async def test_correct_answer_json_format(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        question_factory,
        db_session: AsyncSession,
    ):
        """JSON 格式正确"""
        questions = [
            question_factory(
                question_type=QuestionType.SINGLE_CHOICE,
                correct_answer={"index": 2},
            ),
            question_factory(
                question_type=QuestionType.MULTIPLE_CHOICE,
                correct_answer={"indices": [0, 1, 3]},
            ),
            question_factory(
                question_type=QuestionType.TRUE_FALSE,
                options=None,
                correct_answer={"value": True},
            ),
            question_factory(
                question_type=QuestionType.SHORT_ANSWER,
                options=None,
                correct_answer={"reference": "参考答案"},
            ),
        ]

        await agent._persist_questions(test_quiz.id, questions)

        result = await db_session.execute(
            select(Question)
            .where(Question.quiz_id == test_quiz.id)
            .order_by(Question.order_index)
        )
        saved_questions = result.scalars().all()

        assert saved_questions[0].correct_answer == {"index": 2}
        assert saved_questions[1].correct_answer == {"indices": [0, 1, 3]}
        assert saved_questions[2].correct_answer == {"value": True}
        assert saved_questions[3].correct_answer == {"reference": "参考答案"}

    @pytest.mark.asyncio
    async def test_question_type_preserved(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        question_factory,
        db_session: AsyncSession,
    ):
        """题型正确保存"""
        questions = [
            question_factory(question_type=QuestionType.SINGLE_CHOICE),
            question_factory(question_type=QuestionType.MULTIPLE_CHOICE),
            question_factory(question_type=QuestionType.TRUE_FALSE, options=None),
            question_factory(question_type=QuestionType.SHORT_ANSWER, options=None),
        ]

        await agent._persist_questions(test_quiz.id, questions)

        result = await db_session.execute(
            select(Question)
            .where(Question.quiz_id == test_quiz.id)
            .order_by(Question.order_index)
        )
        saved_questions = result.scalars().all()

        assert saved_questions[0].question_type == QuestionType.SINGLE_CHOICE
        assert saved_questions[1].question_type == QuestionType.MULTIPLE_CHOICE
        assert saved_questions[2].question_type == QuestionType.TRUE_FALSE
        assert saved_questions[3].question_type == QuestionType.SHORT_ANSWER

    @pytest.mark.asyncio
    async def test_options_preserved(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        question_factory,
        db_session: AsyncSession,
    ):
        """选项正确保存"""
        options = ["选项A", "选项B", "选项C", "选项D"]
        questions = [
            question_factory(
                question_type=QuestionType.SINGLE_CHOICE,
                options=options,
            ),
        ]

        await agent._persist_questions(test_quiz.id, questions)

        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        saved_question = result.scalar_one()

        assert saved_question.options == options

    @pytest.mark.asyncio
    async def test_question_stem_preserved(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        question_factory,
        db_session: AsyncSession,
    ):
        """题干正确保存"""
        stem = "这是一道测试题，请选择正确答案。"
        questions = [
            question_factory(question_stem=stem),
        ]

        await agent._persist_questions(test_quiz.id, questions)

        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        saved_question = result.scalar_one()

        assert saved_question.question_stem == stem

    @pytest.mark.asyncio
    async def test_large_batch_persist(
        self,
        agent: TestGenerationAgent,
        test_quiz: Quiz,
        question_factory,
        db_session: AsyncSession,
    ):
        """大批量题目持久化"""
        questions = [
            question_factory(question_stem=f"题目 {i}")
            for i in range(50)
        ]

        count = await agent._persist_questions(test_quiz.id, questions)

        assert count == 50

        result = await db_session.execute(
            select(Question).where(Question.quiz_id == test_quiz.id)
        )
        saved_questions = result.scalars().all()
        assert len(saved_questions) == 50


class TestAgentInit:
    """Agent 初始化测试"""

    @pytest.mark.asyncio
    async def test_agent_has_db_session(self, db_session: AsyncSession):
        """Agent 应持有数据库会话"""
        agent = TestGenerationAgent(db_session)

        assert agent.db is db_session

    @pytest.mark.asyncio
    async def test_agent_has_llm_client(self, db_session: AsyncSession):
        """Agent 应持有 LLM 客户端"""
        agent = TestGenerationAgent(db_session)

        assert agent.llm_client is not None

    @pytest.mark.asyncio
    async def test_agent_has_tool_executor(self, db_session: AsyncSession):
        """Agent 应持有工具执行器"""
        agent = TestGenerationAgent(db_session)

        assert agent.tool_executor is not None
