"""数据库表模型"""

import enum
from datetime import date, datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSON, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # 如果 pgvector 未安装，使用占位符
    Vector = None

from db.database import Base

# ============ 枚举定义 ============


class SubscriptionTier(str, enum.Enum):
    """订阅等级"""

    FREE = "FREE"
    BASIC = "BASIC"
    PREMIUM = "PREMIUM"
    ALPHA = "ALPHA"  # Alpha 内测用户
    ULTRA = "ULTRA"  # Ultra 高级用户


class MessageRole(str, enum.Enum):
    """消息角色"""

    USER = "user"
    ASSISTANT = "assistant"


class MessageResponseStatus(str, enum.Enum):
    """AI 回复状态"""

    COMPLETED = "completed"
    STOPPED = "stopped"


class ConversationKind(str, enum.Enum):
    """Conversation runtime isolation boundary."""

    LEARNING = "learning"
    TEACHER_PRESENTATION = "teacher_presentation"


class PresentationRevisionStatus(str, enum.Enum):
    DRAFT = "draft"
    COMPLETED = "completed"
    FAILED = "failed"


class PresentationRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    RECOVERING = "recovering"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PresentationAssetKind(str, enum.Enum):
    SOURCE = "source"
    TEMPLATE = "template"
    GENERATED_IMAGE = "generated_image"
    PREVIEW = "preview"
    PPTX = "pptx"


class AgentTodoStatus(str, enum.Enum):
    """Agent 对话内 todo 状态"""

    PENDING = "pending"
    COMPLETED = "completed"


class EdgeType(str, enum.Enum):
    """边类型"""

    KNOWLEDGE_TREE = "knowledge_tree"
    LEARNING_PATH = "learning_path"
    ADVANCED = "advanced"


class AgentTaskStatus(str, enum.Enum):
    """Agent 任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AgentTaskType(str, enum.Enum):
    """Agent 任务类型"""

    GENERATE_KNOWLEDGE_GRAPH = "generate_knowledge_graph"
    GENERATE_QUIZ = "generate_quiz"
    EXPAND_NODE = "expand_node"
    GENERATE_ARTIFACT = "generate_artifact"
    GENERATE_KNOWLEDGE_GRAPH_FROM_DOCUMENTS = "generate_knowledge_graph_from_documents"
    GENERATE_REVIEW_QUIZ = "generate_review_quiz"


class QuestionType(str, enum.Enum):
    """题目类型"""

    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class DocumentType(str, enum.Enum):
    """文档类型"""

    DOCUMENT = "document"
    LINK = "link"


class AttachmentType(str, enum.Enum):
    """附件类型"""

    IMAGE = "image"
    FILE = "file"


class MemoryType(str, enum.Enum):
    """记忆类型"""

    LONG_TERM = "long_term"  # 用户长期记忆（跨所有学习空间）
    SPACE = "space"  # 学习空间记忆（特定空间内）


class DifficultyLevel(str, enum.Enum):
    """难度级别"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class VerificationCodePurpose(str, enum.Enum):
    """验证码用途"""

    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"


class ProcessingStatus(str, enum.Enum):
    """文档处理状态"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OrderStatus(str, enum.Enum):
    """支付订单状态"""

    PENDING = "pending"
    PAID = "paid"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BillingCycle(str, enum.Enum):
    """计费周期"""

    MONTHLY = "monthly"
    SEMESTER = "semester"
    YEARLY = "yearly"


class WalletTransactionType(str, enum.Enum):
    """钱包流水类型"""

    CREDIT_PURCHASE = "credit_purchase"
    LLM_CHARGE = "llm_charge"
    SUBSCRIPTION_GRANT = "subscription_grant"
    REGISTRATION_GRANT = "registration_grant"
    INVITE_REWARD = "invite_reward"
    INVITE_SIGNUP_BONUS = "invite_signup_bonus"
    ADMIN_ADJUSTMENT = "admin_adjustment"
    REFUND = "refund"


class NoteAttachmentType(str, enum.Enum):
    """笔记附件类型"""

    IMAGE = "image"
    FILE = "file"
    LINK = "link"


class NotificationType(str, enum.Enum):
    """应用内通知类型"""

    REVIEW_QUIZ_READY = "review_quiz_ready"
    REVIEW_REMINDER = "review_reminder"
    INACTIVITY_CARE = "inactivity_care"
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    ASSIGNMENT_GRADED = "assignment_graded"
    ASSIGNMENT_GRADE_UPDATED = "assignment_grade_updated"


class SpaceMemberRole(str, enum.Enum):
    """协作空间成员角色"""

    OWNER = "owner"
    TEACHER = "teacher"
    MEMBER = "member"


class ShareMode(str, enum.Enum):
    """分享模式"""

    CLONE = "clone"
    COLLABORATIVE = "collaborative"


class FolderContentType(str, enum.Enum):
    """文件夹内容类型"""

    NOTES = "notes"
    QUIZZES = "quizzes"


# ============ 表模型 ============


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    apple_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False
    )
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    spaces: Mapped[list["Space"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("uq_users_username_lower", func.lower(username), unique=True),
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_apple_id", "apple_id", unique=True),
    )


class Space(Base):
    """学习空间表"""

    __tablename__ = "spaces"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    learning_preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="学习偏好设置"
    )
    memory_sharing_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="是否开启记忆共享（允许其他空间检索本空间记忆）",
    )
    tool_mode: Mapped[str] = mapped_column(
        String(10),
        default="auto",
        server_default="auto",
        nullable=False,
        comment="工具模式：auto（AI按需加载）/ manual（用户自选）",
    )
    enabled_tools: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="manual 模式下启用的工具名称数组",
    )
    is_collaborative: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="是否为协作学习空间",
    )
    review_mode: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="复习模式: 0=disabled, 1=suggestions, 2=quiz_no_email, 3=full",
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="spaces")
    nodes: Mapped[list["Node"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
    edges: Mapped[list["Edge"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
    documents: Mapped[list["SpaceDocument"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )
    members: Mapped[list["SpaceMember"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (Index("ix_spaces_user_id", "user_id"),)


class Folder(Base):
    """文件夹表 — 笔记和测试题共用，通过 content_type 区分"""

    __tablename__ = "folders"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
    )
    content_type: Mapped[FolderContentType] = mapped_column(
        Enum(FolderContentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    children: Mapped[list["Folder"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped[Optional["Folder"]] = relationship(
        back_populates="children", remote_side=[id]
    )

    __table_args__ = (
        Index("ix_folders_space_id", "space_id"),
        Index("ix_folders_parent_id", "parent_id"),
    )


class Conversation(Base):
    """对话表"""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[ConversationKind] = mapped_column(
        Enum(
            ConversationKind,
            name="conversationkind",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
        default=ConversationKind.LEARNING,
        server_default=ConversationKind.LEARNING.value,
    )
    artifact_note_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="conversations")
    space: Mapped["Space"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    agent_todos: Mapped[list["ConversationAgentTodo"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationAgentTodo.sort_order",
    )

    # 索引
    __table_args__ = (
        Index("ix_conversations_user_created", "user_id", "created_at"),
        Index("ix_conversations_space_id", "space_id"),
        Index("ix_conversations_kind", "kind"),
        Index("ix_conversations_artifact_note_id", "artifact_note_id"),
    )


class Message(Base):
    """消息表"""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    llm_context: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete LLM API request/response context for debugging and feedback",
    )
    tool_calls: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Extracted tool call data for frontend rendering",
    )
    citations: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Structured citation metadata for source attribution",
    )
    response_status: Mapped[MessageResponseStatus] = mapped_column(
        Enum(
            MessageResponseStatus,
            name="messageresponsestatus",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=MessageResponseStatus.COMPLETED,
        server_default=MessageResponseStatus.COMPLETED.value,
        comment="Assistant response generation status",
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), nullable=False
    )

    # 关系
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )


class ConversationAgentTodo(Base):
    """Conversation-scoped agent todo items."""

    __tablename__ = "conversation_agent_todos"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AgentTodoStatus.PENDING.value,
        server_default=AgentTodoStatus.PENDING.value,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="agent_todos")

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "task_id",
            name="uq_conversation_agent_todos_conversation_task_id",
        ),
        UniqueConstraint(
            "conversation_id",
            "sort_order",
            name="uq_conversation_agent_todos_conversation_sort_order",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_conversation_agent_todos_status",
        ),
        Index(
            "ix_conversation_agent_todos_conversation_sort",
            "conversation_id",
            "sort_order",
        ),
    )


class MessageAttachment(Base):
    """消息附件表"""

    __tablename__ = "message_attachments"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    message_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,  # 可为空，支持孤儿附件
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    attachment_type: Mapped[AttachmentType] = mapped_column(
        ENUM("image", "file", name="attachmenttype", create_type=False), nullable=False
    )

    # 文件信息
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # 图片特定字段
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 文件内容提取字段
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # metadata 格式: {
    #   "extracted_at": "ISO timestamp",
    #   "token_count": int,
    #   "truncated": bool,
    #   "extraction_error": str | None
    # }

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    message: Mapped[Optional["Message"]] = relationship(back_populates="attachments")
    user: Mapped["User"] = relationship()

    # 索引
    __table_args__ = (
        Index("ix_message_attachments_message_id", "message_id"),
        Index("ix_message_attachments_user_id", "user_id"),
        Index("ix_message_attachments_created_at", "created_at"),
    )


class Node(Base):
    """知识节点表"""

    __tablename__ = "nodes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    mastery: Mapped[Optional[int]] = mapped_column(Integer, default=None, nullable=True)

    # 关系
    space: Mapped["Space"] = relationship(back_populates="nodes")

    # 索引和约束
    __table_args__ = (
        Index("ix_nodes_space_id", "space_id"),
        UniqueConstraint("space_id", "label", name="uq_nodes_space_label"),
        CheckConstraint(
            "mastery IS NULL OR (mastery >= 0 AND mastery <= 100)",
            name="ck_nodes_mastery_range",
        ),
    )


class Edge(Base):
    """知识边表"""

    __tablename__ = "edges"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_node_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_node_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[EdgeType] = mapped_column(Enum(EdgeType), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="Per-user edge owner (NULL=shared, set for LEARNING_PATH in collab spaces)",
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship(back_populates="edges")
    from_node: Mapped["Node"] = relationship(foreign_keys=[from_node_id])
    to_node: Mapped["Node"] = relationship(foreign_keys=[to_node_id])

    # 索引和约束
    # Note: The old uq_edges_unique is replaced by two partial indexes in the migration.
    # SQLAlchemy model keeps basic indexes; partial unique indexes are created in migration SQL.
    __table_args__ = (
        Index("ix_edges_space_id", "space_id"),
        Index("ix_edges_from_node", "from_node_id"),
        Index("ix_edges_to_node", "to_node_id"),
        Index("ix_edges_user_id", "user_id"),
    )


class VerificationCode(Base):
    """邮箱验证码表"""

    __tablename__ = "verification_codes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    purpose: Mapped[VerificationCodePurpose] = mapped_column(
        Enum(VerificationCodePurpose), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_verification_email_purpose", "email", "purpose"),
    )


class RefreshToken(Base):
    """Refresh Token 表（轮换机制）"""

    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replaced_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    family_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_token_hash", "token_hash"),
        Index("ix_refresh_tokens_family_id", "family_id"),
    )


class AgentTask(Base):
    """Agent 异步任务表"""

    __tablename__ = "agent_tasks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_type: Mapped[AgentTaskType] = mapped_column(
        Enum(AgentTaskType), nullable=False
    )
    status: Mapped[AgentTaskStatus] = mapped_column(
        Enum(AgentTaskStatus), default=AgentTaskStatus.PENDING, nullable=False
    )
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 关系
    user: Mapped["User"] = relationship()
    space: Mapped["Space"] = relationship()
    conversation: Mapped[Optional["Conversation"]] = relationship()

    # 索引
    __table_args__ = (
        Index("ix_agent_tasks_user_id", "user_id"),
        Index("ix_agent_tasks_space_id", "space_id"),
        Index("ix_agent_tasks_status", "status"),
    )


class Quiz(Base):
    """测试表"""

    __tablename__ = "quizzes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_task_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    folder_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel, values_callable=lambda x: [e.value for e in x]),
        default=DifficultyLevel.MEDIUM,
        nullable=False,
    )
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_review_quiz: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        comment="是否为复习系统自动生成的测试",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship()
    agent_task: Mapped[Optional["AgentTask"]] = relationship()
    questions: Mapped[list["Question"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("ix_quizzes_space_id", "space_id"),
        Index("ix_quizzes_agent_task_id", "agent_task_id"),
        Index("ix_quizzes_folder_id", "folder_id"),
    )


class Question(Base):
    """题目表"""

    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    quiz_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    question_stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[dict] = mapped_column(JSON, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    quiz: Mapped["Quiz"] = relationship(back_populates="questions")

    # 索引
    __table_args__ = (
        Index("ix_questions_quiz_id", "quiz_id"),
    )


class QuizAttempt(Base):
    """测试作答记录表"""

    __tablename__ = "quiz_attempts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    quiz_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 作答状态: in_progress -> pending -> evaluating -> completed / failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="completed"
    )

    # 原始用户答案（草稿和异步评估都复用）
    user_answers_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    current_question_index: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", default=0
    )
    draft_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 评估结果
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False)
    weaknesses: Mapped[list] = mapped_column(JSON, nullable=False)
    suggestions: Mapped[list] = mapped_column(JSON, nullable=False)
    question_results: Mapped[list] = mapped_column(JSON, nullable=False)
    debug_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    quiz: Mapped["Quiz"] = relationship()
    user: Mapped["User"] = relationship()

    # 索引和约束
    __table_args__ = (
        Index("ix_quiz_attempts_quiz_id", "quiz_id"),
        Index("ix_quiz_attempts_user_id", "user_id"),
        UniqueConstraint("quiz_id", "user_id", name="uq_quiz_attempt_once"),
    )


class Assignment(Base):
    """Teacher-authored course assignment."""

    __tablename__ = "assignments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    teacher_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    questions: Mapped[list["AssignmentQuestion"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )
    recipients: Mapped[list["AssignmentRecipient"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )
    submissions: Mapped[list["AssignmentSubmission"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_assignments_space_status_due", "space_id", "status", "due_at"),
        Index("ix_assignments_teacher", "teacher_user_id", "created_at"),
        CheckConstraint("total_score >= 0", name="ck_assignments_total_score"),
    )


class AssignmentQuestion(Base):
    """Immutable-after-publish assignment question snapshot."""

    __tablename__ = "assignment_questions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    question_type: Mapped[str] = mapped_column(String(30), nullable=False)
    question_stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[dict] = mapped_column(JSON, nullable=False)
    rubric: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    grader_type: Mapped[str] = mapped_column(String(30), nullable=False, default="rule")
    public_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    grader_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    assignment: Mapped["Assignment"] = relationship(back_populates="questions")

    __table_args__ = (
        UniqueConstraint("assignment_id", "order_index", name="uq_assignment_question_order"),
        Index("ix_assignment_questions_assignment", "assignment_id"),
        CheckConstraint("max_score > 0", name="ck_assignment_questions_score"),
    )


class AssignmentRecipient(Base):
    """Published assignment recipient snapshot and per-student extension."""

    __tablename__ = "assignment_recipients"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    due_at_override: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    assignment: Mapped["Assignment"] = relationship(back_populates="recipients")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("assignment_id", "user_id", name="uq_assignment_recipient"),
        Index("ix_assignment_recipients_user", "user_id", "assignment_id"),
    )


class AssignmentSubmission(Base):
    """One draft/submission per assignment recipient."""

    __tablename__ = "assignment_submissions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    answers_raw: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    current_question_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    draft_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    grading_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    grading_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provisional_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    teacher_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    grading_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")
    user: Mapped["User"] = relationship()
    answers: Mapped[list["AssignmentAnswer"]] = relationship(
        back_populates="submission", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("assignment_id", "user_id", name="uq_assignment_submission_once"),
        Index("ix_assignment_submissions_assignment_status", "assignment_id", "status"),
        Index("ix_assignment_submissions_user", "user_id", "assignment_id"),
    )


class AssignmentAnswer(Base):
    """Per-question grading result for an assignment submission."""

    __tablename__ = "assignment_answers"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_questions.id", ondelete="CASCADE"), nullable=False
    )
    user_answer: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    auto_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    grader_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    oj_run_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_oj_runs.id", ondelete="SET NULL"), nullable=True
    )

    submission: Mapped["AssignmentSubmission"] = relationship(back_populates="answers")
    question: Mapped["AssignmentQuestion"] = relationship()

    __table_args__ = (
        UniqueConstraint("submission_id", "question_id", name="uq_assignment_answer_question"),
        Index("ix_assignment_answers_submission", "submission_id"),
    )


class AssignmentJob(Base):
    """Durable generation/grading job with retry lease."""

    __tablename__ = "assignment_jobs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    assignment_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=True
    )
    submission_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=True
    )
    requested_by_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_assignment_jobs_claim", "status", "available_at", "lease_expires_at"),
        Index("ix_assignment_jobs_assignment", "assignment_id", "created_at"),
        Index("ix_assignment_jobs_submission", "submission_id", "created_at"),
    )


class AssignmentOjRun(Base):
    """Log-safe control-plane record for an isolated OJ manager run."""

    __tablename__ = "assignment_oj_runs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_questions.id", ondelete="CASCADE"), nullable=False
    )
    submission_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)
    manager_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    problem_version_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_assignment_oj_runs_user_created", "user_id", "created_at"),
        Index("ix_assignment_oj_runs_status", "status", "created_at"),
        Index("ix_assignment_oj_runs_submission", "submission_id", "question_id"),
    )


class AssignmentGradeAudit(Base):
    """Append-only audit trail for teacher score changes."""

    __tablename__ = "assignment_grade_audits"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False
    )
    answer_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignment_answers.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    previous_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_assignment_grade_audits_submission", "submission_id", "created_at"),)


class SpaceDocument(Base):
    """学习空间文档/链接表"""

    __tablename__ = "space_documents"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    creator_user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship(back_populates="documents")
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[creator_user_id])
    processing_task: Mapped[Optional["DocumentProcessingTask"]] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    visual_indexes: Mapped[list["PdfVisualIndex"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # 索引
    __table_args__ = (
        Index("ix_space_documents_space_id", "space_id"),
    )


class TeacherPresentationProject(Base):
    """Teacher-owned presentation workspace in one course."""

    __tablename__ = "teacher_presentation_projects"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    teacher_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    current_revision_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "teacher_presentation_revisions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_presentation_project_current_revision",
        ),
        nullable=True,
    )
    published_document_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("space_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_teacher_presentation_projects_space_teacher", "space_id", "teacher_user_id"),
        Index("ix_teacher_presentation_projects_current_revision", "current_revision_id"),
    )


class TeacherPresentationRevision(Base):
    """Immutable presentation output produced by one successful agent run."""

    __tablename__ = "teacher_presentation_revisions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_revision_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_revisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PresentationRevisionStatus] = mapped_column(
        Enum(
            PresentationRevisionStatus,
            name="presentationrevisionstatus",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
        default=PresentationRevisionStatus.DRAFT,
        server_default=PresentationRevisionStatus.DRAFT.value,
    )
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manifest: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pptx_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    preview_manifest: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("project_id", "revision_number", name="uq_presentation_revision_number"),
        Index("ix_teacher_presentation_revisions_project", "project_id", "created_at"),
    )


class TeacherPresentationRun(Base):
    """Host-side record for a sandbox Presentation Agent invocation."""

    __tablename__ = "teacher_presentation_runs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_revisions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    manager_run_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True)
    status: Mapped[PresentationRunStatus] = mapped_column(
        Enum(
            PresentationRunStatus,
            name="presentationrunstatus",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
        default=PresentationRunStatus.QUEUED,
        server_default=PresentationRunStatus.QUEUED.value,
    )
    capability_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_deadline_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_teacher_presentation_runs_project", "project_id", "created_at"),
        Index("ix_teacher_presentation_runs_status", "status"),
    )


class TeacherPresentationAsset(Base):
    """Private source or generated file; never mounted below public /uploads."""

    __tablename__ = "teacher_presentation_assets"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_revisions.id", ondelete="CASCADE"),
        nullable=True,
    )
    kind: Mapped[PresentationAssetKind] = mapped_column(
        Enum(
            PresentationAssetKind,
            name="presentationassetkind",
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    private_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    asset_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_teacher_presentation_assets_project", "project_id", "created_at"),)


class TeacherPresentationPublication(Base):
    """Append-only audit history for publishing a revision to the course library."""

    __tablename__ = "teacher_presentation_publications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("space_documents.id", ondelete="RESTRICT"), nullable=False
    )
    publisher_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_teacher_presentation_publications_project", "project_id", "created_at"),)


class TeacherPresentationEvent(Base):
    """Persisted sandbox events used for resumable SSE delivery."""

    __tablename__ = "teacher_presentation_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_presentation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_presentation_event_sequence"),
        Index("ix_teacher_presentation_events_run", "run_id", "sequence"),
    )


# ============ RAG 相关表 ============


class DocumentProcessingTask(Base):
    """文档处理任务表"""

    __tablename__ = "document_processing_tasks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("space_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(
            ProcessingStatus,
            values_callable=lambda x: [e.value for e in x],
            name="processingstatus",
        ),
        default=ProcessingStatus.PENDING,
        nullable=False,
    )
    generation: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    stage: Mapped[str] = mapped_column(
        String(40), default="queued", server_default="queued", nullable=False
    )
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processed_pages: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    asset_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    lease_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lease_token: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    warning_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # 关系
    document: Mapped["SpaceDocument"] = relationship(back_populates="processing_task")

    # 索引
    __table_args__ = (
        Index("ix_doc_processing_document_id", "document_id"),
        Index("ix_doc_processing_status", "status"),
        Index(
            "ix_doc_processing_claim",
            "status",
            "available_at",
            "lease_expires_at",
        ),
        CheckConstraint("generation >= 1", name="ck_doc_processing_generation"),
        CheckConstraint("processed_pages >= 0", name="ck_doc_processing_processed_pages"),
        CheckConstraint("asset_count >= 0", name="ck_doc_processing_asset_count"),
        CheckConstraint("attempt_count >= 0", name="ck_doc_processing_attempt_count"),
    )


class PdfVisualIndex(Base):
    """Versioned private visual index for one PDF document."""

    __tablename__ = "pdf_visual_indexes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("space_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), default="staging", server_default="staging", nullable=False
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    outline_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    toc_pdf_page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    toc_pdf_page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    outline_entries: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    outline_markdown_path: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    derived_bytes: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", nullable=False
    )
    renderer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    document: Mapped["SpaceDocument"] = relationship(back_populates="visual_indexes")
    space: Mapped["Space"] = relationship()
    assets: Mapped[list["PdfPageAsset"]] = relationship(
        back_populates="visual_index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    agent_calls: Mapped[list["PdfIndexAgentCall"]] = relationship(
        back_populates="visual_index",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="pdf_visual_index", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint(
            "document_id", "generation", name="uq_pdf_visual_indexes_document_generation"
        ),
        Index("ix_pdf_visual_indexes_space", "space_id"),
        Index("ix_pdf_visual_indexes_state", "state"),
        Index(
            "uq_pdf_visual_indexes_current_document",
            "document_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current = 1"),
        ),
        CheckConstraint("generation >= 1", name="ck_pdf_visual_indexes_generation"),
        CheckConstraint("page_count >= 1", name="ck_pdf_visual_indexes_page_count"),
        CheckConstraint("derived_bytes >= 0", name="ck_pdf_visual_indexes_derived_bytes"),
        CheckConstraint(
            "state IN ('staging', 'published', 'superseded', 'failed')",
            name="ck_pdf_visual_indexes_state",
        ),
        CheckConstraint(
            "outline_status IN ('pending', 'ready', 'not_found', 'failed')",
            name="ck_pdf_visual_indexes_outline_status",
        ),
        CheckConstraint(
            "toc_pdf_page_start IS NULL OR toc_pdf_page_start >= 1",
            name="ck_pdf_visual_indexes_toc_start",
        ),
        CheckConstraint(
            "toc_pdf_page_end IS NULL OR toc_pdf_page_end >= toc_pdf_page_start",
            name="ck_pdf_visual_indexes_toc_end",
        ),
    )


class PdfPageAsset(Base):
    """One immutable 1-up, 2-up, or 4-up rendered PDF page asset."""

    __tablename__ = "pdf_page_assets"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    index_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pdf_visual_indexes.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("space_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False
    )
    pages_per_image: Mapped[int] = mapped_column(Integer, nullable=False)
    physical_page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    physical_page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    visual_index: Mapped["PdfVisualIndex"] = relationship(back_populates="assets")

    __table_args__ = (
        UniqueConstraint(
            "index_id",
            "pages_per_image",
            "physical_page_start",
            name="uq_pdf_page_assets_index_lod_start",
        ),
        Index("ix_pdf_page_assets_document", "document_id"),
        Index("ix_pdf_page_assets_space", "space_id"),
        CheckConstraint(
            "pages_per_image IN (1, 2, 4)", name="ck_pdf_page_assets_pages_per_image"
        ),
        CheckConstraint("physical_page_start >= 1", name="ck_pdf_page_assets_page_start"),
        CheckConstraint(
            "physical_page_end >= physical_page_start",
            name="ck_pdf_page_assets_page_end",
        ),
        CheckConstraint("width > 0", name="ck_pdf_page_assets_width"),
        CheckConstraint("height > 0", name="ck_pdf_page_assets_height"),
        CheckConstraint("byte_size > 0", name="ck_pdf_page_assets_byte_size"),
    )


class PdfIndexAgentCall(Base):
    """Durable checkpoint for an idempotent PDF VLM-agent call."""

    __tablename__ = "pdf_index_agent_calls"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    index_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pdf_visual_indexes.id", ondelete="CASCADE"),
        nullable=False,
    )
    call_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    response_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    visual_index: Mapped["PdfVisualIndex"] = relationship(back_populates="agent_calls")

    __table_args__ = (
        Index("ix_pdf_index_agent_calls_index", "index_id"),
        CheckConstraint("round_index >= 0", name="ck_pdf_index_agent_calls_round"),
    )


class DocumentChunk(Base):
    """文档切片向量存储表"""

    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("space_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    pdf_visual_index_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pdf_visual_indexes.id", ondelete="CASCADE"),
        nullable=True,
    )
    chunk_kind: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    physical_page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    physical_page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_tsv = mapped_column(TSVECTOR, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    document: Mapped["SpaceDocument"] = relationship(back_populates="chunks")
    space: Mapped["Space"] = relationship()
    pdf_visual_index: Mapped[Optional["PdfVisualIndex"]] = relationship(
        back_populates="chunks"
    )

    # 索引（embedding 索引将在迁移中单独创建）
    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_space_id", "space_id"),
        Index("ix_document_chunks_pdf_visual_index_id", "pdf_visual_index_id"),
        Index(
            "ix_document_chunks_kind_page", "chunk_kind", "physical_page_start"
        ),
        CheckConstraint(
            "chunk_kind IS NULL OR chunk_kind IN ('native_page', 'outline_entry')",
            name="ck_document_chunks_chunk_kind",
        ),
        CheckConstraint(
            "physical_page_start IS NULL OR physical_page_start >= 1",
            name="ck_document_chunks_page_start",
        ),
        CheckConstraint(
            "physical_page_end IS NULL OR physical_page_end >= physical_page_start",
            name="ck_document_chunks_page_end",
        ),
    )


class DocumentText(Base):
    """文档全文存储表（每文档一行，去向量化 RAG）"""

    __tablename__ = "document_texts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("space_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_tsv: Mapped[Optional[Any]] = mapped_column(TSVECTOR, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    document: Mapped["SpaceDocument"] = relationship()
    space: Mapped["Space"] = relationship()
    images: Mapped[list["DocumentImage"]] = relationship(
        back_populates="document_text", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_document_texts_space_id", "space_id"),
    )


class DocumentImage(Base):
    """文档嵌入图片存储表（用于知识库图片召回）"""

    __tablename__ = "document_images"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("space_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_text_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_texts.id", ondelete="CASCADE"),
        nullable=True,
    )
    page_num: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    vlm_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    document: Mapped["SpaceDocument"] = relationship()
    document_text: Mapped[Optional["DocumentText"]] = relationship(
        back_populates="images"
    )

    __table_args__ = (
        Index("ix_document_images_document_id", "document_id"),
        Index("ix_document_images_space_id", "space_id"),
        Index("ix_document_images_document_text_id", "document_text_id"),
    )


class LongTermMemory(Base):
    """用户长期记忆表"""

    __tablename__ = "long_term_memories"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 每用户一条记录
    )
    # JSONB 数组存储条目：[{"id": 1, "content": "...", "created_at": "..."}]
    entries: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # 自增序号计数器
    next_entry_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship()

    # 索引
    __table_args__ = (
        Index("ix_long_term_memories_user_id", "user_id"),
    )


class SpaceMemory(Base):
    """学习空间记忆表"""

    __tablename__ = "space_memories"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 每空间一条记录
    )
    # JSONB 数组存储条目：[{"id": 1, "content": "...", "created_at": "..."}]
    entries: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # 自增序号计数器
    next_entry_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship()

    # 索引
    __table_args__ = (
        Index("ix_space_memories_space_id", "space_id"),
    )


class VectorMemory(Base):
    """向量记忆表 - 基于 pgvector 的语义记忆存储"""

    __tablename__ = "vector_memories"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=True,  # NULL 表示长期记忆（跨空间）
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(
            MemoryType,
            name="memorytype",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],  # 使用 value 而非 name
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # pgvector 向量列，1024 维度（与 DashScope text-embedding-v3 配置一致）
    embedding: Mapped[list] = mapped_column(
        Vector(1024) if Vector else Text,  # fallback for dev without pgvector
        nullable=False,
    )
    # 可选元数据（来源、置信度等）- 注意：不能用 metadata，是 SQLAlchemy 保留字
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship()
    space: Mapped[Optional["Space"]] = relationship()

    # 索引（向量索引将在迁移中单独创建）
    __table_args__ = (
        Index("ix_vector_memories_user_id", "user_id"),
        Index("ix_vector_memories_space_id", "space_id"),
        Index("ix_vector_memories_user_type", "user_id", "memory_type"),
    )


# ============ 激活码相关表 ============


class ActivationCode(Base):
    """激活码表"""

    __tablename__ = "activation_codes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    used_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_tier: Mapped["SubscriptionTier"] = mapped_column(
        Enum(SubscriptionTier), nullable=False, server_default="ALPHA",
        comment="目标订阅等级"
    )
    validity_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    user: Mapped[Optional["User"]] = relationship()

    # 索引
    __table_args__ = (
        Index("ix_activation_codes_code", "code", unique=True),
        Index("ix_activation_codes_used_by", "used_by"),
    )


class InviteCode(Base):
    """用户个人邀请码"""

    __tablename__ = "invite_codes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    uses_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship(foreign_keys=[owner_user_id])

    __table_args__ = (
        Index("ix_invite_codes_owner_user_id", "owner_user_id", unique=True),
        Index("ix_invite_codes_code", "code", unique=True),
        Index("ix_invite_codes_status", "status"),
    )


class InviteRedemption(Base):
    """邀请注册绑定和奖励流水"""

    __tablename__ = "invite_redemptions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    invite_code_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invite_codes.id", ondelete="CASCADE"),
        nullable=False,
    )
    inviter_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    invitee_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    inviter_reward_transaction_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    invitee_reward_transaction_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    invite_code: Mapped["InviteCode"] = relationship()
    inviter: Mapped["User"] = relationship(foreign_keys=[inviter_user_id])
    invitee: Mapped["User"] = relationship(foreign_keys=[invitee_user_id])
    inviter_reward_transaction: Mapped[Optional["WalletTransaction"]] = relationship(
        foreign_keys=[inviter_reward_transaction_id]
    )
    invitee_reward_transaction: Mapped[Optional["WalletTransaction"]] = relationship(
        foreign_keys=[invitee_reward_transaction_id]
    )

    __table_args__ = (
        CheckConstraint(
            "inviter_user_id <> invitee_user_id",
            name="ck_invite_redemptions_not_self",
        ),
        Index("ix_invite_redemptions_inviter_created", "inviter_user_id", "created_at"),
        Index("ix_invite_redemptions_invitee", "invitee_user_id", unique=True),
        Index("ix_invite_redemptions_code", "invite_code_id"),
    )


class PendingClientToolRequest(Base):
    """客户端工具请求表 — 跨 worker 共享待处理的客户端工具请求"""

    __tablename__ = "pending_client_tool_requests"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_call_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending / completed / timeout
    result_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 关系
    conversation: Mapped["Conversation"] = relationship()

    # 索引
    __table_args__ = (
        Index("ix_pending_client_tool_requests_conv_id", "conversation_id"),
        Index("ix_pending_client_tool_requests_tool_call_id", "tool_call_id", unique=True),
        Index("ix_pending_client_tool_requests_status", "status"),
    )


# ============ 学习评估相关表 ============


class DailyStudyRecord(Base):
    """每日学习活跃记录表"""

    __tablename__ = "daily_study_records"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    study_date: Mapped[date] = mapped_column(Date, nullable=False)
    activity_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship()

    # 索引和约束
    __table_args__ = (
        UniqueConstraint("user_id", "study_date", name="uq_dsr_user_study_date"),
        Index("ix_dsr_user_date", "user_id", "study_date"),
    )


class StudyActivityLog(Base):
    """学习活动记录表 — 由 MemoryExtractor 每轮对话自动提取"""

    __tablename__ = "study_activity_logs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    space_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Agent 生成内容
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    activity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "学习新知识" / "复习" / "解题" / "探讨" / "测验"
    subject_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )  # Space 名称或 Quick Chat 推断主题

    # 知识图谱关联 — 存节点 label（不存 UUID，因为节点可能重建）
    related_node_labels: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # 元数据
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    study_depth: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # "浅层浏览" / "中等理解" / "深入掌握"

    # 来源标记
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="conversation"
    )  # "conversation" / "quiz"

    # 时间
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    activity_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # 关系
    user: Mapped["User"] = relationship()
    conversation: Mapped[Optional["Conversation"]] = relationship()
    space: Mapped[Optional["Space"]] = relationship()

    # 索引
    __table_args__ = (
        Index("idx_activity_user_date", "user_id", "activity_date"),
        Index("idx_activity_conversation", "conversation_id"),
    )


class LearningPathEvent(Base):
    """学习路径自动扩展事件记录"""

    __tablename__ = "learning_path_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 扩展的新节点（不含衔接节点）
    new_node_names: Mapped[list] = mapped_column(JSONB, nullable=False)

    # 触发时的统计信息（调试用）
    trigger_info: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship()
    user: Mapped["User"] = relationship()

    # 索引
    __table_args__ = (
        Index("ix_learning_path_events_space_id", "space_id"),
        Index("ix_learning_path_events_user_id", "user_id"),
    )


class PaymentOrder(Base):
    """支付订单表"""

    __tablename__ = "payment_orders"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    out_trade_no: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="商户订单号"
    )
    product_type: Mapped[str] = mapped_column(
        String(32),
        default="subscription",
        server_default="subscription",
        nullable=False,
        comment="订单产品类型：subscription / credit_pack",
    )
    product_code: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="产品编码，如 BASIC_monthly / credit_10"
    )
    target_tier: Mapped[Optional[SubscriptionTier]] = mapped_column(
        Enum(SubscriptionTier), nullable=True, comment="目标订阅等级"
    )
    billing_cycle: Mapped[Optional[BillingCycle]] = mapped_column(
        Enum(
            BillingCycle,
            name="billingcycle",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
        comment="计费周期",
    )
    amount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="金额（分）"
    )
    subscription_days: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False, comment="订阅天数"
    )
    credit_amount_cents: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="充值到账金额（分）",
    )
    wallet_grant_cents: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="订阅赠送余额（分）",
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            name="orderstatus",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=OrderStatus.PENDING,
        nullable=False,
    )
    alipay_trade_no: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="支付宝交易号"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="订单过期时间（30分钟）"
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship()

    # 索引
    __table_args__ = (
        Index("ix_payment_orders_user_id", "user_id"),
        Index("ix_payment_orders_out_trade_no", "out_trade_no", unique=True),
        Index("ix_payment_orders_status", "status"),
        Index("ix_payment_orders_product_type", "product_type"),
        Index("ix_payment_orders_expires_at", "expires_at"),
    )


class PaymentQrCode(Base):
    """收款码图片管理"""

    __tablename__ = "payment_qr_codes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    product_type: Mapped[str] = mapped_column(
        String(32),
        default="subscription",
        server_default="subscription",
        nullable=False,
        comment="二维码产品类型：subscription / credit_pack",
    )
    product_code: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="产品编码"
    )
    tier: Mapped[Optional[SubscriptionTier]] = mapped_column(
        Enum(SubscriptionTier), nullable=True
    )
    billing_cycle: Mapped[Optional[BillingCycle]] = mapped_column(
        Enum(
            BillingCycle,
            name="billingcycle",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    pay_method: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="alipay / wechat"
    )
    display_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="展示用二维码文件名"
    )
    save_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="保存到相册用文件名"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "product_type",
            "tier",
            "billing_cycle",
            "pay_method",
            name="uq_payment_qr_subscription_combo",
        ),
        UniqueConstraint(
            "product_type",
            "product_code",
            "pay_method",
            name="uq_payment_qr_product_combo",
        ),
    )


class PaymentNotifyLog(Base):
    """支付宝异步通知处理日志"""

    __tablename__ = "payment_notify_logs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    out_trade_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trade_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trade_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    app_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    seller_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    total_amount: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    raw_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    verify_success: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    process_success: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    process_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_payment_notify_logs_out_trade_no", "out_trade_no"),
        Index("ix_payment_notify_logs_trade_no", "trade_no"),
        Index("ix_payment_notify_logs_received_at", "received_at"),
        Index("ix_payment_notify_logs_provider_created", "provider", "created_at"),
    )


class WalletAccount(Base):
    """用户钱包账户"""

    __tablename__ = "wallet_accounts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    balance_cents: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False, comment="当前余额（分）"
    )
    debt_limit_cents: Mapped[int] = mapped_column(
        Integer,
        default=500,
        server_default="500",
        nullable=False,
        comment="允许欠费额度（正数，分）",
    )
    total_recharged_cents: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    total_granted_cents: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    total_spent_cents: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_wallet_accounts_user_id", "user_id", unique=True),
    )


class WalletTransaction(Base):
    """用户钱包流水"""

    __tablename__ = "wallet_transactions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallet_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_type: Mapped[WalletTransactionType] = mapped_column(
        Enum(WalletTransactionType, name="wallettransactiontype"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="流水金额（分），正数入账，负数扣费"
    )
    balance_after_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()
    account: Mapped["WalletAccount"] = relationship()

    __table_args__ = (
        Index("ix_wallet_transactions_user_created", "user_id", "created_at"),
        Index("ix_wallet_transactions_type", "transaction_type"),
        Index(
            "ix_wallet_transactions_idempotency_key",
            "idempotency_key",
            unique=True,
        ),
    )


class ReviewSchedule(Base):
    """艾宾浩斯遗忘曲线复习计划"""

    __tablename__ = "review_schedules"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_activity_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    review_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending / completed / skipped
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_by_activity_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study_activity_logs.id", ondelete="SET NULL"),
        nullable=True,
    )
    study_depth: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # SM-2 算法字段
    ease_factor: Mapped[float] = mapped_column(
        Float, default=2.5, server_default="2.5", nullable=False,
        comment="SM-2 易度因子 (>= 1.3)",
    )
    interval_days: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False,
        comment="当前计算的复习间隔天数",
    )
    quality_score: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="SM-2 质量评分 (0-5)",
    )
    review_quiz_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联的复习测试题",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship()
    activity: Mapped["StudyActivityLog"] = relationship(
        foreign_keys=[activity_id]
    )

    # 索引
    __table_args__ = (
        Index("idx_review_user_date", "user_id", "scheduled_date"),
        Index("idx_review_user_node", "user_id", "node_label"),
        Index("idx_review_activity", "activity_id"),
        Index("idx_review_status_date", "user_id", "status", "scheduled_date"),
    )


class ReviewEmailLog(Base):
    """复习邮件发送日志"""

    __tablename__ = "review_email_log"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    email_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="邮件类型: daily_review / inactivity_care",
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False,
    )
    spaces_included: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
        comment="包含的空间 ID/名称列表",
    )
    quiz_ids: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True,
        comment="关联的测试题 ID 列表",
    )

    # 关系
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_review_email_user_type_date", "user_id", "email_type", "sent_at"),
    )


class Notification(Base):
    """应用内通知"""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType), nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="灵活载荷: quiz_id, space_id, space_name, action 等",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # 关系
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_notif_user_read_created", "user_id", "is_read", "created_at"),
        Index("idx_notif_user_created", "user_id", "created_at"),
    )


class UserSearchSettings(Base):
    """用户搜索渠道设置"""

    __tablename__ = "user_search_settings"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    web_search_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    academic_search_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    encyclopedia_search_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    course_search_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index("idx_search_settings_user", "user_id", unique=True),
    )


class Note(Base):
    """笔记卡片表"""

    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    folder_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note_type: Mapped[str] = mapped_column(String(50), default="text", nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    creator_user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship(back_populates="notes")
    node: Mapped[Optional["Node"]] = relationship()
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[creator_user_id])
    attachments: Mapped[list["NoteAttachment"]] = relationship(
        back_populates="note", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_notes_space_id", "space_id"),
        Index("ix_notes_node_id", "node_id"),
        Index("ix_notes_folder_id", "folder_id"),
    )


class NoteAttachment(Base):
    """笔记附件表"""

    __tablename__ = "note_attachments"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    note_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    attachment_type: Mapped[NoteAttachmentType] = mapped_column(
        Enum(NoteAttachmentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    link_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    link_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    note: Mapped["Note"] = relationship(back_populates="attachments")

    __table_args__ = (
        Index("ix_note_attachments_note_id", "note_id"),
    )


class CalendarEvent(Base):
    """用户日历事件"""
    __tablename__ = "calendar_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_conversation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_calendar_events_user_id", "user_id"),
        Index("ix_calendar_events_user_start", "user_id", "start_time"),
    )


class SpaceShareCode(Base):
    """学习空间分享码"""

    __tablename__ = "space_share_codes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    creator_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    share_mode: Mapped[ShareMode] = mapped_column(
        Enum(
            ShareMode,
            name="sharemode",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ShareMode.CLONE,
        server_default="clone",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship()
    creator: Mapped["User"] = relationship()

    # one code per (space, mode)
    __table_args__ = (
        UniqueConstraint("space_id", "share_mode", name="uq_share_code_space_mode"),
    )


class SpaceMember(Base):
    """协作学习空间成员表"""

    __tablename__ = "space_members"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[SpaceMemberRole] = mapped_column(
        Enum(
            SpaceMemberRole,
            name="spacememberrole",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    color: Mapped[str] = mapped_column(
        String(7), default="#0088FF", server_default="#0088FF", nullable=False
    )
    can_edit_graph: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False,
        comment="是否允许修改知识图谱结构"
    )

    # 关系
    space: Mapped["Space"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("space_id", "user_id", name="uq_space_member"),
        Index("ix_space_members_space_id", "space_id"),
        Index("ix_space_members_user_id", "user_id"),
    )


class NodeUserMastery(Base):
    """节点用户掌握度表（协作空间中每人独立）"""

    __tablename__ = "node_user_mastery"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    node_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    mastery: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    node: Mapped["Node"] = relationship()
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("node_id", "user_id", name="uq_node_user_mastery"),
        Index("ix_node_user_mastery_node_id", "node_id"),
        Index("ix_node_user_mastery_user_id", "user_id"),
        CheckConstraint(
            "mastery >= 0 AND mastery <= 100",
            name="ck_node_user_mastery_range",
        ),
    )


class NodeMasteryEvent(Base):
    """协作空间中每次真实掌握度变化的审计事件。"""

    __tablename__ = "node_mastery_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    space_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_mastery: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    new_mastery: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "previous_mastery IS NULL OR (previous_mastery >= 0 AND previous_mastery <= 100)",
            name="ck_mastery_events_previous_range",
        ),
        CheckConstraint(
            "new_mastery >= 0 AND new_mastery <= 100",
            name="ck_mastery_events_new_range",
        ),
        CheckConstraint(
            "source IN ('baseline', 'chat_tool', 'quiz_evaluation')",
            name="ck_mastery_events_source",
        ),
        Index("ix_mastery_events_space_time", "space_id", "created_at"),
        Index("ix_mastery_events_user_time", "user_id", "created_at"),
        Index(
            "ix_mastery_events_user_node_time",
            "user_id",
            "node_id",
            "created_at",
        ),
    )


# ============ MCP 服务配置 ============


class UserMcpService(Base):
    """用户自定义 MCP 服务配置"""

    __tablename__ = "user_mcp_services"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tools_cache: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "url", name="uq_user_mcp_service_url"),
        Index("ix_user_mcp_services_user_id", "user_id"),
    )
