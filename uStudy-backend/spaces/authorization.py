"""Centralized space access authorization"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Space, SpaceMember, SpaceMemberRole


class SpaceNotFoundError(Exception):
    pass


class SpaceAccessDeniedError(Exception):
    pass


async def verify_space_access(
    db: AsyncSession, space_id: UUID, user_id: UUID
) -> Space:
    """Verify user has access to space (owner OR member).

    Returns the Space object if access is granted.
    Raises SpaceNotFoundError or SpaceAccessDeniedError.
    """
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()

    if not space:
        raise SpaceNotFoundError(f"Space {space_id} not found")

    # Owner always has access
    if space.user_id == user_id:
        return space

    # Check membership
    member_result = await db.execute(
        select(SpaceMember).where(
            SpaceMember.space_id == space_id,
            SpaceMember.user_id == user_id,
        )
    )
    if member_result.scalar_one_or_none():
        return space

    raise SpaceAccessDeniedError(f"Access denied to space {space_id}")


async def verify_space_ownership(
    db: AsyncSession, space_id: UUID, user_id: UUID
) -> Space:
    """Verify user is the owner of the space.

    Returns the Space object if ownership is confirmed.
    Raises SpaceNotFoundError or SpaceAccessDeniedError.
    """
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()

    if not space:
        raise SpaceNotFoundError(f"Space {space_id} not found")

    if space.user_id != user_id:
        raise SpaceAccessDeniedError(f"Only the owner can perform this action on space {space_id}")

    return space


async def get_user_role_in_space(
    db: AsyncSession, space_id: UUID, user_id: UUID
) -> str | None:
    """Get user's role in a space. Returns 'owner', 'member', or None."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if not space:
        return None

    if space.user_id == user_id:
        return SpaceMemberRole.OWNER.value

    member_result = await db.execute(
        select(SpaceMember.role).where(
            SpaceMember.space_id == space_id,
            SpaceMember.user_id == user_id,
        )
    )
    member_role = member_result.scalar_one_or_none()
    if member_role:
        return member_role.value

    return None
