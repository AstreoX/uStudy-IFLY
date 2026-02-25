"""支付模块 Pydantic 模型"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from db.models import BillingCycle, OrderStatus, SubscriptionTier


class CreateOrderRequest(BaseModel):
    """创建订单请求"""

    tier: SubscriptionTier  # BASIC or PREMIUM
    billing_cycle: BillingCycle


class QrCodeUrls(BaseModel):
    """单个支付方式的收款码 URL"""

    display: str | None = None
    save: str | None = None


class QrCodesResponse(BaseModel):
    """所有支付方式的收款码"""

    alipay: QrCodeUrls = QrCodeUrls()
    wechat: QrCodeUrls = QrCodeUrls()


class CreateOrderResponse(BaseModel):
    """创建订单响应"""

    order_id: UUID
    out_trade_no: str
    amount_cents: int
    amount_display: str  # e.g. "¥12.90"
    expires_at: datetime
    qr_codes: QrCodesResponse = QrCodesResponse()


class AdminConfirmRequest(BaseModel):
    """管理员确认订单请求"""

    order_id: UUID


class OrderStatusResponse(BaseModel):
    """订单状态响应"""

    order_id: UUID
    out_trade_no: str
    status: OrderStatus
    target_tier: SubscriptionTier
    billing_cycle: BillingCycle
    amount_cents: int
    subscription_days: int
    paid_at: datetime | None = None
    created_at: datetime


class OrderListItem(BaseModel):
    """订单列表项"""

    order_id: UUID
    out_trade_no: str
    status: OrderStatus
    target_tier: SubscriptionTier
    billing_cycle: BillingCycle
    amount_cents: int
    created_at: datetime


class QrCodeAdminItem(BaseModel):
    """管理员查看收款码列表项"""

    id: UUID
    tier: SubscriptionTier
    billing_cycle: BillingCycle
    pay_method: str
    display_url: str | None = None
    save_url: str | None = None
    updated_at: datetime
