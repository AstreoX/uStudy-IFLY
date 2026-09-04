"""Admin business logic"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from admin.schemas import (
    ActivityTypeCount,
    AdminAnalytics,
    AiOpsBreakdownItem,
    AiOpsDashboard,
    AiOpsOverview,
    AiOpsRecentFailure,
    AiOpsTrendPoint,
    AdminStats,
    AdminUserDetail,
    AdminUserItem,
    ContentStats,
    DailyCount,
    DailyRevenue,
    PaginatedUsers,
    StatusCount,
    TierCount,
    TierRevenue,
)
from db.models import (
    Conversation,
    DailyStudyRecord,
    Message,
    Quiz,
    Space,
    StudyActivityLog,
    SubscriptionTier,
    User,
)
from usage.models import AiRequestLog

logger = logging.getLogger(__name__)

AI_OPS_SAMPLE_LIMIT = 20000


def _avg_int(values: list[int]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values))


def _percentile_int(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def _failure_rate(total: int, failures: int) -> float:
    if total <= 0:
        return 0.0
    return round(failures / total, 4)


def _ai_breakdown_item(key: str, rows: list[AiRequestLog]) -> AiOpsBreakdownItem:
    total = len(rows)
    failures = sum(1 for row in rows if row.status != "success")
    latencies = [row.latency_ms for row in rows if row.latency_ms is not None]
    ttfts = [row.ttft_ms for row in rows if row.ttft_ms is not None]
    return AiOpsBreakdownItem(
        key=key,
        total_calls=total,
        failure_count=failures,
        failure_rate=_failure_rate(total, failures),
        avg_latency_ms=_avg_int(latencies),
        avg_ttft_ms=_avg_int(ttfts),
    )


def _ai_breakdown_from_values(
    key: str,
    total: int,
    failures: int,
    avg_latency_ms: float | None,
    avg_ttft_ms: float | None,
) -> AiOpsBreakdownItem:
    return AiOpsBreakdownItem(
        key=key,
        total_calls=total,
        failure_count=failures,
        failure_rate=_failure_rate(total, failures),
        avg_latency_ms=round(avg_latency_ms) if avg_latency_ms is not None else None,
        avg_ttft_ms=round(avg_ttft_ms) if avg_ttft_ms is not None else None,
    )


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
        select(func.count()).select_from(User).where(User.created_at >= seven_days_ago)
    )
    new_users_7d = new_q.scalar() or 0

    # Users by tier
    tier_q = await db.execute(
        select(User.subscription_tier, func.count()).group_by(User.subscription_tier)
    )
    users_by_tier = [TierCount(tier=tier, count=count) for tier, count in tier_q.all()]

    return AdminStats(
        total_users=total_users,
        active_subscriptions=active_subscriptions,
        new_users_7d=new_users_7d,
        pending_count=0,
        revenue_30d_cents=0,
        paid_order_count_30d=0,
        users_by_tier=users_by_tier,
    )


async def get_analytics(db: AsyncSession) -> AdminAnalytics:
    """Analytics data for dashboard trend panels."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Build date lookup for filling gaps
    date_range = [
        (now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30, -1, -1)
    ]

    # 1. User growth 30d
    ug_q = await db.execute(
        select(
            func.date(User.created_at).label("d"),
            func.count().label("c"),
        )
        .where(User.created_at >= thirty_days_ago)
        .group_by(func.date(User.created_at))
    )
    ug_map = {str(row.d): row.c for row in ug_q.all()}
    user_growth_30d = [DailyCount(date=d, count=ug_map.get(d, 0)) for d in date_range]

    revenue_trend_30d = [DailyRevenue(date=d, amount_cents=0, order_count=0) for d in date_range]

    # 3. DAU 30d
    dau_q = await db.execute(
        select(
            DailyStudyRecord.study_date.label("d"),
            func.count(func.distinct(DailyStudyRecord.user_id)).label("c"),
        )
        .where(DailyStudyRecord.study_date >= thirty_days_ago.date())
        .group_by(DailyStudyRecord.study_date)
    )
    dau_map = {str(row.d): row.c for row in dau_q.all()}
    dau_30d = [DailyCount(date=d, count=dau_map.get(d, 0)) for d in date_range]

    # 4. Content stats
    spaces_q = await db.execute(select(func.count()).select_from(Space))
    convos_q = await db.execute(select(func.count()).select_from(Conversation))
    msgs_q = await db.execute(select(func.count()).select_from(Message))
    quizzes_q = await db.execute(select(func.count()).select_from(Quiz))
    content_stats = ContentStats(
        total_spaces=spaces_q.scalar() or 0,
        total_conversations=convos_q.scalar() or 0,
        total_messages=msgs_q.scalar() or 0,
        total_quizzes=quizzes_q.scalar() or 0,
    )

    orders_by_status = []

    # 6. Activity by type
    abt_q = await db.execute(
        select(StudyActivityLog.activity_type, func.count().label("c"))
        .group_by(StudyActivityLog.activity_type)
        .order_by(func.count().desc())
    )
    activity_by_type = [
        ActivityTypeCount(activity_type=atype, count=count)
        for atype, count in abt_q.all()
    ]

    revenue_by_tier = []

    return AdminAnalytics(
        user_growth_30d=user_growth_30d,
        revenue_trend_30d=revenue_trend_30d,
        dau_30d=dau_30d,
        content_stats=content_stats,
        orders_by_status=orders_by_status,
        activity_by_type=activity_by_type,
        revenue_by_tier=revenue_by_tier,
    )


async def get_ai_ops_dashboard(db: AsyncSession, hours: int = 24) -> AiOpsDashboard:
    """AI request stability metrics for admin operations."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)

    failure_case = case((AiRequestLog.status != "success", 1), else_=0)
    summary_result = await db.execute(
        select(
            func.count(AiRequestLog.id),
            func.coalesce(func.sum(failure_case), 0),
            func.avg(AiRequestLog.latency_ms),
            func.avg(AiRequestLog.ttft_ms),
            func.coalesce(func.sum(AiRequestLog.retry_count), 0),
        ).where(AiRequestLog.created_at >= since)
    )
    total, failures, avg_latency_ms, avg_ttft_ms, retry_count = summary_result.one()
    total = int(total or 0)
    failures = int(failures or 0)
    successes = total - failures

    metrics_result = await db.execute(
        select(AiRequestLog.latency_ms, AiRequestLog.ttft_ms)
        .where(AiRequestLog.created_at >= since)
        .where(
            (AiRequestLog.latency_ms.is_not(None)) | (AiRequestLog.ttft_ms.is_not(None))
        )
        .order_by(AiRequestLog.created_at.desc())
        .limit(AI_OPS_SAMPLE_LIMIT)
    )
    metric_rows = metrics_result.all()
    latencies = [row.latency_ms for row in metric_rows if row.latency_ms is not None]
    ttfts = [row.ttft_ms for row in metric_rows if row.ttft_ms is not None]

    overview = AiOpsOverview(
        total_calls=total,
        success_count=successes,
        failure_count=failures,
        failure_rate=_failure_rate(total, failures),
        avg_latency_ms=round(avg_latency_ms) if avg_latency_ms is not None else None,
        p95_latency_ms=_percentile_int(latencies, 0.95),
        avg_ttft_ms=round(avg_ttft_ms) if avg_ttft_ms is not None else None,
        p95_ttft_ms=_percentile_int(ttfts, 0.95),
        retry_count=int(retry_count or 0),
    )

    sample_result = await db.execute(
        select(AiRequestLog)
        .where(AiRequestLog.created_at >= since)
        .order_by(AiRequestLog.created_at.desc())
        .limit(AI_OPS_SAMPLE_LIMIT)
    )
    rows = list(sample_result.scalars().all())

    trend_map: dict[datetime, list[AiRequestLog]] = {}
    for row in rows:
        bucket = row.created_at.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        trend_map.setdefault(bucket, []).append(row)

    bucket_count = min(max(hours, 1), 168)
    trend: list[AiOpsTrendPoint] = []
    first_bucket = now.replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=bucket_count - 1
    )
    for i in range(bucket_count):
        bucket = first_bucket + timedelta(hours=i)
        bucket_rows = trend_map.get(bucket, [])
        bucket_latencies = [
            row.latency_ms for row in bucket_rows if row.latency_ms is not None
        ]
        bucket_ttfts = [row.ttft_ms for row in bucket_rows if row.ttft_ms is not None]
        trend.append(
            AiOpsTrendPoint(
                bucket=bucket.isoformat(),
                total_calls=len(bucket_rows),
                failure_count=sum(1 for row in bucket_rows if row.status != "success"),
                avg_latency_ms=_avg_int(bucket_latencies),
                avg_ttft_ms=_avg_int(bucket_ttfts),
            )
        )

    model_result = await db.execute(
        select(
            AiRequestLog.model,
            func.count(AiRequestLog.id),
            func.coalesce(func.sum(failure_case), 0),
            func.avg(AiRequestLog.latency_ms),
            func.avg(AiRequestLog.ttft_ms),
        )
        .where(AiRequestLog.created_at >= since)
        .group_by(AiRequestLog.model)
        .order_by(func.count(AiRequestLog.id).desc())
        .limit(8)
    )
    by_model = [
        _ai_breakdown_from_values(
            key=model or "unknown",
            total=int(total_calls or 0),
            failures=int(failure_count or 0),
            avg_latency_ms=avg_latency,
            avg_ttft_ms=avg_ttft,
        )
        for model, total_calls, failure_count, avg_latency, avg_ttft in model_result.all()
    ]

    source_result = await db.execute(
        select(
            AiRequestLog.source_module,
            AiRequestLog.source_operation,
            func.count(AiRequestLog.id),
            func.coalesce(func.sum(failure_case), 0),
            func.avg(AiRequestLog.latency_ms),
            func.avg(AiRequestLog.ttft_ms),
        )
        .where(AiRequestLog.created_at >= since)
        .group_by(AiRequestLog.source_module, AiRequestLog.source_operation)
        .order_by(func.count(AiRequestLog.id).desc())
        .limit(8)
    )
    by_source = [
        _ai_breakdown_from_values(
            key="/".join(part for part in [module, operation] if part) or "unknown",
            total=int(total_calls or 0),
            failures=int(failure_count or 0),
            avg_latency_ms=avg_latency,
            avg_ttft_ms=avg_ttft,
        )
        for module, operation, total_calls, failure_count, avg_latency, avg_ttft in source_result.all()
    ]

    failure_result = await db.execute(
        select(AiRequestLog, User.email)
        .outerjoin(User, AiRequestLog.user_id == User.id)
        .where(AiRequestLog.created_at >= since)
        .where(AiRequestLog.status != "success")
        .order_by(AiRequestLog.created_at.desc())
        .limit(20)
    )
    recent_failures = [
        AiOpsRecentFailure(
            id=row.id,
            created_at=row.created_at,
            model=row.model,
            request_kind=row.request_kind,
            source_module=row.source_module,
            source_operation=row.source_operation,
            user_email=email,
            http_status_code=row.http_status_code,
            error_type=row.error_type,
            error_message=(row.error_message[:240] if row.error_message else None),
            latency_ms=row.latency_ms,
            ttft_ms=row.ttft_ms,
        )
        for row, email in failure_result.all()
    ]

    return AiOpsDashboard(
        hours=hours,
        since=since,
        overview=overview,
        trend=trend,
        by_model=by_model,
        by_source=by_source,
        recent_failures=recent_failures,
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
        base.order_by(User.created_at.desc()).offset(offset).limit(page_size)
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
        recent_orders=[],
    )


