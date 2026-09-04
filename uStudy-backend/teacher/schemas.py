"""Response schemas for the teacher review dashboard."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PeriodResponse(BaseModel):
    days: int
    timezone: str = "Asia/Shanghai"
    start_date: date
    end_date: date
    previous_start_date: date
    previous_end_date: date
    generated_at: datetime


class ActivityMixItem(BaseModel):
    activity_type: str
    count: int


class DailyActivityPoint(BaseModel):
    date: date
    active_students: int
    active_rate: float | None
    activity_count: int
    activity_mix: list[ActivityMixItem] = Field(default_factory=list)


class OverviewResponse(BaseModel):
    period: PeriodResponse
    students_total: int
    active_students: int
    active_rate: float | None
    active_rate_previous: float | None
    assessed_pairs: int
    knowledge_coverage: float | None
    knowledge_coverage_previous: float | None
    avg_mastery: float | None
    avg_mastery_previous: float | None
    quiz_participants: int
    quiz_attempts: int
    quiz_accuracy: float | None
    quiz_accuracy_previous: float | None
    daily_activity: list[DailyActivityPoint]
    activity_calendar: list[DailyActivityPoint]
    activity_mix: list[ActivityMixItem]


class MasteryTrendPoint(BaseModel):
    date: date
    assessed_pairs: int
    coverage_rate: float | None
    avg_mastery: float | None


class KnowledgeNodeResponse(BaseModel):
    node_id: UUID
    label: str
    chapter: str
    assessed_students: int
    coverage_rate: float | None
    avg_mastery: float | None
    mastered_students: int
    mastered_rate: float | None


class KnowledgeResponse(BaseModel):
    period: PeriodResponse
    nodes: list[KnowledgeNodeResponse]
    weak_nodes: list[KnowledgeNodeResponse]
    trend: list[MasteryTrendPoint]


class StudentListItem(BaseModel):
    user_id: UUID
    nickname: str
    last_active_at: datetime | None
    active_days: int
    activity_count: int
    assessed_node_count: int
    coverage_rate: float | None
    avg_mastery: float | None
    mastered_node_count: int
    quiz_attempt_count: int
    quiz_accuracy: float | None


class StudentListResponse(BaseModel):
    period: PeriodResponse
    items: list[StudentListItem]
    page: int
    page_size: int
    total: int


class QuizSummaryResponse(BaseModel):
    quiz_id: UUID
    title: str
    submitted_at: datetime
    score_percent: float | None
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]


class LearningSummaryResponse(BaseModel):
    id: UUID
    activity_time: datetime
    activity_type: str
    title: str
    summary: str
    study_depth: str | None
    related_node_labels: list[str] = Field(default_factory=list)
    source: str


class StudentDetailResponse(BaseModel):
    period: PeriodResponse
    student: StudentListItem
    knowledge_nodes: list[KnowledgeNodeResponse]
    mastery_trend: list[MasteryTrendPoint]
    recent_quizzes: list[QuizSummaryResponse]
    learning_summaries: list[LearningSummaryResponse]
