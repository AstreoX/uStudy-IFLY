"""Quiz 模块 Pydantic Schemas"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============ 调试信息 Schema ============


class DebugStepResponse(BaseModel):
    """评估步骤调试信息"""

    step_number: int = Field(..., description="步骤序号")
    step_name: str = Field(..., description="步骤名称")
    status: Literal["success", "failed", "skipped"] = Field(..., description="状态")
    duration_ms: int = Field(..., description="耗时（毫秒）")
    details: list[str] = Field(default_factory=list, description="详细信息")
    metadata: dict[str, Any] | None = Field(None, description="元数据")


class DebugInfoResponse(BaseModel):
    """评估调试信息"""

    steps: list[DebugStepResponse] = Field(
        default_factory=list, description="评估步骤列表"
    )
    model_name: str = Field(default="", description="使用的模型名称")
    total_duration_ms: int = Field(default=0, description="总耗时（毫秒）")


# ============ 请求 Schema ============


class UserAnswerItem(BaseModel):
    """用户单题答案"""

    question_id: UUID = Field(..., description="题目 ID")
    answer: Any = Field(..., description="用户答案，格式同 correct_answer")


class QuizSubmitRequest(BaseModel):
    """答卷提交请求"""

    answers: list[UserAnswerItem] = Field(..., description="用户答案列表")


# ============ 响应 Schema ============


class QuestionResponse(BaseModel):
    """题目响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="题目 ID")
    question_type: str = Field(..., description="题目类型")
    question_stem: str = Field(..., description="题干")
    options: list[str] | None = Field(None, description="选项列表")
    correct_answer: dict[str, Any] = Field(..., description="正确答案")
    order_index: int = Field(..., description="题目顺序")


class QuizDetailResponse(BaseModel):
    """测试详情响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="测试 ID")
    space_id: UUID = Field(..., description="学习空间 ID")
    title: str = Field(..., description="测试标题")
    topic: str = Field(..., description="测试主题")
    difficulty: str = Field(..., description="难度级别")
    total_questions: int = Field(..., description="题目总数")
    questions: list[QuestionResponse] = Field(..., description="题目列表")
    created_at: datetime = Field(..., description="创建时间")


class QuestionResultResponse(BaseModel):
    """逐题评估结果"""

    id: UUID = Field(..., description="题目 ID")
    order: int = Field(..., description="题目序号（从1开始）")
    question_type: str = Field(..., description="题型")
    title: str = Field(..., description="题干")
    options: list[str] | None = Field(None, description="选项列表（选择题）")
    status: Literal["correct", "wrong", "partial"] = Field(
        ..., description="判定结果"
    )
    score: int = Field(..., description="得分")
    max_score: int = Field(..., description="满分")
    user_answer: Any = Field(None, description="用户答案")
    correct_answer: Any = Field(..., description="正确答案")
    ai_evaluation: str | None = Field(None, description="简答题 AI 评语")


class QuizEvaluationResponse(BaseModel):
    """整卷评估响应"""

    quiz_id: UUID = Field(..., description="测试 ID")
    score: int = Field(..., description="实际得分")
    total_score: int = Field(..., description="总分")
    strengths: list[str] = Field(..., description="优点分析")
    weaknesses: list[str] = Field(..., description="缺点分析")
    suggestions: list[str] = Field(..., description="提升建议")
    question_results: list[QuestionResultResponse] = Field(
        ..., description="逐题评估结果"
    )
    debug_info: DebugInfoResponse | None = Field(
        None, description="AI评估调试信息（仅新提交有）"
    )


class QuizSubmitAsyncResponse(BaseModel):
    """异步提交响应"""

    quiz_id: UUID = Field(..., description="测试 ID")
    attempt_id: UUID = Field(..., description="作答记录 ID")
    status: str = Field(..., description="状态: pending")
    message: str = Field(..., description="提示信息")


class QuizListItemResponse(BaseModel):
    """测验列表项响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="测试 ID")
    title: str = Field(..., description="测试标题")
    topic: str = Field(..., description="测试主题")
    difficulty: str = Field(..., description="难度级别")
    total_questions: int = Field(..., description="题目总数")
    created_at: datetime = Field(..., description="创建时间")
    has_attempt: bool = Field(..., description="是否已作答")
    attempt_score: int | None = Field(None, description="得分（已作答时）")
    attempt_total_score: int | None = Field(None, description="总分（已作答时）")
    attempt_status: str | None = Field(None, description="评估状态（pending/evaluating/completed/failed）")


class QuizAttemptResponse(BaseModel):
    """测验作答记录响应"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="作答记录 ID")
    quiz_id: UUID = Field(..., description="测试 ID")
    score: int = Field(..., description="实际得分")
    total_score: int = Field(..., description="总分")
    strengths: list[str] = Field(..., description="优点分析")
    weaknesses: list[str] = Field(..., description="缺点分析")
    suggestions: list[str] = Field(..., description="提升建议")
    question_results: list[QuestionResultResponse] = Field(
        ..., description="逐题评估结果"
    )
    debug_info: DebugInfoResponse | None = Field(
        None, description="AI评估调试信息（可能为空）"
    )
    status: str = Field("completed", description="评估状态")
    submitted_at: datetime = Field(..., description="提交时间")
