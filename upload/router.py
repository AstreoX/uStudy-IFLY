"""上传模块路由"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from upload.schemas import AvatarUploadResponse
from upload.service import upload_avatar

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/avatar", response_model=AvatarUploadResponse)
async def upload_user_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AvatarUploadResponse:
    """
    上传用户头像

    - 支持格式: JPEG, PNG, WebP
    - 最大大小: 2MB
    - 图片会自动调整为 256x256 并转换为 WebP 格式
    """
    # 读取文件内容
    file_data = await file.read()

    if not file_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件为空",
        )

    try:
        avatar_url = await upload_avatar(
            user_id=current_user.id,
            file_data=file_data,
            content_type=file.content_type,
            db=db,
        )
        return AvatarUploadResponse(
            success=True,
            avatar_url=avatar_url,
            message="头像上传成功",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="上传失败，请稍后重试",
        )
