"""Quiz 服务层"""

import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Quiz, QuizAttempt, Space
from quiz.full_evaluation_service import (
    FullQuizEvaluationResult,
    QuizEvaluationService,
)
from quizzes.schemas import (
    DebugInfoResponse,
    DebugStepResponse,
    QuestionResponse,
    QuestionResultResponse,
    QuizAttemptResponse,
    QuizDetailResponse,
    QuizListItemResponse,
    UserAnswerItem,
)

logger = logging.getLogger(__name__)


class QuizNotFoundError(Exception):
    """测试不存在"""

    pass


class QuizAccessDeniedError(Exception):
    """无权访问测试"""

    pass


class QuizAlreadyAttemptedError(Exception):
    """测试已经作答过"""

    pass


class QuizAttemptNotFoundError(Exception):
    """作答记录不存在"""

    pass


class QuizService:
    """Quiz 服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_quiz_detail(
        self,
        user_id: UUID,
        quiz_id: UUID,
    ) -> QuizDetailResponse:
        """
        获取测试详情（包含所有题目）

        Args:
            user_id: 用户 ID
            quiz_id: 测试 ID

        Returns:
            QuizDetailResponse

        Raises:
            QuizNotFoundError: 测试不存在
            QuizAccessDeniedError: 无权访问
        """
        # 查询 Quiz 并预加载 questions 和 space
        result = await self.db.execute(
            select(Quiz)
            .options(selectinload(Quiz.questions), selectinload(Quiz.space))
            .where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()

        if not quiz:
            raise QuizNotFoundError(f"测试不存在: {quiz_id}")

        # 验证用户权限（通过 space）
        if quiz.space.user_id != user_id:
            raise QuizAccessDeniedError(f"无权访问该测试: {quiz_id}")

        # 按 order_index 排序题目
        sorted_questions = sorted(quiz.questions, key=lambda q: q.order_index)

        # 构建响应
        question_responses = [
            QuestionResponse(
                id=q.id,
                question_type=q.question_type.value,
                question_stem=q.question_stem,
                options=q.options,
                correct_answer=q.correct_answer,
                order_index=q.order_index,
            )
            for q in sorted_questions
        ]

        return QuizDetailResponse(
            id=quiz.id,
            space_id=quiz.space_id,
            title=quiz.title,
            topic=quiz.topic,
            difficulty=quiz.difficulty.value,
            total_questions=quiz.total_questions,
            questions=question_responses,
            created_at=quiz.created_at,
        )

    async def submit_and_evaluate(
        self,
        user_id: UUID,
        quiz_id: UUID,
        answers: list[UserAnswerItem],
    ) -> FullQuizEvaluationResult:
        """
        提交答卷并进行评估

        Args:
            user_id: 用户 ID
            quiz_id: 测试 ID
            answers: 用户答案列表

        Returns:
            FullQuizEvaluationResult

        Raises:
            QuizNotFoundError: 测试不存在
            QuizAccessDeniedError: 无权访问
        """
        # 查询 Quiz 并预加载 questions 和 space
        result = await self.db.execute(
            select(Quiz)
            .options(selectinload(Quiz.questions), selectinload(Quiz.space))
            .where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()

        if not quiz:
            raise QuizNotFoundError(f"测试不存在: {quiz_id}")

        # 验证用户权限（通过 space）
        if quiz.space.user_id != user_id:
            raise QuizAccessDeniedError(f"无权访问该测试: {quiz_id}")

        # 按 order_index 排序题目
        sorted_questions = sorted(quiz.questions, key=lambda q: q.order_index)

        # 构建题目数据列表
        questions_data = [
            {
                "id": q.id,
                "question_type": q.question_type.value,
                "question_stem": q.question_stem,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "order_index": q.order_index,
            }
            for q in sorted_questions
        ]

        # 构建答案映射 {question_id: answer}
        user_answers = {str(item.question_id): item.answer for item in answers}

        # 检查是否已经作答过
        existing_attempt = await self.db.execute(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.user_id == user_id,
            )
        )
        if existing_attempt.scalar_one_or_none():
            raise QuizAlreadyAttemptedError(f"该测试已经作答过: {quiz_id}")

        # 调用评估服务（传递 space_id 以支持掌握分更新）
        evaluation_service = QuizEvaluationService(
            space_id=quiz.space_id,
        )
        evaluation_result = await evaluation_service.evaluate_quiz(
            quiz_id=quiz_id,
            quiz_topic=quiz.topic,
            difficulty_level=quiz.difficulty.value,
            questions=questions_data,
            user_answers=user_answers,
        )

        # 持久化作答记录
        question_results_data = [
            {
                "question_id": str(qr.question_id),
                "order": qr.order,
                "question_type": qr.question_type,
                "title": qr.question_stem,
                "options": qr.options,
                "status": qr.status,
                "score": qr.score,
                "max_score": qr.max_score,
                "user_answer": qr.user_answer,
                "correct_answer": qr.correct_answer,
                "ai_evaluation": qr.ai_evaluation,
            }
            for qr in evaluation_result.question_results
        ]

        # 序列化 debug_info
        debug_info_data = None
        if evaluation_result.debug_info:
            debug_info_data = {
                "steps": [
                    {
                        "step_number": s.step_number,
                        "step_name": s.step_name,
                        "status": s.status,
                        "duration_ms": s.duration_ms,
                        "details": s.details,
                        "metadata": s.metadata,
                    }
                    for s in evaluation_result.debug_info.steps
                ],
                "model_name": evaluation_result.debug_info.model_name,
                "total_duration_ms": evaluation_result.debug_info.total_duration_ms,
            }

        attempt = QuizAttempt(
            quiz_id=quiz_id,
            user_id=user_id,
            score=evaluation_result.score,
            total_score=evaluation_result.total_score,
            strengths=evaluation_result.strengths,
            weaknesses=evaluation_result.weaknesses,
            suggestions=evaluation_result.suggestions,
            question_results=question_results_data,
            debug_info=debug_info_data,
        )
        self.db.add(attempt)
        await self.db.commit()

        return evaluation_result

    async def get_quizzes_by_space(
        self,
        user_id: UUID,
        space_id: UUID,
    ) -> list[QuizListItemResponse]:
        """
        获取空间内所有测验列表（带作答状态）

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID

        Returns:
            list[QuizListItemResponse]

        Raises:
            QuizAccessDeniedError: 无权访问该空间
        """
        # 验证用户权限
        space_result = await self.db.execute(
            select(Space).where(Space.id == space_id)
        )
        space = space_result.scalar_one_or_none()

        if not space:
            raise QuizAccessDeniedError(f"空间不存在: {space_id}")

        if space.user_id != user_id:
            raise QuizAccessDeniedError(f"无权访问该空间: {space_id}")

        # 查询空间内所有测验
        quizzes_result = await self.db.execute(
            select(Quiz).where(Quiz.space_id == space_id).order_by(Quiz.created_at.desc())
        )
        quizzes = quizzes_result.scalars().all()

        # 查询用户在这些测验中的作答记录
        quiz_ids = [q.id for q in quizzes]
        attempts_result = await self.db.execute(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id.in_(quiz_ids),
                QuizAttempt.user_id == user_id,
            )
        )
        attempts = {a.quiz_id: a for a in attempts_result.scalars().all()}

        # 构建响应
        response_items = []
        for quiz in quizzes:
            attempt = attempts.get(quiz.id)
            response_items.append(
                QuizListItemResponse(
                    id=quiz.id,
                    title=quiz.title,
                    topic=quiz.topic,
                    difficulty=quiz.difficulty.value,
                    total_questions=quiz.total_questions,
                    created_at=quiz.created_at,
                    has_attempt=attempt is not None,
                    attempt_score=attempt.score if attempt else None,
                    attempt_total_score=attempt.total_score if attempt else None,
                )
            )

        return response_items

    async def get_quiz_attempt(
        self,
        user_id: UUID,
        quiz_id: UUID,
    ) -> QuizAttemptResponse:
        """
        获取测验作答记录

        Args:
            user_id: 用户 ID
            quiz_id: 测试 ID

        Returns:
            QuizAttemptResponse

        Raises:
            QuizNotFoundError: 测试不存在
            QuizAccessDeniedError: 无权访问
            QuizAttemptNotFoundError: 作答记录不存在
        """
        # 验证测验存在且有权限
        quiz_result = await self.db.execute(
            select(Quiz).options(selectinload(Quiz.space)).where(Quiz.id == quiz_id)
        )
        quiz = quiz_result.scalar_one_or_none()

        if not quiz:
            raise QuizNotFoundError(f"测试不存在: {quiz_id}")

        if quiz.space.user_id != user_id:
            raise QuizAccessDeniedError(f"无权访问该测试: {quiz_id}")

        # 查询作答记录
        attempt_result = await self.db.execute(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.user_id == user_id,
            )
        )
        attempt = attempt_result.scalar_one_or_none()

        if not attempt:
            raise QuizAttemptNotFoundError(f"作答记录不存在: {quiz_id}")

        # 构建逐题结果
        question_results = [
            QuestionResultResponse(
                id=qr["question_id"],
                order=qr["order"],
                question_type=qr["question_type"],
                title=qr["title"],
                options=qr.get("options"),
                status=qr["status"],
                score=qr["score"],
                max_score=qr["max_score"],
                user_answer=qr["user_answer"],
                correct_answer=qr["correct_answer"],
                ai_evaluation=qr.get("ai_evaluation"),
            )
            for qr in attempt.question_results
        ]

        # 构建调试信息（如有）
        debug_info_response = None
        if attempt.debug_info:
            debug_info_response = DebugInfoResponse(
                steps=[
                    DebugStepResponse(
                        step_number=s["step_number"],
                        step_name=s["step_name"],
                        status=s["status"],
                        duration_ms=s["duration_ms"],
                        details=s.get("details", []),
                        metadata=s.get("metadata"),
                    )
                    for s in attempt.debug_info.get("steps", [])
                ],
                model_name=attempt.debug_info.get("model_name", ""),
                total_duration_ms=attempt.debug_info.get("total_duration_ms", 0),
            )

        return QuizAttemptResponse(
            id=attempt.id,
            quiz_id=attempt.quiz_id,
            score=attempt.score,
            total_score=attempt.total_score,
            strengths=attempt.strengths,
            weaknesses=attempt.weaknesses,
            suggestions=attempt.suggestions,
            question_results=question_results,
            debug_info=debug_info_response,
            submitted_at=attempt.submitted_at,
        )

    async def delete_quiz(
        self,
        user_id: UUID,
        quiz_id: UUID,
    ) -> None:
        """
        删除测验

        Args:
            user_id: 用户 ID
            quiz_id: 测试 ID

        Raises:
            QuizNotFoundError: 测试不存在
            QuizAccessDeniedError: 无权访问
        """
        # 验证测验存在且有权限
        quiz_result = await self.db.execute(
            select(Quiz).options(selectinload(Quiz.space)).where(Quiz.id == quiz_id)
        )
        quiz = quiz_result.scalar_one_or_none()

        if not quiz:
            raise QuizNotFoundError(f"测试不存在: {quiz_id}")

        if quiz.space.user_id != user_id:
            raise QuizAccessDeniedError(f"无权删除该测试: {quiz_id}")

        # 删除测验（关联的 questions 和 attempts 会级联删除）
        await self.db.execute(delete(Quiz).where(Quiz.id == quiz_id))
        await self.db.commit()
