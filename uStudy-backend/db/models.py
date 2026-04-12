"""数据库表模型"""

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import ENUM, JSON, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # 如果 pgvector 未安装，使用占位符
    Vector = None

from db.database import Base

if TYPE_CHECKING:
    pass


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


class QuickChatToolTaskStatus(str, enum.Enum):
    """快速对话工具任务状态"""

    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class QuickChatToolTaskStage(str, enum.Enum):
    """快速对话创建学习空间任务阶段"""

    QUEUED = "queued"
    SPACE_CREATED = "space_created"
    KG_RUNNING = "kg_running"
    KG_DONE = "kg_done"
    BINDING = "binding"
    BINDING_DONE = "binding_done"
    KG_FAILED = "kg_failed"
    BINDING_FAILED = "binding_failed"
    TIMEOUT = "timeout"
    CLEANUP_DONE = "cleanup_done"
    CLEANUP_FAILED = "cleanup_failed"


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


class NoteAttachmentType(str, enum.Enum):
    """笔记附件类型"""

    IMAGE = "image"
    FILE = "file"
    LINK = "link"


# ============ 表模型 ============


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
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

    # 索引
    __table_args__ = (Index("ix_spaces_user_id", "user_id"),)


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
    space_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
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
    space: Mapped[Optional["Space"]] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("ix_conversations_user_created", "user_id", "created_at"),
        Index("ix_conversations_space_id", "space_id"),
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
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship(back_populates="edges")
    from_node: Mapped["Node"] = relationship(foreign_keys=[from_node_id])
    to_node: Mapped["Node"] = relationship(foreign_keys=[to_node_id])

    # 索引和约束
    __table_args__ = (
        Index("ix_edges_space_id", "space_id"),
        Index("ix_edges_from_node", "from_node_id"),
        Index("ix_edges_to_node", "to_node_id"),
        UniqueConstraint(
            "space_id", "from_node_id", "to_node_id", "type", name="uq_edges_unique"
        ),
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
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel, values_callable=lambda x: [e.value for e in x]),
        default=DifficultyLevel.MEDIUM,
        nullable=False,
    )
    total_questions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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

    # 异步评估状态: pending -> evaluating -> completed / failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="completed"
    )

    # 原始用户答案（异步模式下存储，供后台任务使用）
    user_answers_raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship(back_populates="documents")
    processing_task: Mapped[Optional["DocumentProcessingTask"]] = relationship(
        back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("ix_space_documents_space_id", "space_id"),
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
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
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

    # 关系
    document: Mapped["SpaceDocument"] = relationship(back_populates="processing_task")

    # 索引
    __table_args__ = (
        Index("ix_doc_processing_document_id", "document_id"),
        Index("ix_doc_processing_status", "status"),
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
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(2000), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # 关系
    document: Mapped["SpaceDocument"] = relationship(back_populates="chunks")
    space: Mapped["Space"] = relationship()

    # 索引（embedding 索引将在迁移中单独创建）
    __table_args__ = (
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_space_id", "space_id"),
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
    # pgvector 向量列，2000 维度（与现有 embedding 配置一致）
    embedding: Mapped[list] = mapped_column(
        Vector(2000) if Vector else Text,  # fallback for dev without pgvector
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


class QuickChatToolTask(Base):
    """快速对话工具异步任务表（主要用于 create_learning_space）"""

    __tablename__ = "quick_chat_tool_tasks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_call_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tool_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[QuickChatToolTaskStatus] = mapped_column(
        Enum(
            QuickChatToolTaskStatus,
            name="quickchattooltaskstatus",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=QuickChatToolTaskStatus.RUNNING,
        nullable=False,
    )
    stage: Mapped[QuickChatToolTaskStage] = mapped_column(
        Enum(
            QuickChatToolTaskStage,
            name="quickchattooltaskstage",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=QuickChatToolTaskStage.QUEUED,
        nullable=False,
    )
    space_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    kg_task_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_message_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship()
    conversation: Mapped["Conversation"] = relationship()
    space: Mapped[Optional["Space"]] = relationship()
    kg_task: Mapped[Optional["AgentTask"]] = relationship()
    source_message: Mapped[Optional["Message"]] = relationship()

    __table_args__ = (
        Index(
            "ix_quick_chat_tool_tasks_conversation_status",
            "conversation_id",
            "status",
        ),
        Index("ix_quick_chat_tool_tasks_tool_call_id", "tool_call_id", unique=True),
        Index("ix_quick_chat_tool_tasks_user_status", "user_id", "status"),
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
    target_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier), nullable=False, comment="目标订阅等级"
    )
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        Enum(
            BillingCycle,
            name="billingcycle",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        comment="计费周期",
    )
    amount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="金额（分）"
    )
    subscription_days: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="订阅天数"
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
        Index("ix_payment_orders_expires_at", "expires_at"),
    )


class PaymentQrCode(Base):
    """收款码图片管理"""

    __tablename__ = "payment_qr_codes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier), nullable=False
    )
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        Enum(
            BillingCycle,
            name="billingcycle",
            create_type=False,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
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
            "tier", "billing_cycle", "pay_method", name="uq_payment_qr_combo"
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
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note_type: Mapped[str] = mapped_column(String(50), default="text", nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    space: Mapped["Space"] = relationship(back_populates="notes")
    node: Mapped[Optional["Node"]] = relationship()
    attachments: Mapped[list["NoteAttachment"]] = relationship(
        back_populates="note", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_notes_space_id", "space_id"),
        Index("ix_notes_node_id", "node_id"),
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
