"""Usage service for aggregation queries."""

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4, UUID

from sqlalchemy import case, cast, Date, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from usage.models import ApiUsageLog, AppUsageDaily, UsageType
from usage.schemas import (
    DailyUsage,
    UsageBreakdownResponse,
    UsageByType,
    UsageHistoryResponse,
    UsageSummaryResponse,
)


def _get_period_bounds(period: str) -> tuple[datetime, datetime]:
    """Calculate period start and end based on period string (UTC)."""
    now = datetime.now(timezone.utc)
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "week":
        # Start from Monday of current week
        days_since_monday = now.weekday()
        start = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=7)
    else:  # month
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Next month
        if now.month == 12:
            end = start.replace(year=now.year + 1, month=1)
        else:
            end = start.replace(month=now.month + 1)
    return start, end


def _get_previous_period_bounds(
    period: str, current_start: datetime
) -> tuple[datetime, datetime]:
    """Calculate previous period bounds for comparison."""
    if period == "day":
        prev_start = current_start - timedelta(days=1)
        prev_end = current_start
    elif period == "week":
        prev_start = current_start - timedelta(days=7)
        prev_end = current_start
    else:  # month
        # Safely handle month boundary by always using day=1
        if current_start.month == 1:
            prev_start = current_start.replace(year=current_start.year - 1, month=12, day=1)
        else:
            prev_start = current_start.replace(month=current_start.month - 1, day=1)
        prev_end = current_start
    return prev_start, prev_end


class UsageService:
    """Service for usage aggregation queries."""

    @staticmethod
    async def record_heartbeat(
        db: AsyncSession, user_id: UUID, seconds: int
    ) -> None:
        """Record app usage heartbeat via atomic UPSERT."""
        today = datetime.now(timezone.utc).date()
        stmt = pg_insert(AppUsageDaily).values(
            id=uuid4(),
            user_id=user_id,
            usage_date=today,
            total_seconds=seconds,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_app_usage_daily_user_date",
            set_={
                "total_seconds": AppUsageDaily.total_seconds + seconds,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)

    @staticmethod
    async def get_summary(
        db: AsyncSession, user_id: UUID, period: str = "month"
    ) -> UsageSummaryResponse:
        """Get usage summary for a period."""
        start, end = _get_period_bounds(period)

        # Query current period
        result = await db.execute(
            select(
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("total_tokens"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ApiUsageLog.usage_type.in_(
                                    [UsageType.CHAT_LLM, UsageType.AGENT_LLM]
                                ),
                                ApiUsageLog.total_tokens,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("chat_tokens"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ApiUsageLog.usage_type == UsageType.EMBEDDING,
                                ApiUsageLog.total_tokens,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("embedding_tokens"),
                func.count(
                    case(
                        (
                            ApiUsageLog.usage_type.in_(
                                [UsageType.CHAT_LLM, UsageType.AGENT_LLM]
                            ),
                            1,
                        )
                    )
                ).label("chat_calls"),
                func.count(
                    case((ApiUsageLog.usage_type == UsageType.EMBEDDING, 1))
                ).label("embedding_calls"),
                func.coalesce(func.sum(ApiUsageLog.estimated_cost_cents), 0).label(
                    "cost"
                ),
            )
            .where(ApiUsageLog.user_id == user_id)
            .where(ApiUsageLog.created_at >= start)
            .where(ApiUsageLog.created_at < end)
        )
        row = result.one()

        # Query previous period for comparison
        prev_start, prev_end = _get_previous_period_bounds(period, start)
        prev_result = await db.execute(
            select(func.coalesce(func.sum(ApiUsageLog.total_tokens), 0))
            .where(ApiUsageLog.user_id == user_id)
            .where(ApiUsageLog.created_at >= prev_start)
            .where(ApiUsageLog.created_at < prev_end)
        )
        prev_tokens = prev_result.scalar() or 0

        # Calculate change percent
        tokens_change_percent = None
        if prev_tokens > 0:
            tokens_change_percent = ((row.total_tokens - prev_tokens) / prev_tokens) * 100

        return UsageSummaryResponse(
            period_start=start,
            period_end=end,
            total_tokens=row.total_tokens,
            total_chat_tokens=row.chat_tokens,
            total_embedding_tokens=row.embedding_tokens,
            chat_calls=row.chat_calls,
            embedding_calls=row.embedding_calls,
            estimated_cost_cents=row.cost,
            tokens_change_percent=tokens_change_percent,
        )

    @staticmethod
    async def get_breakdown(
        db: AsyncSession, user_id: UUID, period: str = "month"
    ) -> UsageBreakdownResponse:
        """Get usage breakdown by type."""
        start, end = _get_period_bounds(period)

        result = await db.execute(
            select(
                ApiUsageLog.usage_type,
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("total_tokens"),
                func.count().label("call_count"),
                func.coalesce(func.sum(ApiUsageLog.estimated_cost_cents), 0).label("cost"),
            )
            .where(ApiUsageLog.user_id == user_id)
            .where(ApiUsageLog.created_at >= start)
            .where(ApiUsageLog.created_at < end)
            .group_by(ApiUsageLog.usage_type)
        )

        breakdown = [
            UsageByType(
                usage_type=row.usage_type,
                total_tokens=row.total_tokens,
                call_count=row.call_count,
                estimated_cost_cents=row.cost,
            )
            for row in result
        ]

        return UsageBreakdownResponse(
            period_start=start, period_end=end, breakdown=breakdown
        )

    @staticmethod
    async def get_history(
        db: AsyncSession, user_id: UUID, start_date: date, end_date: date
    ) -> UsageHistoryResponse:
        """Get daily usage history."""
        start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

        result = await db.execute(
            select(
                cast(ApiUsageLog.created_at, Date).label("date"),
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("total_tokens"),
                func.count().label("call_count"),
                func.coalesce(func.sum(ApiUsageLog.estimated_cost_cents), 0).label("cost"),
            )
            .where(ApiUsageLog.user_id == user_id)
            .where(ApiUsageLog.created_at >= start)
            .where(ApiUsageLog.created_at <= end)
            .group_by(cast(ApiUsageLog.created_at, Date))
            .order_by(cast(ApiUsageLog.created_at, Date))
        )

        daily_usage = [
            DailyUsage(
                date=row.date,
                total_tokens=row.total_tokens,
                call_count=row.call_count,
                estimated_cost_cents=row.cost,
            )
            for row in result
        ]

        total_tokens = sum(d.total_tokens for d in daily_usage)
        total_calls = sum(d.call_count for d in daily_usage)
        total_cost = sum(d.estimated_cost_cents for d in daily_usage)

        return UsageHistoryResponse(
            start_date=start_date,
            end_date=end_date,
            daily_usage=daily_usage,
            total_tokens=total_tokens,
            total_calls=total_calls,
            total_cost_cents=total_cost,
        )
