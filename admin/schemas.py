"""Admin module Pydantic schemas"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

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


# ---- Users ----


class AdminUserItem(BaseModel):
    id: UUID
    email: str
    nickname: str
    avatar_url: str | None = None
    subscription_tier: SubscriptionTier
    subscription_expires_at: datetime | None = None
    created_at: datetime


class AdminUserDetail(AdminUserItem):
    spaces_count: int
    conversations_count: int
    recent_orders: list["AdminOrderItem"]


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
    target_tier: SubscriptionTier
    billing_cycle: BillingCycle
    amount_cents: int
    status: OrderStatus
    paid_at: datetime | None = None
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
