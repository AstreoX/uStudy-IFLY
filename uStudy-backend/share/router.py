"""分享功能 API 端点"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from share.schemas import ImportSpaceRequest, ShareCodeResponse
from share.service import ShareCodeError, ShareService
from spaces.schemas import SpaceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spaces", tags=["share"])


@router.post("/{space_id}/share-code", response_model=ShareCodeResponse)
async def generate_share_code(
    space_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShareCodeResponse:
    """生成或获取学习空间的分享码"""
    try:
        return await ShareService.generate_share_code(db, current_user.id, space_id)
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
        return await ShareService.import_space(db, current_user.id, request.share_code)
    except ShareCodeError as e:
        raise HTTPException(status_code=400, detail=str(e))
