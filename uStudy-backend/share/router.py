"""分享功能 API 端点"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from share.schemas import (
    GenerateShareCodeRequest,
    ImportSpaceRequest,
    ShareCodeResponse,
)
from share.service import ShareCodeError, ShareFeatureDisabledError, ShareService
from spaces.schemas import SpaceResponse

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
    except ShareFeatureDisabledError as e:
        raise HTTPException(
            status_code=404,
            detail={"code": "FEATURE_DISABLED", "message": str(e)},
        )
    except ShareCodeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return response
