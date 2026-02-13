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


@router.post("/activate", response_model=ActivateCodeResponse)
async def activate_endpoint(
    request: ActivateCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    使用激活码激活 Alpha 内测资格。

    - 激活码为一次性使用
    - 激活后用户等级变为 ALPHA
    - ALPHA 用户享受 30 天有效期
    """
    try:
        user = await activate_code(
            db=db,
            user_id=current_user.id,
            code=request.code,
        )

        asyncio.create_task(
            send_activation_notification(
                settings=get_settings(),
                user_email=user.email,
                user_nickname=user.nickname or user.email,
                activation_code=request.code.upper().strip(),
                expires_at=user.subscription_expires_at,
            )
        )

        return ActivateCodeResponse(
            success=True,
            subscription_tier=user.subscription_tier.value,
            subscription_expires_at=user.subscription_expires_at,
            message="激活成功！欢迎加入 Alpha 内测",
        )

    except ActivationError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message})
