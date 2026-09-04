"""API usage tracking data models."""

import enum
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class UsageType(str, enum.Enum):
    """API 用量类型"""

    CHAT_LLM = "chat_llm"  # 聊天 LLM 调用
    EMBEDDING = "embedding"  # Embedding 调用
    AGENT_LLM = "agent_llm"  # Agent 异步任务 LLM 调用


class ApiUsageLog(Base):
    """API 用量日志表"""

    __tablename__ = "api_usage_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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
            values_callable=lambda x: [
                e.value for e in x
            ],  # Use enum value (lowercase)
        ),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Token 用量
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 估算成本 (以美分为单位，方便整数存储)
    estimated_cost_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    source_module: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_operation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    billable: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    charge_cents: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    billing_status: Mapped[str] = mapped_column(
        String(32), default="not_charged", server_default="not_charged", nullable=False
    )
    wallet_transaction_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)

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
        Index("ix_api_usage_logs_source", "source_module", "source_operation"),
        Index("ix_api_usage_logs_idempotency_key", "idempotency_key", unique=True),
    )


class AppUsageDaily(Base):
    """每日 APP 使用时长记录（心跳累加）"""

    __tablename__ = "app_usage_daily"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_app_usage_daily_user_date"),
        Index("ix_app_usage_daily_user_date", "user_id", "usage_date"),
    )


class AiRequestLog(Base):
    """AI provider request observability log."""

    __tablename__ = "ai_request_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    model: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_module: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_operation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttft_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_chunk_gap_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    retry_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_result_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ai_request_logs_created_at", "created_at"),
        Index("ix_ai_request_logs_status_created", "status", "created_at"),
        Index("ix_ai_request_logs_model_created", "model", "created_at"),
        Index(
            "ix_ai_request_logs_source_created",
            "source_module",
            "source_operation",
            "created_at",
        ),
        Index("ix_ai_request_logs_user_created", "user_id", "created_at"),
    )
