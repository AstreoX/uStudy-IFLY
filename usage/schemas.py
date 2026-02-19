"""Pydantic schemas for usage API."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from usage.models import UsageType


class HeartbeatRequest(BaseModel):
    """心跳上报请求"""

    seconds: int = Field(ge=1, le=120)


class UsageSummaryResponse(BaseModel):
    """用量摘要响应"""

    period_start: datetime
    period_end: datetime

    total_tokens: int
    total_chat_tokens: int
    total_embedding_tokens: int

    chat_calls: int
    embedding_calls: int

    estimated_cost_cents: int

    # 与上一周期对比
    tokens_change_percent: float | None = None

    # 配额信息 (如果有)
    quota_limit: int | None = None
    quota_used_percent: float | None = None


class UsageByType(BaseModel):
    """按类型的用量统计"""

    usage_type: UsageType
    total_tokens: int
    call_count: int
    estimated_cost_cents: int


class UsageBreakdownResponse(BaseModel):
    """用量分类统计响应"""

    period_start: datetime
    period_end: datetime
    breakdown: list[UsageByType]


class DailyUsage(BaseModel):
    """每日用量"""

    date: date
    total_tokens: int
    call_count: int
    estimated_cost_cents: int


class UsageHistoryResponse(BaseModel):
    """用量历史响应"""

    start_date: date
    end_date: date
    daily_usage: list[DailyUsage]
    total_tokens: int
    total_calls: int
    total_cost_cents: int
