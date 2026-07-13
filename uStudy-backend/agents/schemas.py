"""Agent 模块 Pydantic Schemas"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentTaskStatusEnum(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class DifficultyLevelEnum(str, Enum):
    """难度级别枚举"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionTypeEnum(str, Enum):
    """题目类型枚举"""

    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


# ============ 请求 Schemas ============


class KnowledgeGraphGenerateRequest(BaseModel):
    """知识图谱生成请求"""

    topic: str = Field(..., min_length=1, max_length=500, description="学习主题")
    user_preference: str | None = Field(
        None, max_length=1000, description="用户偏好（可选）"
    )


class TestStructItem(BaseModel):
    """测试结构项"""

    question_type: QuestionTypeEnum = Field(..., description="题目类型")
    question_num: int = Field(..., ge=1, le=20, description="题目数量")


class QuizGenerateRequest(BaseModel):
    """测试生成请求"""

    topic: str = Field(..., min_length=1, max_length=500, description="测试主题")
    difficulty_level: DifficultyLevelEnum = Field(
        DifficultyLevelEnum.MEDIUM, description="难度级别"
    )
    test_struct: list[TestStructItem] = Field(
        ..., min_length=1, max_length=10, description="题目结构配置"
    )


# ============ 响应 Schemas ============


class AgentTaskResponse(BaseModel):
    """任务创建响应"""

    model_config = ConfigDict(from_attributes=True)

    task_id: UUID = Field(..., description="任务 ID")
    status: AgentTaskStatusEnum = Field(..., description="任务状态")
    task_type: str = Field(..., description="任务类型")
    created_at: datetime = Field(..., description="创建时间")


class DebugLogEntry(BaseModel):
    """调试日志条目"""

    iteration: int = Field(..., description="迭代次数")
    timestamp: str = Field(..., description="时间戳")
    llm_content: str | None = Field(None, description="LLM 原始回复内容")
    tool_calls_count: int = Field(0, description="工具调用数量")
    progress: str = Field(..., description="进度 (已创建/期望总数)")


class AgentTaskResultResponse(BaseModel):
    """任务结果响应"""

    model_config = ConfigDict(from_attributes=True)

    task_id: UUID = Field(..., description="任务 ID")
    status: AgentTaskStatusEnum = Field(..., description="任务状态")
    task_type: str = Field(..., description="任务类型")
    space_id: UUID | None = Field(None, description="学习空间 ID")
    error_message: str | None = Field(None, description="错误信息")
    # 知识图谱任务结果
    node_count: int | None = Field(None, description="创建的节点数")
    edge_count: int | None = Field(None, description="创建的边数")
    # 测试生成任务结果
    quiz_id: UUID | None = Field(None, description="测试 ID")
    question_count: int | None = Field(None, description="创建的题目数")
    # Artifact 任务结果
    note_id: UUID | None = Field(None, description="交互演示笔记 ID")
    artifact_title: str | None = Field(None, description="交互演示标题")
    artifact_progress_status: str | None = Field(None, description="Artifact 生成进度状态")
    code_snapshot: str | None = Field(None, description="当前代码快照")
    html_size: int | None = Field(None, description="最终 HTML 大小（字节）")
    # 调试日志
    debug_logs: list[dict[str, Any]] | None = Field(None, description="调试日志（LLM 原始回复）")
    created_at: datetime = Field(..., description="创建时间")
    started_at: datetime | None = Field(None, description="开始时间")
    completed_at: datetime | None = Field(None, description="完成时间")
