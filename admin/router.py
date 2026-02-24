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
    PaginatedOrders,
    PaginatedUsers,
    UpdateSubscriptionRequest,
)
from admin.service import (
    get_analytics,
    get_orders,
    get_stats,
    get_user_detail,
    get_users,
    update_user_subscription,
)
from db.database import get_db
from db.models import User
from payment.exceptions import OrderExpiredError, OrderNotFoundError
from payment.service import admin_confirm_order

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


@router.put("/users/{user_id}/subscription", response_model=AdminUserItem)
async def update_subscription(
    user_id: UUID,
    body: UpdateSubscriptionRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update user subscription tier and/or expiry."""
    try:
        return await update_user_subscription(db, user_id, body.tier, body.expires_at)
    except ValueError:
        raise HTTPException(status_code=404, detail="用户不存在")


@router.get("/orders", response_model=PaginatedOrders)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Paginated order list."""
    return await get_orders(db, page, page_size, status)


@router.post("/orders/{order_id}/confirm")
async def confirm_order(
    order_id: UUID,
    admin: User = Depends(require_admin),
):
    """Confirm payment for an order (delegates to payment service)."""
    try:
        return await admin_confirm_order(order_id, admin)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="订单不存在")
    except OrderExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限")
