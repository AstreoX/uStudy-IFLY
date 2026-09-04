"""Authorization dependencies for teacher-only course analytics."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from db.database import get_db
from db.models import SpaceMember, SpaceMemberRole, User
from experiment.default_course import DEFAULT_SPACE_ID


async def require_course_teacher(
    space_id: UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> User:
    if space_id != DEFAULT_SPACE_ID:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "COURSE_NOT_FOUND", "message": "教师看板仅支持默认数据结构课程"},
        )

    role = await db.scalar(
        select(SpaceMember.role).where(
            SpaceMember.space_id == space_id,
            SpaceMember.user_id == user.id,
        )
    )
    if role != SpaceMemberRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TEACHER_REQUIRED", "message": "仅课程教师可访问教学看板"},
        )
    return user
