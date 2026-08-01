"""Activation code API routes."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.registration_notification import send_activation_notification
from config import get_settings
from db.database import get_db
from db.models import User

from .exceptions import ActivationError
from .schemas import ActivateCodeRequest, ActivateCodeResponse
from .service import activate_code

router = APIRouter(prefix="/api/auth", tags=["activation"])

_TIER_LABELS = {
    "FREE": "Free",
    "BASIC": "Plus",
    "PREMIUM": "Ultra",
    "ALPHA": "Alpha 内测",
    "ULTRA": "Ultra",
}


@router.post("/activate", response_model=ActivateCodeResponse)
async def activate_endpoint(
    request: ActivateCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    使用激活码开通订阅。

    - 激活码为一次性使用
    - 支持不同订阅等级和有效期
    - 同等级叠加时长，升级时旧时间作废
    """
    try:
        user = await activate_code(
            db=db,
            user_id=current_user.id,
            code=request.code,
        )

        tier_label = _TIER_LABELS.get(
            user.subscription_tier.value, user.subscription_tier.value
        )

        asyncio.create_task(
            send_activation_notification(
                settings=get_settings(),
                user_email=user.email,
                user_nickname=user.nickname or user.email,
                activation_code=request.code.upper().strip(),
                expires_at=user.subscription_expires_at,
                tier_name=tier_label,
            )
        )

        return ActivateCodeResponse(
            success=True,
            subscription_tier=user.subscription_tier.value,
            subscription_expires_at=user.subscription_expires_at,
            message=f"激活成功！已开通 {tier_label} 会员",
        )

    except ActivationError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
