"""Centralized space access authorization"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Space, SpaceMember, SpaceMemberRole
from experiment.course_catalog import is_managed_course


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


async def verify_space_graph_edit_access(
    db: AsyncSession, space_id: UUID, user_id: UUID
) -> Space:
    """Allow structural graph edits only for the owner or delegated editors."""
    space = await verify_space_access(db, space_id, user_id)
    if space.user_id == user_id:
        return space
    if is_managed_course(space_id):
        raise SpaceAccessDeniedError(
            f"Managed course graph is owner-only for user {user_id} in space {space_id}"
        )
    can_edit = await db.scalar(
        select(SpaceMember.can_edit_graph).where(
            SpaceMember.space_id == space_id,
            SpaceMember.user_id == user_id,
        )
    )
    if not can_edit:
        raise SpaceAccessDeniedError(
            f"Graph structure is read-only for user {user_id} in space {space_id}"
        )
    return space


async def get_user_role_in_space(
    db: AsyncSession, space_id: UUID, user_id: UUID
) -> str | None:
    """Get user's role in a space. Returns 'owner', 'teacher', 'member', or None."""
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
