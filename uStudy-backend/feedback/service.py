"""Feedback service for handling user feedback submissions."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.prompt_builder import PromptBuilder
from config import get_settings
from db.models import Conversation, Message, Space
from feedback.email_service import FeedbackEmailService
from feedback.models import ChatMode, Feedback
from feedback.schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)

# Rate limit: max 5 feedbacks per user per 5 minutes
RATE_LIMIT_WINDOW_MINUTES = 5
RATE_LIMIT_MAX_REQUESTS = 5


class FeedbackService:
    """Service for managing user feedback."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.settings = get_settings()
        self.email_service = FeedbackEmailService(self.settings)
        self.prompt_builder = PromptBuilder()

    async def submit_feedback(
        self,
        user_id: UUID,
        user_email: str,
        user_nickname: str,
        request: FeedbackRequest,
        background_tasks: BackgroundTasks,
    ) -> FeedbackResponse:
        """Submit user feedback.

        Saves feedback to database and sends email notification.
        Email failures don't block the response.

        Args:
            user_id: The user's ID
            user_email: The user's email
            user_nickname: The user's display name
            request: The feedback request data
            background_tasks: FastAPI background tasks for async email sending

        Returns:
            FeedbackResponse indicating success/failure
        """
        try:
            # Check rate limit
            is_rate_limited = await self._check_rate_limit(user_id)
            if is_rate_limited:
                return FeedbackResponse(
                    success=False,
                    message="提交过于频繁，请稍后再试",
                )

            # Determine chat mode enum
            chat_mode = (
                ChatMode.SPACE_CHAT
                if request.chat_mode == "space_chat"
                else ChatMode.QUICK_CHAT
            )

            # Parse message_id if it's a valid UUID string
            message_id = None
            if request.message_id:
                try:
                    message_id = UUID(request.message_id)
                except (ValueError, TypeError):
                    pass

            # Get LLM context from the message (contains full API request/response)
            llm_context = await self._get_llm_context(message_id)

            # Get system prompt as fallback (for messages without llm_context)
            system_prompt = None
            if not llm_context:
                system_prompt = await self._get_system_prompt(
                    conversation_id=request.conversation_id,
                    chat_mode=chat_mode,
                )

            # Build complete conversation data
            conversation_data = {
                "messages": request.conversation_history,
                "system_prompt": system_prompt,
                "llm_context": llm_context,
            }

            # Create feedback record
            feedback = Feedback(
                user_id=user_id,
                conversation_id=request.conversation_id,
                message_id=message_id,
                chat_mode=chat_mode,
                space_name=request.space_name,
                feedback_type=request.feedback_type or "report",
                feedback_content=request.feedback_content,
                conversation_history=conversation_data,
                user_email=user_email,
                user_nickname=user_nickname,
            )

            self.db.add(feedback)
            await self.db.commit()

            logger.info(
                f"Feedback saved: user={user_email}, mode={chat_mode.value}, "
                f"id={feedback.id}"
            )

            # Schedule email notification as background task (runs after response)
            background_tasks.add_task(
                self._send_email_notification,
                user_email=user_email,
                user_nickname=user_nickname,
                chat_mode=request.chat_mode,
                space_name=request.space_name,
                feedback_type=request.feedback_type or "report",
                feedback_content=request.feedback_content,
                conversation_history=request.conversation_history,
                system_prompt=system_prompt,
                llm_context=llm_context,
            )

            return FeedbackResponse(
                success=True,
                message="Feedback submitted successfully",
            )

        except Exception:
            logger.exception("Failed to submit feedback")
            await self.db.rollback()
            return FeedbackResponse(
                success=False,
                message="Failed to submit feedback. Please try again.",
            )

    async def _check_rate_limit(self, user_id: UUID) -> bool:
        """Check if user has exceeded the feedback rate limit.

        Returns True if rate limited, False otherwise.
        """
        try:
            window_start = datetime.now(timezone.utc) - timedelta(
                minutes=RATE_LIMIT_WINDOW_MINUTES
            )
            result = await self.db.execute(
                select(func.count(Feedback.id)).where(
                    Feedback.user_id == user_id,
                    Feedback.created_at > window_start,
                )
            )
            recent_count = result.scalar() or 0
            return recent_count >= RATE_LIMIT_MAX_REQUESTS
        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            # Fail open - allow the request if rate limit check fails
            return False

    async def _get_system_prompt(
        self,
        conversation_id: Optional[UUID],
        chat_mode: ChatMode,
    ) -> Optional[str]:
        """Get the system prompt used for this conversation.

        Args:
            conversation_id: The conversation ID (may be None)
            chat_mode: The chat mode (quick_chat or space_chat)

        Returns:
            The system prompt string, or None if unavailable
        """
        try:
            if chat_mode == ChatMode.QUICK_CHAT:
                # Quick chat uses a standard prompt
                return self.prompt_builder.build_quick_chat_prompt(with_tools=True)

            # For space chat, we need to get the space info
            if conversation_id:
                result = await self.db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()

                if conversation and conversation.space_id:
                    space_result = await self.db.execute(
                        select(Space).where(Space.id == conversation.space_id)
                    )
                    space = space_result.scalar_one_or_none()

                    if space:
                        return self.prompt_builder.build_system_prompt(
                            space_id=space.id,
                            space_name=space.name,
                        )

            # Fallback to generic quick chat prompt
            return self.prompt_builder.build_quick_chat_prompt(with_tools=True)

        except Exception as e:
            logger.warning(f"Failed to get system prompt: {e}")
            return None

    async def _get_llm_context(
        self,
        message_id: Optional[UUID],
    ) -> Optional[dict[str, Any]]:
        """Get the complete LLM API context from the message.

        Args:
            message_id: The AI message ID that was reported

        Returns:
            The llm_context dict containing full API request/response, or None
        """
        if not message_id:
            return None

        try:
            result = await self.db.execute(
                select(Message.llm_context).where(Message.id == message_id)
            )
            llm_context = result.scalar_one_or_none()
            return llm_context
        except Exception as e:
            logger.warning(f"Failed to get LLM context: {e}")
            return None

    def _send_email_notification(
        self,
        user_email: str,
        user_nickname: str,
        chat_mode: str,
        space_name: Optional[str],
        feedback_type: str,
        feedback_content: str,
        conversation_history: list[dict[str, Any]],
        system_prompt: Optional[str],
        llm_context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Send email notification for feedback.

        This runs as a background task (sync function for BackgroundTasks).
        """
        import asyncio

        async def _async_send():
            try:
                success = await self.email_service.send_feedback_email(
                    user_email=user_email,
                    user_nickname=user_nickname,
                    chat_mode=chat_mode,
                    space_name=space_name,
                    feedback_type=feedback_type,
                    feedback_content=feedback_content,
                    conversation_history=conversation_history,
                    system_prompt=system_prompt,
                    llm_context=llm_context,
                )
                if success:
                    logger.info("Feedback email sent successfully")
                else:
                    logger.warning("Failed to send feedback email")
            except Exception:
                logger.exception("Error sending feedback email")

        # Run the async function in the event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_async_send())
            else:
                loop.run_until_complete(_async_send())
        except RuntimeError:
            # No event loop, create a new one
            asyncio.run(_async_send())
