"""Admin module endpoints"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from admin.dependencies import require_admin
from admin.schemas import (
    AdminAnalytics,
    AdminStats,
    AdminUserDetail,
    AdminUserItem,
    AiOpsDashboard,
    PaginatedUsers,
)
from admin.service import (
    get_ai_ops_dashboard,
    get_analytics,
    get_stats,
    get_user_detail,
    get_users,
)
from db.database import get_db
from db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/verify")
async def verify_admin(admin: User = Depends(require_admin)):
    """Confirm the caller is an admin."""
    return {
        "is_admin": True,
        "email": admin.email,
        "nickname": admin.nickname,
    }


@router.get("/stats", response_model=AdminStats)
async def dashboard_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard statistics."""
    return await get_stats(db)


@router.get("/analytics", response_model=AdminAnalytics)
async def analytics(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard analytics with trend data."""
    return await get_analytics(db)


@router.get("/ai-stability", response_model=AiOpsDashboard)
async def ai_stability(
    hours: int = Query(24, ge=1, le=168),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """AI request stability metrics: failures, latency and TTFT."""
    return await get_ai_ops_dashboard(db, hours)


@router.get("/users", response_model=PaginatedUsers)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Paginated user list."""
    return await get_users(db, page, page_size, search)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(
    user_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """User detail with stats and recent orders."""
    try:
        return await get_user_detail(db, user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="用户不存在")


