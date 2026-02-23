"""支付模块路由"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from payment.exceptions import (
    AlipayError,
    InvalidPlanError,
    OrderExpiredError,
    OrderNotFoundError,
)
from payment.schemas import (
    AdminConfirmRequest,
    CreateOrderRequest,
    CreateOrderResponse,
    OrderListItem,
    OrderStatusResponse,
)
from payment.service import (
    admin_confirm_order,
    create_order,
    get_order_status,
    handle_alipay_notification,
    list_pending_orders,
    list_user_orders,
    ADMIN_EMAILS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment", tags=["payment"])


@router.post("/orders", response_model=CreateOrderResponse)
async def create_payment_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建支付订单，发送管理员通知邮件"""
    try:
        return await create_order(db, current_user, request.tier, request.billing_cycle)
    except InvalidPlanError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AlipayError as e:
        logger.error(f"Payment error creating order: {e}")
        raise HTTPException(status_code=502, detail="支付服务暂时不可用，请稍后重试")


@router.get("/orders/{order_id}", response_model=OrderStatusResponse)
async def get_payment_order_status(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询订单状态（前端轮询用）"""
    try:
        return await get_order_status(db, order_id, current_user.id)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="订单不存在")
    except OrderExpiredError:
        raise HTTPException(status_code=410, detail="订单已过期")


@router.get("/orders", response_model=list[OrderListItem])
async def list_payment_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户最近订单列表"""
    return await list_user_orders(db, current_user.id)


# ---- 管理员接口 ----


@router.post("/admin/confirm", response_model=OrderStatusResponse)
async def admin_confirm_payment(
    request: AdminConfirmRequest,
    current_user: User = Depends(get_current_user),
):
    """管理员确认收款并激活订阅"""
    if current_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="无权限")
    try:
        return await admin_confirm_order(request.order_id, current_user)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="订单不存在")
    except OrderExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))


@router.get("/admin/pending", response_model=list[OrderListItem])
async def admin_list_pending_orders(
    current_user: User = Depends(get_current_user),
):
    """获取待确认订单列表（管理员用）"""
    if current_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="无权限")
    return await list_pending_orders()


# ---- 支付宝回调（保留以备将来使用）----


@router.post("/alipay/notify")
async def alipay_notify(request: Request):
    """支付宝异步通知回调（无需鉴权，由支付宝服务器调用）"""
    form_data = await request.form()
    data = dict(form_data)

    logger.info(f"Received Alipay notification: out_trade_no={data.get('out_trade_no')}")

    try:
        success = await handle_alipay_notification(data)
    except Exception:
        logger.exception("Failed to handle Alipay notification")
        success = False

    return PlainTextResponse("success" if success else "failure")
