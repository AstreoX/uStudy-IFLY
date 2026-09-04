"""Feedback Pydantic schemas."""

import json
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class MessageHistoryItem(BaseModel):
    """A single message in conversation history."""

    role: str = Field(..., description="Message role: user or assistant")
    content: str = Field(..., description="Message content")
    created_at: Optional[str] = Field(None, description="ISO format timestamp")
    tool_calls: Optional[list[dict[str, Any]]] = Field(
        None, description="Tool calls made in this message"
    )
    segments: Optional[list[dict[str, Any]]] = Field(
        None, description="Message segments for AI responses with tool calls"
    )


class FeedbackRequest(BaseModel):
    """Request schema for submitting feedback."""

    conversation_id: Optional[UUID] = Field(
        None, description="The conversation ID (may be null for new conversations)"
    )
    message_id: Optional[str] = Field(
        None, description="The specific AI message being reported (UUID string or null)"
    )
    chat_mode: str = Field(
        "space_chat",
        description="Chat mode: space_chat",
        pattern="^space_chat$",
    )
    space_name: Optional[str] = Field(
        None,
        max_length=200,
        description="Learning space name if in space_chat mode",
    )
    feedback_type: Optional[str] = Field(
        None,
        pattern="^(positive|negative|report)$",
        description="Feedback type: positive (like), negative (dislike), report (manual report)",
    )
    feedback_content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's feedback description",
    )
    conversation_history: list[dict[str, Any]] = Field(
        ...,
        max_length=200,
        description="Complete conversation data with timestamps (max 200 messages)",
    )

    @field_validator("conversation_history")
    @classmethod
    def validate_history_size(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate conversation history size to prevent abuse."""
        raw = json.dumps(v, ensure_ascii=False)
        if len(raw) > 500_000:  # 500KB limit
            raise ValueError("conversation_history exceeds maximum allowed size (500KB)")
        return v

    @field_validator("message_id")
    @classmethod
    def validate_message_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate message_id is a valid UUID string or null."""
        if v is None:
            return None
        # Check if it's a valid UUID format
        try:
            UUID(v)
            return v
        except (ValueError, TypeError):
            # If not a valid UUID (e.g., an integer), return None
            return None


class FeedbackResponse(BaseModel):
    """Response schema for feedback submission."""

    success: bool
    message: str
