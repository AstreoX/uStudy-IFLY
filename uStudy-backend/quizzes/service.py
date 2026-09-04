"""Quiz 服务层"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Quiz, QuizAttempt
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
    QuizDraftSaveResponse,
    QuizListItemResponse,
    QuizSubmitAsyncResponse,
    UserAnswerResponseItem,
    UserAnswerItem,
)

logger = logging.getLogger(__name__)

# Prevent GC of fire-and-forget tasks
_background_tasks: set[asyncio.Task] = set()


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


class QuizAttemptLockedError(Exception):
    """作答状态已锁定，不能继续修改"""

    pass


class QuizService:
    """Quiz 服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _check_space_access(self, space_id: UUID, user_id: UUID) -> None:
        """Verify user has access (owner or member). Raises QuizAccessDeniedError."""
        # Lazy import to avoid circular: quizzes → spaces → chat → quizzes
        from spaces.authorization import (
            SpaceAccessDeniedError,
            SpaceNotFoundError,
            verify_space_access,
        )

        try:
            await verify_space_access(self.db, space_id, user_id)
        except (SpaceNotFoundError, SpaceAccessDeniedError):
            raise QuizAccessDeniedError(f"无权访问该空间: {space_id}")

    async def _check_space_ownership(self, space_id: UUID, user_id: UUID) -> None:
        """Verify user is the space owner. Raises QuizAccessDeniedError."""
        from spaces.authorization import (
            SpaceAccessDeniedError,
            SpaceNotFoundError,
            verify_space_ownership,
        )

        try:
            await verify_space_ownership(self.db, space_id, user_id)
        except (SpaceNotFoundError, SpaceAccessDeniedError):
            raise QuizAccessDeniedError(f"无权操作该空间: {space_id}")

    async def _get_quiz(
        self,
        quiz_id: UUID,
        *,
        user_id: UUID | None = None,
        with_questions: bool = False,
        with_space: bool = False,
    ) -> Quiz:
        options = []
        if with_questions:
            options.append(selectinload(Quiz.questions))
        if with_space:
            options.append(selectinload(Quiz.space))

        result = await self.db.execute(
            select(Quiz).options(*options).where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()
        if not quiz:
            raise QuizNotFoundError(f"测试不存在: {quiz_id}")
        if (
            user_id is not None
            and quiz.visibility == "private"
            and quiz.creator_user_id != user_id
        ):
            raise QuizNotFoundError(f"测试不存在: {quiz_id}")
        return quiz

    async def _get_existing_attempt(
        self,
        quiz_id: UUID,
        user_id: UUID,
    ) -> QuizAttempt | None:
        result = await self.db.execute(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    def _serialize_user_answers(
        self,
        answers: list[UserAnswerItem],
    ) -> dict[str, Any]:
        serialized: dict[str, Any] = {}
        for item in answers:
            if item.answer is None:
                continue
            serialized[str(item.question_id)] = item.answer
        return serialized

    def _build_draft_answers_response(
        self,
        questions: list[Any],
        user_answers_raw: dict[str, Any] | None,
    ) -> list[UserAnswerResponseItem]:
        if not user_answers_raw:
            return []

        response_items: list[UserAnswerResponseItem] = []
        for question in questions:
            answer = user_answers_raw.get(str(question.id))
            if answer is None:
                continue
            response_items.append(
                UserAnswerResponseItem(
                    question_id=question.id,
                    answer=answer,
                )
            )
        return response_items

    def _serialize_question_results(
        self,
        evaluation_result: FullQuizEvaluationResult,
    ) -> list[dict[str, Any]]:
        return [
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

    def _serialize_debug_info(
        self,
        evaluation_result: FullQuizEvaluationResult,
    ) -> dict[str, Any] | None:
        if not evaluation_result.debug_info:
            return None

        return {
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
        quiz = await self._get_quiz(
            quiz_id, user_id=user_id, with_questions=True
        )

        # 验证用户权限（owner 或 collaborative member）
        await self._check_space_access(quiz.space_id, user_id)

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

        existing_attempt = await self._get_existing_attempt(quiz_id, user_id)
        draft_answers = []
        current_question_index = 0
        draft_updated_at = None
        attempt_status = None
        if existing_attempt:
            attempt_status = existing_attempt.status
            current_question_index = existing_attempt.current_question_index or 0
            draft_updated_at = existing_attempt.draft_updated_at
            if existing_attempt.status == "in_progress":
                draft_answers = self._build_draft_answers_response(
                    sorted_questions,
                    existing_attempt.user_answers_raw,
                )

        return QuizDetailResponse(
            id=quiz.id,
            space_id=quiz.space_id,
            title=quiz.title,
            topic=quiz.topic,
            difficulty=quiz.difficulty.value,
            total_questions=quiz.total_questions,
            is_review_quiz=quiz.is_review_quiz,
            creator_user_id=quiz.creator_user_id,
            visibility=quiz.visibility,
            attempt_status=attempt_status,
            draft_answers=draft_answers,
            current_question_index=current_question_index,
            draft_updated_at=draft_updated_at,
            questions=question_responses,
            created_at=quiz.created_at,
        )

    async def save_draft(
        self,
        user_id: UUID,
        quiz_id: UUID,
        answers: list[UserAnswerItem],
        current_question_index: int,
    ) -> QuizDraftSaveResponse:
        quiz = await self._get_quiz(quiz_id, user_id=user_id)
        await self._check_space_access(quiz.space_id, user_id)

        user_answers = self._serialize_user_answers(answers)
        clamped_question_index = max(0, current_question_index)

        attempt = await self._get_existing_attempt(quiz_id, user_id)
        if attempt and attempt.status != "in_progress":
            raise QuizAttemptLockedError(f"该测试状态已锁定: {quiz_id} -> {attempt.status}")

        if not attempt:
            attempt = QuizAttempt(
                quiz_id=quiz_id,
                user_id=user_id,
                status="in_progress",
                user_answers_raw=user_answers,
                current_question_index=clamped_question_index,
                score=0,
                total_score=0,
                strengths=[],
                weaknesses=[],
                suggestions=[],
                question_results=[],
                submitted_at=datetime.now(timezone.utc),
                draft_updated_at=datetime.now(timezone.utc),
            )
            self.db.add(attempt)
        else:
            attempt.user_answers_raw = user_answers
            attempt.current_question_index = clamped_question_index
            attempt.draft_updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(attempt)

        return QuizDraftSaveResponse(
            quiz_id=quiz_id,
            attempt_id=attempt.id,
            status=attempt.status,
            draft_updated_at=attempt.draft_updated_at,
            message="草稿已暂存",
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
        quiz = await self._get_quiz(
            quiz_id,
            user_id=user_id,
            with_questions=True,
            with_space=True,
        )

        # 验证用户权限（owner 或 collaborative member）
        await self._check_space_access(quiz.space_id, user_id)

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
        user_answers = self._serialize_user_answers(answers)

        existing_attempt = await self._get_existing_attempt(quiz_id, user_id)
        if existing_attempt and existing_attempt.status != "in_progress":
            raise QuizAlreadyAttemptedError(f"该测试已经作答过: {quiz_id}")

        # 调用评估服务（传递 space_id, user_id, is_collaborative 以支持掌握分更新）
        evaluation_service = QuizEvaluationService(
            space_id=quiz.space_id,
            user_id=user_id,
            is_collaborative=quiz.space.is_collaborative if quiz.space else False,
        )
        evaluation_result = await evaluation_service.evaluate_quiz(
            quiz_id=quiz_id,
            quiz_topic=quiz.topic,
            difficulty_level=quiz.difficulty.value,
            questions=questions_data,
            user_answers=user_answers,
        )

        question_results_data = self._serialize_question_results(evaluation_result)
        debug_info_data = self._serialize_debug_info(evaluation_result)

        attempt = existing_attempt or QuizAttempt(
            quiz_id=quiz_id,
            user_id=user_id,
            score=0,
            total_score=0,
            strengths=[],
            weaknesses=[],
            suggestions=[],
            question_results=[],
            submitted_at=datetime.now(timezone.utc),
            draft_updated_at=datetime.now(timezone.utc),
        )
        if not existing_attempt:
            self.db.add(attempt)

        attempt.status = "completed"
        attempt.user_answers_raw = user_answers
        attempt.current_question_index = max(len(sorted_questions) - 1, 0)
        attempt.score = evaluation_result.score
        attempt.total_score = evaluation_result.total_score
        attempt.strengths = evaluation_result.strengths
        attempt.weaknesses = evaluation_result.weaknesses
        attempt.suggestions = evaluation_result.suggestions
        attempt.question_results = question_results_data
        attempt.debug_info = debug_info_data
        attempt.submitted_at = datetime.now(timezone.utc)
        attempt.draft_updated_at = datetime.now(timezone.utc)
        await self.db.commit()

        # 记录测验活动（fire-and-forget）
        from activity.service import record_quiz_activity

        task = asyncio.create_task(
            record_quiz_activity(
                user_id=user_id,
                quiz_topic=quiz.topic,
                quiz_space_id=quiz.space_id,
                quiz_space_name=quiz.space.name if quiz.space else None,
                score=evaluation_result.score,
                total_score=evaluation_result.total_score,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        # SM-2 反馈：如果是复习测试题，更新复习间隔
        if quiz.is_review_quiz:
            sm2_task = asyncio.create_task(
                _trigger_sm2_feedback(
                    user_id=user_id,
                    quiz_id=quiz.id,
                    score=evaluation_result.score,
                    total_score=evaluation_result.total_score,
                )
            )
            _background_tasks.add(sm2_task)
            sm2_task.add_done_callback(_background_tasks.discard)

        return evaluation_result

    async def submit_async(
        self,
        user_id: UUID,
        quiz_id: UUID,
        answers: list[UserAnswerItem],
    ) -> QuizSubmitAsyncResponse:
        """
        异步提交答卷：立即返回，后台评估

        Args:
            user_id: 用户 ID
            quiz_id: 测试 ID
            answers: 用户答案列表

        Returns:
            QuizSubmitAsyncResponse

        Raises:
            QuizNotFoundError: 测试不存在
            QuizAccessDeniedError: 无权访问
            QuizAlreadyAttemptedError: 已作答
        """
        quiz = await self._get_quiz(
            quiz_id,
            user_id=user_id,
            with_questions=True,
            with_space=True,
        )

        # 验证用户权限（owner 或 collaborative member）
        await self._check_space_access(quiz.space_id, user_id)

        # 构建答案映射
        user_answers = self._serialize_user_answers(answers)

        # 快照题目数据（避免 DB session 跨边界）
        questions_snapshot = [
            {
                "id": str(q.id),
                "question_type": q.question_type.value,
                "question_stem": q.question_stem,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "order_index": q.order_index,
            }
            for q in sorted(quiz.questions, key=lambda q: q.order_index)
        ]

        # 快照 space 信息
        space_id = quiz.space_id
        space_name = quiz.space.name if quiz.space else None
        space_is_collaborative = quiz.space.is_collaborative if quiz.space else False
        quiz_topic = quiz.topic
        quiz_difficulty = quiz.difficulty.value
        quiz_is_review = quiz.is_review_quiz

        existing_attempt = await self._get_existing_attempt(quiz_id, user_id)
        if existing_attempt and existing_attempt.status != "in_progress":
            raise QuizAlreadyAttemptedError(f"该测试已经作答过: {quiz_id}")

        attempt = existing_attempt or QuizAttempt(
            quiz_id=quiz_id,
            user_id=user_id,
            status="pending",
            user_answers_raw=user_answers,
            current_question_index=max(len(questions_snapshot) - 1, 0),
            score=0,
            total_score=0,
            strengths=[],
            weaknesses=[],
            suggestions=[],
            question_results=[],
            submitted_at=datetime.now(timezone.utc),
            draft_updated_at=datetime.now(timezone.utc),
        )
        if not existing_attempt:
            self.db.add(attempt)

        attempt.status = "pending"
        attempt.user_answers_raw = user_answers
        attempt.current_question_index = max(len(questions_snapshot) - 1, 0)
        attempt.score = 0
        attempt.total_score = 0
        attempt.strengths = []
        attempt.weaknesses = []
        attempt.suggestions = []
        attempt.question_results = []
        attempt.debug_info = None
        attempt.submitted_at = datetime.now(timezone.utc)
        attempt.draft_updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(attempt)

        attempt_id = attempt.id

        # 启动后台评估任务
        task = asyncio.create_task(
            _run_background_evaluation(
                attempt_id=attempt_id,
                user_id=user_id,
                quiz_id=quiz_id,
                quiz_topic=quiz_topic,
                quiz_difficulty=quiz_difficulty,
                space_id=space_id,
                space_name=space_name,
                questions_snapshot=questions_snapshot,
                user_answers=user_answers,
                is_collaborative=space_is_collaborative,
                is_review_quiz=quiz_is_review,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        return QuizSubmitAsyncResponse(
            quiz_id=quiz_id,
            attempt_id=attempt_id,
            status="pending",
            message="提交成功，AI 正在后台评估",
        )

    async def get_quizzes_by_space(
        self,
        user_id: UUID,
        space_id: UUID,
        folder_id: "UUID | None" = None,
    ) -> list[QuizListItemResponse]:
        """
        获取空间内所有测验列表（带作答状态）

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID
            folder_id: 文件夹 ID（可选，筛选指定文件夹）

        Returns:
            list[QuizListItemResponse]

        Raises:
            QuizAccessDeniedError: 无权访问该空间
        """
        # 验证用户权限（owner 或 collaborative member）
        await self._check_space_access(space_id, user_id)

        # 查询空间内所有测验
        stmt = (
            select(Quiz)
            .where(
                Quiz.space_id == space_id,
                or_(
                    Quiz.visibility == "shared",
                    Quiz.creator_user_id == user_id,
                ),
            )
            .order_by(Quiz.created_at.desc())
        )
        if folder_id is not None:
            stmt = stmt.where(Quiz.folder_id == folder_id)

        quizzes_result = await self.db.execute(stmt)
        quizzes = quizzes_result.scalars().all()

        # 查询用户在这些测验中的作答记录
        quiz_ids = [q.id for q in quizzes]
        attempts: dict[UUID, QuizAttempt] = {}
        if quiz_ids:
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
                    folder_id=quiz.folder_id,
                    creator_user_id=quiz.creator_user_id,
                    visibility=quiz.visibility,
                    created_at=quiz.created_at,
                    has_attempt=attempt is not None,
                    attempt_score=attempt.score if attempt else None,
                    attempt_total_score=attempt.total_score if attempt else None,
                    attempt_status=attempt.status if attempt else None,
                    draft_answer_count=(
                        len(attempt.user_answers_raw or {})
                        if attempt and attempt.status == "in_progress"
                        else None
                    ),
                    draft_updated_at=(
                        attempt.draft_updated_at
                        if attempt and attempt.status == "in_progress"
                        else None
                    ),
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
        quiz = await self._get_quiz(quiz_id, user_id=user_id)

        await self._check_space_access(quiz.space_id, user_id)

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
            status=attempt.status,
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
        # 验证测验存在且有权限（仅 owner 可删除）
        quiz = await self._get_quiz(quiz_id, user_id=user_id)
        await self._check_space_access(quiz.space_id, user_id)
        if quiz.visibility != "private":
            await self._check_space_ownership(quiz.space_id, user_id)

        # 删除测验（关联的 questions 和 attempts 会级联删除）
        await self.db.execute(delete(Quiz).where(Quiz.id == quiz_id))
        await self.db.commit()


async def _run_background_evaluation(
    *,
    attempt_id: UUID,
    user_id: UUID,
    quiz_id: UUID,
    quiz_topic: str,
    quiz_difficulty: str,
    space_id: UUID,
    space_name: str | None,
    questions_snapshot: list[dict],
    user_answers: dict[str, Any],
    is_collaborative: bool = False,
    is_review_quiz: bool = False,
) -> None:
    """后台执行 AI 评估（fire-and-forget）。使用独立 DB session。"""
    from db.database import get_scoped_session
    from notifications.queue import push_notification

    try:
        # 标记为 evaluating
        async with get_scoped_session() as session:
            result = await session.execute(
                select(QuizAttempt).where(QuizAttempt.id == attempt_id)
            )
            attempt = result.scalar_one_or_none()
            if not attempt:
                logger.error("Background eval: attempt %s not found", attempt_id)
                return
            attempt.status = "evaluating"
            attempt.draft_updated_at = datetime.now(timezone.utc)
            await session.commit()

        # 调用 AI 评估（与同步流程相同的服务）
        evaluation_service = QuizEvaluationService(
            space_id=space_id,
            user_id=user_id,
            is_collaborative=is_collaborative,
        )
        evaluation_result = await evaluation_service.evaluate_quiz(
            quiz_id=quiz_id,
            quiz_topic=quiz_topic,
            difficulty_level=quiz_difficulty,
            questions=questions_snapshot,
            user_answers=user_answers,
        )

        # 序列化结果
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

        # 更新 attempt 记录
        async with get_scoped_session() as session:
            result = await session.execute(
                select(QuizAttempt).where(QuizAttempt.id == attempt_id)
            )
            attempt = result.scalar_one()
            attempt.status = "completed"
            attempt.score = evaluation_result.score
            attempt.total_score = evaluation_result.total_score
            attempt.strengths = evaluation_result.strengths
            attempt.weaknesses = evaluation_result.weaknesses
            attempt.suggestions = evaluation_result.suggestions
            attempt.question_results = question_results_data
            attempt.debug_info = debug_info_data
            attempt.draft_updated_at = datetime.now(timezone.utc)
            await session.commit()

        # 推送通知
        await push_notification(user_id, {
            "type": "quiz_evaluation_complete",
            "data": {
                "quiz_id": str(quiz_id),
                "attempt_id": str(attempt_id),
                "quiz_topic": quiz_topic,
                "score": evaluation_result.score,
                "total_score": evaluation_result.total_score,
                "status": "completed",
            },
        })

        # 记录活动（fire-and-forget）
        from activity.service import record_quiz_activity

        task = asyncio.create_task(
            record_quiz_activity(
                user_id=user_id,
                quiz_topic=quiz_topic,
                quiz_space_id=space_id,
                quiz_space_name=space_name,
                score=evaluation_result.score,
                total_score=evaluation_result.total_score,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        # SM-2 反馈：如果是复习测试题，更新复习间隔
        if is_review_quiz:
            sm2_task = asyncio.create_task(
                _trigger_sm2_feedback(
                    user_id=user_id,
                    quiz_id=quiz_id,
                    score=evaluation_result.score,
                    total_score=evaluation_result.total_score,
                )
            )
            _background_tasks.add(sm2_task)
            sm2_task.add_done_callback(_background_tasks.discard)

        logger.info(
            "Background quiz evaluation completed: attempt=%s score=%d/%d",
            attempt_id,
            evaluation_result.score,
            evaluation_result.total_score,
        )

    except Exception:
        logger.exception("Background quiz evaluation failed: attempt=%s", attempt_id)

        # 标记为 failed
        try:
            async with get_scoped_session() as session:
                result = await session.execute(
                    select(QuizAttempt).where(QuizAttempt.id == attempt_id)
                )
                attempt = result.scalar_one_or_none()
                if attempt:
                    attempt.status = "failed"
                    attempt.draft_updated_at = datetime.now(timezone.utc)
                    await session.commit()
        except Exception:
            logger.exception("Failed to mark attempt as failed: %s", attempt_id)

        # 推送失败通知
        try:
            await push_notification(user_id, {
                "type": "quiz_evaluation_complete",
                "data": {
                    "quiz_id": str(quiz_id),
                    "attempt_id": str(attempt_id),
                    "quiz_topic": quiz_topic,
                    "score": 0,
                    "total_score": 0,
                    "status": "failed",
                },
            })
        except Exception:
            logger.exception("Failed to push failure notification: %s", attempt_id)


async def _trigger_sm2_feedback(
    user_id: UUID,
    quiz_id: UUID,
    score: int,
    total_score: int,
) -> None:
    """复习测试题完成后，触发 SM-2 间隔更新（fire-and-forget）。"""
    from db.database import get_scoped_session
    from db.models import ReviewSchedule
    from review.service import complete_review_with_quiz_score

    try:
        async with get_scoped_session() as session:
            result = await session.execute(
                select(ReviewSchedule).where(
                    ReviewSchedule.review_quiz_id == quiz_id,
                    ReviewSchedule.user_id == user_id,
                    ReviewSchedule.status == "pending",
                )
            )
            reviews = result.scalars().all()

        for review in reviews:
            await complete_review_with_quiz_score(
                user_id=user_id,
                review_id=review.id,
                quiz_score=score,
                quiz_total=total_score,
            )
            logger.info(
                "SM-2 feedback: review=%s quiz=%s score=%d/%d",
                review.id, quiz_id, score, total_score,
            )
    except Exception:
        logger.exception(
            "SM-2 feedback failed: quiz=%s user=%s", quiz_id, user_id,
        )
