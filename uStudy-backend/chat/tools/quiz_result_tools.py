"""Quiz Result Tools - View quiz scores and detailed attempt results"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from chat.tools.base import ToolResult
from db.database import get_scoped_session
from db.models import Quiz
from quizzes.service import (
    QuizAccessDeniedError,
    QuizAttemptNotFoundError,
    QuizNotFoundError,
    QuizService,
)

logger = logging.getLogger(__name__)


# ============ Tool Definitions (OpenAI Function Calling Format) ============


QUIZ_RESULT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "view_quiz_results",
            "description": "查看当前学习空间内所有测验的成绩列表。当用户询问测验表现、学习进度、考试成绩时调用此工具。返回每个测验的标题、主题、难度、得分等信息。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_quiz_attempt_detail",
            "description": "查看某个测验的详细作答结果，包括得分分析、强项、弱项、建议和逐题摘要。当用户要求分析某次测验的具体表现时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "quiz_id": {
                        "type": "string",
                        "description": "测验 ID（UUID 格式），可从 view_quiz_results 的返回结果中获取",
                    },
                },
                "required": ["quiz_id"],
            },
        },
    },
]

QUIZ_RESULT_TOOL_NAMES = {"view_quiz_results", "view_quiz_attempt_detail"}


# ============ Executor ============


class QuizResultToolExecutor:
    """Executor for quiz result viewing tools"""

    def __init__(self, user_id: UUID, space_id: UUID) -> None:
        self.user_id = user_id
        self.space_id = space_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a quiz result tool and return result."""
        try:
            if tool_name == "view_quiz_results":
                return await self._view_quiz_results()
            elif tool_name == "view_quiz_attempt_detail":
                return await self._view_quiz_attempt_detail(arguments)
            else:
                return ToolResult(
                    success=False, data=None, message=f"未知的工具: {tool_name}"
                )
        except (QuizNotFoundError, QuizAccessDeniedError, QuizAttemptNotFoundError) as e:
            return ToolResult(success=False, data=None, message=str(e))
        except Exception as e:
            logger.error(f"Quiz result tool error: {e}", exc_info=True)
            return ToolResult(success=False, data=None, message=f"执行错误: {str(e)}")

    async def _view_quiz_results(self) -> ToolResult:
        """List all quizzes in the current space with scores."""
        async with get_scoped_session() as db:
            service = QuizService(db)
            quizzes = await service.get_quizzes_by_space(self.user_id, self.space_id)

        if not quizzes:
            return ToolResult(
                success=True,
                data={"quizzes": []},
                message="当前学习空间没有测验",
            )

        quiz_list = [
            {
                "id": str(q.id),
                "title": q.title,
                "topic": q.topic,
                "difficulty": q.difficulty,
                "score": q.attempt_score,
                "total_score": q.attempt_total_score,
                "has_attempt": q.has_attempt,
                "attempt_status": q.attempt_status,
                "created_at": q.created_at.strftime("%Y-%m-%d"),
            }
            for q in quizzes
        ]

        attempted = sum(1 for q in quizzes if q.has_attempt)
        return ToolResult(
            success=True,
            data={"quizzes": quiz_list},
            message=f"共 {len(quizzes)} 个测验，已作答 {attempted} 个",
        )

    async def _view_quiz_attempt_detail(self, args: dict) -> ToolResult:
        """Get detailed results for a specific quiz attempt."""
        quiz_id_str = args.get("quiz_id", "")
        if not quiz_id_str:
            return ToolResult(
                success=False, data=None, message="缺少 quiz_id 参数"
            )

        try:
            quiz_id = UUID(quiz_id_str)
        except ValueError:
            return ToolResult(
                success=False, data=None, message=f"无效的 quiz_id: {quiz_id_str}"
            )

        async with get_scoped_session() as db:
            service = QuizService(db)
            attempt = await service.get_quiz_attempt(self.user_id, quiz_id)
            # Fetch quiz title for frontend display
            quiz_row = await db.execute(select(Quiz.title).where(Quiz.id == quiz_id))
            quiz_title = quiz_row.scalar_one_or_none() or ""

        questions_detail = [
            {
                "order": qr.order,
                "type": qr.question_type,
                "title": qr.title,
                "options": qr.options,
                "user_answer": qr.user_answer,
                "correct_answer": qr.correct_answer,
                "status": qr.status,
                "score": f"{qr.score}/{qr.max_score}",
                "ai_evaluation": qr.ai_evaluation,
            }
            for qr in attempt.question_results
        ]

        percentage = (
            round(attempt.score / attempt.total_score * 100)
            if attempt.total_score > 0
            else 0
        )

        return ToolResult(
            success=True,
            data={
                "quiz_title": quiz_title,
                "score": attempt.score,
                "total_score": attempt.total_score,
                "percentage": percentage,
                "strengths": attempt.strengths,
                "weaknesses": attempt.weaknesses,
                "suggestions": attempt.suggestions,
                "questions": questions_detail,
            },
            message=f"测验得分: {attempt.score}/{attempt.total_score} ({percentage}%)",
        )
