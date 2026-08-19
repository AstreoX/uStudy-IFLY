"""分享功能 API 端点"""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from config import get_settings
from db.database import get_db
from db.models import User
from share.notification import send_space_join_notification
from share.schemas import GenerateShareCodeRequest, ImportSpaceRequest, ShareCodeResponse
from share.service import ShareCodeError, ShareService
from spaces.schemas import SpaceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spaces", tags=["share"])


@router.post("/{space_id}/share-code", response_model=ShareCodeResponse)
async def generate_share_code(
    space_id: UUID,
    body: GenerateShareCodeRequest = GenerateShareCodeRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShareCodeResponse:
    """生成或获取学习空间的分享码

    - share_mode: "clone" (创建副本) 或 "collaborative" (共同学习)
    """
    try:
        return await ShareService.generate_share_code(
            db, current_user.id, space_id, share_mode=body.share_mode
        )
    except ShareCodeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import", response_model=SpaceResponse)
async def import_space(
    request: ImportSpaceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SpaceResponse:
    """通过分享码导入学习空间"""
    try:
        response = await ShareService.import_space(db, current_user.id, request.share_code)
    except ShareCodeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Send email notification to space owner when a user joins collaboratively
    if response.user_role == "member":
        owner = await db.get(User, response.user_id)
        if owner and owner.email:
            asyncio.create_task(
                send_space_join_notification(
                    settings=get_settings(),
                    owner_email=owner.email,
                    joiner_email=current_user.email,
                    joiner_nickname=current_user.nickname or "",
                    space_name=response.name,
                )
            )

    return response
