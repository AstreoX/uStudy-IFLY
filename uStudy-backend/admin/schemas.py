"""Admin module Pydantic schemas"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from db.models import BillingCycle, OrderStatus, SubscriptionTier


# ---- Dashboard ----


class TierCount(BaseModel):
    tier: SubscriptionTier
    count: int


class AdminStats(BaseModel):
    total_users: int
    active_subscriptions: int
    new_users_7d: int
    pending_count: int
    revenue_30d_cents: int
    paid_order_count_30d: int
    users_by_tier: list[TierCount]


# ---- Analytics ----


class DailyCount(BaseModel):
    date: str
    count: int


class DailyRevenue(BaseModel):
    date: str
    amount_cents: int
    order_count: int


class ContentStats(BaseModel):
    total_spaces: int
    total_conversations: int
    total_messages: int
    total_quizzes: int


class StatusCount(BaseModel):
    status: str
    count: int


class ActivityTypeCount(BaseModel):
    activity_type: str
    count: int


class TierRevenue(BaseModel):
    tier: SubscriptionTier
    amount_cents: int
    order_count: int


class AdminAnalytics(BaseModel):
    user_growth_30d: list[DailyCount]
    revenue_trend_30d: list[DailyRevenue]
    dau_30d: list[DailyCount]
    content_stats: ContentStats
    orders_by_status: list[StatusCount]
    activity_by_type: list[ActivityTypeCount]
    revenue_by_tier: list[TierRevenue]


# ---- AI Operations ----


class AiOpsOverview(BaseModel):
    total_calls: int
    success_count: int
    failure_count: int
    failure_rate: float
    avg_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    avg_ttft_ms: int | None = None
    p95_ttft_ms: int | None = None
    retry_count: int


class AiOpsTrendPoint(BaseModel):
    bucket: str
    total_calls: int
    failure_count: int
    avg_latency_ms: int | None = None
    avg_ttft_ms: int | None = None


class AiOpsBreakdownItem(BaseModel):
    key: str
    total_calls: int
    failure_count: int
    failure_rate: float
    avg_latency_ms: int | None = None
    avg_ttft_ms: int | None = None


class AiOpsRecentFailure(BaseModel):
    id: UUID
    created_at: datetime
    model: str
    request_kind: str
    source_module: str | None = None
    source_operation: str | None = None
    user_email: str | None = None
    http_status_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    ttft_ms: int | None = None


class AiOpsDashboard(BaseModel):
    hours: int
    since: datetime
    overview: AiOpsOverview
    trend: list[AiOpsTrendPoint]
    by_model: list[AiOpsBreakdownItem]
    by_source: list[AiOpsBreakdownItem]
    recent_failures: list[AiOpsRecentFailure]


# ---- Users ----


class AdminUserItem(BaseModel):
    id: UUID
    email: str
    nickname: str
    avatar_url: str | None = None
    subscription_tier: SubscriptionTier
    subscription_expires_at: datetime | None = None
    created_at: datetime


class AdminInviterInfo(BaseModel):
    user_id: UUID
    email: str
    nickname: str
    code: str | None = None
    created_at: datetime


class AdminInviteeItem(BaseModel):
    redemption_id: UUID
    user_id: UUID
    email_masked: str
    nickname: str
    reward_cents: int
    created_at: datetime


class AdminUserDetail(AdminUserItem):
    spaces_count: int
    conversations_count: int
    recent_orders: list["AdminOrderItem"]
    wallet_balance_cents: int = 0
    wallet_available_cents: int = 0
    wallet_total_spent_cents: int = 0
    invite_code: str | None = None
    invite_url: str | None = None
    invited_by: AdminInviterInfo | None = None
    invite_total_count: int = 0
    invite_reward_cents: int = 0
    recent_invitees: list[AdminInviteeItem] = Field(default_factory=list)


class UpdateSubscriptionRequest(BaseModel):
    tier: SubscriptionTier
    expires_at: datetime | None = None


# ---- Orders ----


class AdminOrderItem(BaseModel):
    order_id: UUID
    out_trade_no: str
    user_id: UUID
    user_email: str
    user_nickname: str
    product_type: str = "subscription"
    product_code: str | None = None
    target_tier: SubscriptionTier | None = None
    billing_cycle: BillingCycle | None = None
    amount_cents: int
    credit_amount_cents: int = 0
    wallet_grant_cents: int = 0
    status: OrderStatus
    paid_at: datetime | None = None
    created_at: datetime


class AdminInviteRedemptionItem(BaseModel):
    id: UUID
    code: str
    inviter_user_id: UUID
    inviter_email: str
    inviter_nickname: str
    invitee_user_id: UUID
    invitee_email: str
    invitee_nickname: str
    reward_cents: int
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime


# ---- Paginated response ----


class PaginatedUsers(BaseModel):
    items: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class PaginatedOrders(BaseModel):
    items: list[AdminOrderItem]
    total: int
    page: int
    page_size: int


class PaginatedInviteRedemptions(BaseModel):
    items: list[AdminInviteRedemptionItem]
    total: int
    page: int
    page_size: int
