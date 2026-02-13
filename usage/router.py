"""API router for usage statistics endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from db.database import get_db
from usage.schemas import (
    UsageBreakdownResponse,
    UsageHistoryResponse,
    UsageSummaryResponse,
)
from usage.service import UsageService

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    period: str = Query("month", pattern="^(day|week|month)$"),
    user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryResponse:
    """
    获取当前用户的用量摘要。

    - **period**: 统计周期 (day/week/month)

    返回:
    - 总 token 用量
    - 聊天/Embedding 分类用量
    - API 调用次数
    - 估算费用
    - 与上一周期的对比
    """
    return await UsageService.get_summary(db, user.id, period)


@router.get("/breakdown", response_model=UsageBreakdownResponse)
async def get_usage_breakdown(
    period: str = Query("month", pattern="^(day|week|month)$"),
    user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> UsageBreakdownResponse:
    """
    获取用量分类统计。

    按 usage_type 分组返回各类型的用量统计。
    """
    return await UsageService.get_breakdown(db, user.id, period)


@router.get("/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> UsageHistoryResponse:
    """
    获取用量历史记录。

    - **start_date**: 开始日期 (YYYY-MM-DD)
    - **end_date**: 结束日期 (YYYY-MM-DD)

    返回每日的用量统计和汇总数据。最大查询范围 365 天。
    """
    if end_date < start_date:
        raise HTTPException(400, "end_date must be after start_date")
    if (end_date - start_date).days > 365:
        raise HTTPException(400, "Date range cannot exceed 365 days")

    return await UsageService.get_history(db, user.id, start_date, end_date)
