"""Assessment Pydantic response models."""

from datetime import date

from pydantic import BaseModel


class CalendarDayRecord(BaseModel):
    date: date
    activity_count: int


class ContinuityScoreResponse(BaseModel):
    score: float
    cumulative_active_days: int
    effective_gap_days: int
    current_streak: int
    last_gap: int
    reset_threshold: int


class FocusScoreResponse(BaseModel):
    score: float
    week_start: str
    week_end: str
    total_sessions: int
    avg_session_depth: float
    avg_session_duration_min: float
    rhythm_score: float
    active_days: int


class DepthScoreResponse(BaseModel):
    score: float
    week_start: str
    week_end: str
    total_conversations: int
    avg_messages_per_conv: float
    avg_message_length: float
    mastery_score: float
    studied_node_count: int
    total_node_count: int


class ComprehensionScoreResponse(BaseModel):
    score: float
    quiz_accuracy: float
    mastery_ratio: float
    quiz_score_sum: int
    quiz_total_score_sum: int
    high_mastery_node_count: int
    total_node_count: int


class KnowledgeStructureScoreResponse(BaseModel):
    score: float
    solidity: float
    advanced_ratio: float
    qualifying_parent_count: int
    total_node_count: int
    advanced_edge_count: int


class ProfileStatsResponse(BaseModel):
    study_days: int
    total_study_hours: float
    avg_mastery: float
    node_coverage_percent: float


class ContinuityCalendarResponse(BaseModel):
    start_date: date
    end_date: date
    records: list[CalendarDayRecord]
