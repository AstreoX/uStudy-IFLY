"""Authorization dependencies for teacher-only course analytics."""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from db.database import get_db
from db.models import Space, SpaceMember, SpaceMemberRole, User


async def has_course_teacher_access(
    db: AsyncSession, space_id: UUID, user_id: UUID
) -> bool:
    """Return whether the user is the real owner or a delegated course teacher."""

    is_owner = await db.scalar(
        select(Space.id).where(Space.id == space_id, Space.user_id == user_id)
    )
    if is_owner is not None:
        return True
    role = await db.scalar(
        select(SpaceMember.role).where(
            SpaceMember.space_id == space_id,
            SpaceMember.user_id == user_id,
        )
    )
    return role == SpaceMemberRole.TEACHER


async def require_course_teacher(
    space_id: UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> User:
    if not await has_course_teacher_access(db, space_id, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TEACHER_REQUIRED", "message": "仅课程教师可访问教学功能"},
        )
    return user
