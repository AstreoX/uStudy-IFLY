"""Feedback API router."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from feedback.schemas import FeedbackRequest, FeedbackResponse
from feedback.service import FeedbackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("/submit", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Submit user feedback for an AI response.

    Saves the feedback to database and sends an email notification.

    Args:
        request: The feedback data including conversation history
        background_tasks: FastAPI background tasks for async operations
        user: The authenticated user
        db: Database session

    Returns:
        FeedbackResponse with success status
    """
    logger.info(
        f"Feedback submission: user={user.email}, mode={request.chat_mode}, "
        f"conversation={request.conversation_id}"
    )

    service = FeedbackService(db)
    return await service.submit_feedback(
        user_id=user.id,
        user_email=user.email,
        user_nickname=user.nickname,
        request=request,
        background_tasks=background_tasks,
    )
