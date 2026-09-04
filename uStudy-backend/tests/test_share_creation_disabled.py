"""Share-import feature-flag regression tests."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import (
    ShareMode,
    Space,
    SpaceMember,
    SpaceMemberRole,
    SpaceShareCode,
    User,
)
from share.router import import_space as import_shared_space
from share.schemas import ImportSpaceRequest


async def seed_share_code(
    db: AsyncSession,
    *,
    mode: ShareMode,
) -> tuple[User, User, Space, SpaceShareCode]:
    owner = User(email=f"owner-{mode.value}@example.com", nickname="Owner")
    importer = User(email=f"importer-{mode.value}@example.com", nickname="Importer")
    db.add_all([owner, importer])
    await db.flush()
    source = Space(user_id=owner.id, name="Source", color="#123456")
    db.add(source)
    await db.flush()
    code = SpaceShareCode(
        id=uuid4(),
        code="CLONE234" if mode == ShareMode.CLONE else "COLLAB23",
        space_id=source.id,
        creator_user_id=owner.id,
        share_mode=mode,
    )
    db.add_all(
        [
            SpaceMember(
                space_id=source.id,
                user_id=owner.id,
                role=SpaceMemberRole.OWNER,
            ),
            code,
        ]
    )
    await db.commit()
    return owner, importer, source, code


@pytest.mark.asyncio
async def test_clone_import_returns_feature_disabled_without_creating_space(
    db_session: AsyncSession,
    monkeypatch,
):
    _, importer, _, code = await seed_share_code(db_session, mode=ShareMode.CLONE)
    monkeypatch.setattr(get_settings(), "space_creation_enabled", False)
    count_before = await db_session.scalar(select(func.count()).select_from(Space))

    with pytest.raises(HTTPException) as exc_info:
        await import_shared_space(
            ImportSpaceRequest(share_code=code.code),
            db=db_session,
            current_user=importer,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == {
        "code": "FEATURE_DISABLED",
        "message": "新建学习空间功能在实验环境中不可用",
    }
    count_after = await db_session.scalar(select(func.count()).select_from(Space))
    assert count_after == count_before


@pytest.mark.asyncio
async def test_collaborative_import_still_joins_without_creating_space(
    db_session: AsyncSession,
    monkeypatch,
):
    _, importer, source, code = await seed_share_code(
        db_session,
        mode=ShareMode.COLLABORATIVE,
    )
    monkeypatch.setattr(get_settings(), "space_creation_enabled", False)
    count_before = await db_session.scalar(select(func.count()).select_from(Space))

    response = await import_shared_space(
        ImportSpaceRequest(share_code=code.code),
        db=db_session,
        current_user=importer,
    )

    membership = await db_session.scalar(
        select(SpaceMember).where(
            SpaceMember.space_id == source.id,
            SpaceMember.user_id == importer.id,
        )
    )
    assert response.id == source.id
    assert response.user_role == "member"
    assert membership is not None
    assert membership.role == SpaceMemberRole.MEMBER
    count_after = await db_session.scalar(select(func.count()).select_from(Space))
    assert count_after == count_before
