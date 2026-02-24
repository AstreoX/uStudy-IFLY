"""Admin business logic"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.schemas import (
    AdminOrderItem,
    AdminStats,
    AdminUserDetail,
    AdminUserItem,
    PaginatedOrders,
    PaginatedUsers,
    TierCount,
)
from db.models import (
    Conversation,
    OrderStatus,
    PaymentOrder,
    Space,
    SubscriptionTier,
    User,
)

logger = logging.getLogger(__name__)


async def get_stats(db: AsyncSession) -> AdminStats:
    """Dashboard statistics."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Total users
    total_q = await db.execute(select(func.count()).select_from(User))
    total_users = total_q.scalar() or 0

    # Active subscriptions (non-FREE with future expiry)
    active_q = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.subscription_tier != SubscriptionTier.FREE,
            User.subscription_expires_at > now,
        )
    )
    active_subscriptions = active_q.scalar() or 0

    # New users in last 7 days
    new_q = await db.execute(
        select(func.count())
        .select_from(User)
        .where(User.created_at >= seven_days_ago)
    )
    new_users_7d = new_q.scalar() or 0

    # Pending orders count
    pending_q = await db.execute(
        select(func.count())
        .select_from(PaymentOrder)
        .where(PaymentOrder.status == OrderStatus.PENDING)
    )
    pending_count = pending_q.scalar() or 0

    # Revenue in last 30 days (sum of paid orders)
    rev_q = await db.execute(
        select(
            func.coalesce(func.sum(PaymentOrder.amount_cents), 0),
            func.count(),
        )
        .select_from(PaymentOrder)
        .where(
            PaymentOrder.status == OrderStatus.PAID,
            PaymentOrder.paid_at >= thirty_days_ago,
        )
    )
    rev_row = rev_q.one()
    revenue_30d_cents = rev_row[0] or 0
    paid_order_count_30d = rev_row[1] or 0

    # Users by tier
    tier_q = await db.execute(
        select(User.subscription_tier, func.count())
        .group_by(User.subscription_tier)
    )
    users_by_tier = [
        TierCount(tier=tier, count=count)
        for tier, count in tier_q.all()
    ]

    return AdminStats(
        total_users=total_users,
        active_subscriptions=active_subscriptions,
        new_users_7d=new_users_7d,
        pending_count=pending_count,
        revenue_30d_cents=revenue_30d_cents,
        paid_order_count_30d=paid_order_count_30d,
        users_by_tier=users_by_tier,
    )


async def get_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: str = "",
) -> PaginatedUsers:
    """Paginated user list with optional search."""
    base = select(User)
    count_base = select(func.count()).select_from(User)

    if search:
        pattern = f"%{search}%"
        condition = User.email.ilike(pattern) | User.nickname.ilike(pattern)
        base = base.where(condition)
        count_base = count_base.where(condition)

    total_q = await db.execute(count_base)
    total = total_q.scalar() or 0

    offset = (page - 1) * page_size
    rows_q = await db.execute(
        base.order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    users = rows_q.scalars().all()

    return PaginatedUsers(
        items=[
            AdminUserItem(
                id=u.id,
                email=u.email,
                nickname=u.nickname,
                avatar_url=u.avatar_url,
                subscription_tier=u.subscription_tier,
                subscription_expires_at=u.subscription_expires_at,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_user_detail(db: AsyncSession, user_id: UUID) -> AdminUserDetail:
    """User detail with counts and recent orders."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")

    spaces_q = await db.execute(
        select(func.count()).select_from(Space).where(Space.user_id == user_id)
    )
    spaces_count = spaces_q.scalar() or 0

    convos_q = await db.execute(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.user_id == user_id)
    )
    conversations_count = convos_q.scalar() or 0

    orders_q = await db.execute(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user_id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(10)
    )
    orders = orders_q.scalars().all()

    return AdminUserDetail(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        subscription_tier=user.subscription_tier,
        subscription_expires_at=user.subscription_expires_at,
        created_at=user.created_at,
        spaces_count=spaces_count,
        conversations_count=conversations_count,
        recent_orders=[
            AdminOrderItem(
                order_id=o.id,
                out_trade_no=o.out_trade_no,
                user_id=o.user_id,
                user_email=user.email,
                user_nickname=user.nickname,
                target_tier=o.target_tier,
                billing_cycle=o.billing_cycle,
                amount_cents=o.amount_cents,
                status=o.status,
                paid_at=o.paid_at,
                created_at=o.created_at,
            )
            for o in orders
        ],
    )


async def update_user_subscription(
    db: AsyncSession,
    user_id: UUID,
    tier: SubscriptionTier,
    expires_at: datetime | None,
) -> AdminUserItem:
    """Update a user's subscription tier and/or expiry."""
    result = await db.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError("User not found")

    user.subscription_tier = tier
    if expires_at is not None:
        user.subscription_expires_at = expires_at

    await db.flush()
    await db.refresh(user)

    logger.info(
        f"Admin updated user {user.email}: tier={tier.value}, expires_at={expires_at}"
    )

    return AdminUserItem(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        subscription_tier=user.subscription_tier,
        subscription_expires_at=user.subscription_expires_at,
        created_at=user.created_at,
    )


async def get_orders(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: str = "",
) -> PaginatedOrders:
    """Paginated order list with optional status filter."""
    base = (
        select(PaymentOrder, User.email, User.nickname)
        .join(User, PaymentOrder.user_id == User.id)
    )
    count_base = select(func.count()).select_from(PaymentOrder)

    if status_filter:
        try:
            order_status = OrderStatus(status_filter)
        except ValueError:
            pass
        else:
            base = base.where(PaymentOrder.status == order_status)
            count_base = count_base.where(PaymentOrder.status == order_status)

    total_q = await db.execute(count_base)
    total = total_q.scalar() or 0

    offset = (page - 1) * page_size
    rows_q = await db.execute(
        base.order_by(PaymentOrder.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = rows_q.all()

    return PaginatedOrders(
        items=[
            AdminOrderItem(
                order_id=o.id,
                out_trade_no=o.out_trade_no,
                user_id=o.user_id,
                user_email=email,
                user_nickname=nickname,
                target_tier=o.target_tier,
                billing_cycle=o.billing_cycle,
                amount_cents=o.amount_cents,
                status=o.status,
                paid_at=o.paid_at,
                created_at=o.created_at,
            )
            for o, email, nickname in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
