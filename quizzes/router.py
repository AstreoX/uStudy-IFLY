"""Quiz 模块 API 路由"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from quizzes.schemas import (
    DebugInfoResponse,
    DebugStepResponse,
    QuestionResultResponse,
    QuizAttemptResponse,
    QuizDetailResponse,
    QuizEvaluationResponse,
    QuizListItemResponse,
    QuizSubmitRequest,
)
from quizzes.service import (
    QuizAccessDeniedError,
    QuizAlreadyAttemptedError,
    QuizAttemptNotFoundError,
    QuizNotFoundError,
    QuizService,
)

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


@router.get(
    "",
    response_model=list[QuizListItemResponse],
    summary="获取空间所有测验",
    description="获取指定学习空间的所有测验列表，包含作答状态。",
)
async def get_quizzes_by_space(
    space_id: UUID = Query(..., description="学习空间 ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[QuizListItemResponse]:
    """
    获取空间所有测验

    - **space_id**: 学习空间 ID

    返回测验列表，每条包含作答状态和得分。
    """
    service = QuizService(db)

    try:
        return await service.get_quizzes_by_space(user.id, space_id)
    except QuizAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该空间"},
        )


@router.get(
    "/{quiz_id}",
    response_model=QuizDetailResponse,
    summary="获取测试详情",
    description="获取测试的详细信息，包含所有题目。",
)
async def get_quiz_detail(
    quiz_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizDetailResponse:
    """
    获取测试详情

    - **quiz_id**: 测试 ID

    返回测试信息和所有题目。
    """
    service = QuizService(db)

    try:
        return await service.get_quiz_detail(user.id, quiz_id)
    except QuizNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUIZ_NOT_FOUND", "message": "测试不存在"},
        )
    except QuizAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "QUIZ_ACCESS_DENIED", "message": "无权访问该测试"},
        )


@router.post(
    "/{quiz_id}/submit",
    response_model=QuizEvaluationResponse,
    summary="提交答卷并获取评估结果",
    description="提交用户的答案，系统会自动评分并返回整卷评估结果。",
)
async def submit_quiz(
    quiz_id: UUID,
    request: QuizSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizEvaluationResponse:
    """
    提交答卷并获取评估结果

    - **quiz_id**: 测试 ID
    - **request**: 包含用户答案列表

    返回评估结果，包括得分、优缺点分析、提升建议和逐题评估。
    """
    service = QuizService(db)

    try:
        result = await service.submit_and_evaluate(user.id, quiz_id, request.answers)

        # 构建调试信息响应（如有）
        debug_info_response = None
        if result.debug_info:
            debug_info_response = DebugInfoResponse(
                steps=[
                    DebugStepResponse(
                        step_number=s.step_number,
                        step_name=s.step_name,
                        status=s.status,
                        duration_ms=s.duration_ms,
                        details=s.details,
                        metadata=s.metadata,
                    )
                    for s in result.debug_info.steps
                ],
                model_name=result.debug_info.model_name,
                total_duration_ms=result.debug_info.total_duration_ms,
            )

        return QuizEvaluationResponse(
            quiz_id=result.quiz_id,
            score=result.score,
            total_score=result.total_score,
            strengths=result.strengths,
            weaknesses=result.weaknesses,
            suggestions=result.suggestions,
            question_results=[
                QuestionResultResponse(
                    id=qr.question_id,
                    order=qr.order,
                    question_type=qr.question_type,
                    title=qr.question_stem,
                    options=qr.options,
                    status=qr.status,
                    score=qr.score,
                    max_score=qr.max_score,
                    user_answer=qr.user_answer,
                    correct_answer=qr.correct_answer,
                    ai_evaluation=qr.ai_evaluation,
                )
                for qr in result.question_results
            ],
            debug_info=debug_info_response,
        )
    except QuizNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUIZ_NOT_FOUND", "message": "测试不存在"},
        )
    except QuizAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "QUIZ_ACCESS_DENIED", "message": "无权访问该测试"},
        )
    except QuizAlreadyAttemptedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "QUIZ_ALREADY_ATTEMPTED", "message": "该测试已经作答过"},
        )


@router.get(
    "/{quiz_id}/attempt",
    response_model=QuizAttemptResponse,
    summary="获取作答记录",
    description="获取用户对该测验的作答记录和评估结果。",
)
async def get_quiz_attempt(
    quiz_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizAttemptResponse:
    """
    获取作答记录

    - **quiz_id**: 测试 ID

    返回作答记录，包括得分、评估结果和逐题详情。
    """
    service = QuizService(db)

    try:
        return await service.get_quiz_attempt(user.id, quiz_id)
    except QuizNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUIZ_NOT_FOUND", "message": "测试不存在"},
        )
    except QuizAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "QUIZ_ACCESS_DENIED", "message": "无权访问该测试"},
        )
    except QuizAttemptNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ATTEMPT_NOT_FOUND", "message": "作答记录不存在"},
        )


@router.delete(
    "/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除测验",
    description="删除测验及其所有关联数据（题目、作答记录）。",
)
async def delete_quiz(
    quiz_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    删除测验

    - **quiz_id**: 测试 ID

    删除成功返回 204 No Content。
    """
    service = QuizService(db)

    try:
        await service.delete_quiz(user.id, quiz_id)
    except QuizNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUIZ_NOT_FOUND", "message": "测试不存在"},
        )
    except QuizAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "QUIZ_ACCESS_DENIED", "message": "无权删除该测试"},
        )
