"""API usage tracking data models."""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class UsageType(str, enum.Enum):
    """API 用量类型"""

    CHAT_LLM = "chat_llm"  # 聊天 LLM 调用
    QUICK_CHAT_LLM = "quick_chat_llm"  # 快速聊天 LLM 调用
    EMBEDDING = "embedding"  # Embedding 调用
    AGENT_LLM = "agent_llm"  # Agent 异步任务 LLM 调用


class ApiUsageLog(Base):
    """API 用量日志表"""

    __tablename__ = "api_usage_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )

    usage_type: Mapped[UsageType] = mapped_column(
        Enum(
            UsageType,
            name="usagetype",
            values_callable=lambda x: [e.value for e in x],  # Use enum value (lowercase)
        ),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Token 用量
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 估算成本 (以美分为单位，方便整数存储)
    estimated_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 请求元数据
    request_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        # Composite index (user_id, created_at) covers user_id-only queries
        Index("ix_api_usage_logs_user_created", "user_id", "created_at"),
        Index("ix_api_usage_logs_usage_type", "usage_type"),
        Index("ix_api_usage_logs_created_at", "created_at"),
    )
