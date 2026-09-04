"""Feedback data models."""

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class ChatMode(str, enum.Enum):
    """Chat mode enumeration."""

    SPACE_CHAT = "space_chat"


class Feedback(Base):
    """User feedback for AI responses.

    Stores user-submitted feedback along with complete conversation context
    for debugging and improving AI responses.
    """

    __tablename__ = "feedbacks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="The specific AI message that triggered the feedback",
    )
    chat_mode: Mapped[ChatMode] = mapped_column(
        Enum(
            ChatMode,
            name="chatmode",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        comment="space_chat",
    )
    space_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Learning space name if space_chat mode",
    )
    feedback_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default="report",
        server_default="report",
        comment="Feedback type: positive, negative, report",
    )
    feedback_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="User's feedback description",
    )
    conversation_history: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Complete conversation data including messages, tool calls, and system prompts",
    )
    user_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User's email for reference",
    )
    user_nickname: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="User's display name",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
    )
