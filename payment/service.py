"""支付业务逻辑"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_scoped_session
from db.models import (
    BillingCycle,
    OrderStatus,
    PaymentOrder,
    SubscriptionTier,
    User,
)
from payment.alipay_client import create_alipay_page_url, verify_alipay_notification
from payment.exceptions import (
    AlipayError,
    InvalidPlanError,
    OrderExpiredError,
    OrderNotFoundError,
)
from payment.pricing import PRICING
from payment.schemas import (
    CreateOrderResponse,
    OrderListItem,
    OrderStatusResponse,
)

logger = logging.getLogger(__name__)

ORDER_EXPIRY_MINUTES = 30

# 定价方案名称映射
_TIER_NAMES = {
    SubscriptionTier.BASIC: "Plus",
    SubscriptionTier.PREMIUM: "Ultra",
}

_CYCLE_NAMES = {
    BillingCycle.MONTHLY: "月付",
    BillingCycle.SEMESTER: "学期包",
    BillingCycle.YEARLY: "年付",
}


def _generate_trade_no() -> str:
    """生成商户订单号: UST + 时间戳 + 随机 hex"""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:8]
    return f"UST{ts}{rand}"


def _cents_to_yuan(cents: int) -> str:
    """分 → 元字符串 (保留两位小数)"""
    return f"{cents / 100:.2f}"


async def create_order(
    db: AsyncSession,
    user: User,
    tier: SubscriptionTier,
    billing_cycle: BillingCycle,
) -> CreateOrderResponse:
    """创建支付订单"""
    if tier not in (SubscriptionTier.BASIC, SubscriptionTier.PREMIUM):
        raise InvalidPlanError(f"Cannot purchase tier: {tier.value}")

    price_key = (tier, billing_cycle)
    if price_key not in PRICING:
        raise InvalidPlanError(f"Invalid plan: {tier.value}/{billing_cycle.value}")

    amount_cents, subscription_days = PRICING[price_key]

    # 取消该用户所有待支付订单
    await db.execute(
        update(PaymentOrder)
        .where(
            PaymentOrder.user_id == user.id,
            PaymentOrder.status == OrderStatus.PENDING,
        )
        .values(status=OrderStatus.CANCELLED)
    )

    now = datetime.now(timezone.utc)
    out_trade_no = _generate_trade_no()

    order = PaymentOrder(
        user_id=user.id,
        out_trade_no=out_trade_no,
        target_tier=tier,
        billing_cycle=billing_cycle,
        amount_cents=amount_cents,
        subscription_days=subscription_days,
        status=OrderStatus.PENDING,
        expires_at=now + timedelta(minutes=ORDER_EXPIRY_MINUTES),
    )
    db.add(order)
    await db.flush()

    tier_name = _TIER_NAMES.get(tier, tier.value)
    cycle_name = _CYCLE_NAMES.get(billing_cycle, billing_cycle.value)
    subject = f"uStudy {tier_name} - {cycle_name}"
    total_amount = _cents_to_yuan(amount_cents)

    payment_url = await create_alipay_page_url(
        out_trade_no=out_trade_no,
        total_amount=total_amount,
        subject=subject,
    )

    await db.commit()
    await db.refresh(order)

    return CreateOrderResponse(
        order_id=order.id,
        out_trade_no=out_trade_no,
        payment_url=payment_url,
        amount_cents=amount_cents,
        amount_display=f"¥{total_amount}",
        expires_at=order.expires_at,
    )


async def handle_alipay_notification(form_data: dict) -> bool:
    """处理支付宝异步通知回调（使用独立 session）"""
    verified = await verify_alipay_notification(form_data)
    if not verified:
        logger.warning("Alipay notification signature verification failed")
        return False

    out_trade_no = form_data.get("out_trade_no")
    trade_status = form_data.get("trade_status")
    alipay_trade_no = form_data.get("trade_no", "")
    total_amount_str = form_data.get("total_amount", "0")

    if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
        logger.info(f"Ignoring trade_status={trade_status} for {out_trade_no}")
        return True  # non-success status, acknowledge but skip

    # 解析支付金额（元 → 分）
    try:
        paid_amount_cents = round(float(total_amount_str) * 100)
    except (ValueError, TypeError):
        logger.error(f"Invalid total_amount: {total_amount_str}")
        return False

    async with get_scoped_session() as session:
        # SELECT FOR UPDATE 防止并发重复处理
        result = await session.execute(
            select(PaymentOrder)
            .where(PaymentOrder.out_trade_no == out_trade_no)
            .with_for_update()
        )
        order = result.scalar_one_or_none()

        if order is None:
            logger.error(f"Order not found: {out_trade_no}")
            return False

        if order.status != OrderStatus.PENDING:
            logger.info(f"Order {out_trade_no} already {order.status.value}, skipping")
            return True  # idempotent

        # 验证支付金额与订单金额一致
        if paid_amount_cents != order.amount_cents:
            logger.error(
                f"Amount mismatch for {out_trade_no}: "
                f"expected {order.amount_cents}, got {paid_amount_cents}"
            )
            return False

        now = datetime.now(timezone.utc)
        order.status = OrderStatus.PAID
        order.alipay_trade_no = alipay_trade_no
        order.paid_at = now

        await _activate_subscription(session, order.user_id, order)
        await session.commit()

    logger.info(
        f"Order {out_trade_no} PAID, tier={order.target_tier.value}, "
        f"days={order.subscription_days}"
    )
    return True


async def _activate_subscription(
    session: AsyncSession,
    user_id,
    order: PaymentOrder,
) -> None:
    """激活订阅 — 如有未过期订阅则从到期日延续，否则从现在开始"""
    result = await session.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = result.scalar_one()

    now = datetime.now(timezone.utc)
    current_expiry = user.subscription_expires_at

    # 如果用户有未过期的付费订阅，从到期日延续
    if (
        current_expiry is not None
        and current_expiry > now
        and user.subscription_tier != SubscriptionTier.FREE
    ):
        base = current_expiry
    else:
        base = now

    new_expiry = base + timedelta(days=order.subscription_days)
    user.subscription_tier = order.target_tier
    user.subscription_expires_at = new_expiry


async def get_order_status(
    db: AsyncSession,
    order_id,
    user_id,
) -> OrderStatusResponse:
    """查询订单状态（用于前端轮询）"""
    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.id == order_id,
            PaymentOrder.user_id == user_id,
        )
    )
    order = result.scalar_one_or_none()

    if order is None:
        raise OrderNotFoundError("Order not found")

    # 检查是否已自然过期
    if (
        order.status == OrderStatus.PENDING
        and order.expires_at < datetime.now(timezone.utc)
    ):
        order.status = OrderStatus.EXPIRED
        await db.commit()
        await db.refresh(order)

    return OrderStatusResponse(
        order_id=order.id,
        out_trade_no=order.out_trade_no,
        status=order.status,
        target_tier=order.target_tier,
        billing_cycle=order.billing_cycle,
        amount_cents=order.amount_cents,
        subscription_days=order.subscription_days,
        paid_at=order.paid_at,
        created_at=order.created_at,
    )


async def list_user_orders(
    db: AsyncSession,
    user_id,
    limit: int = 20,
) -> list[OrderListItem]:
    """获取用户最近订单列表"""
    result = await db.execute(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user_id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(limit)
    )
    orders = result.scalars().all()

    return [
        OrderListItem(
            order_id=o.id,
            out_trade_no=o.out_trade_no,
            status=o.status,
            target_tier=o.target_tier,
            billing_cycle=o.billing_cycle,
            amount_cents=o.amount_cents,
            created_at=o.created_at,
        )
        for o in orders
    ]


async def expire_stale_orders() -> int:
    """过期未支付订单（由 scheduler 调用）"""
    async with get_scoped_session() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            update(PaymentOrder)
            .where(
                PaymentOrder.status == OrderStatus.PENDING,
                PaymentOrder.expires_at < now,
            )
            .values(status=OrderStatus.EXPIRED)
        )
        count = result.rowcount
        await session.commit()

    if count > 0:
        logger.info(f"Expired {count} stale payment orders")
    return count
