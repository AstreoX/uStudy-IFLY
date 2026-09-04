"""Authorization-aware space selection for vector-memory retrieval."""

from contextlib import asynccontextmanager
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import memory.retriever as retriever_module
from db.models import Space, SpaceMember, SpaceMemberRole, User
from memory.retriever import MemoryRetriever


class CapturingMemoryService:
    def __init__(self):
        self.embedding_client = self
        self.calls: list[dict] = []

    async def embed_query(self, _query: str) -> list[float]:
        return [0.0]

    async def search_memories(self, **kwargs):
        self.calls.append(kwargs)
        return []


@pytest.mark.asyncio
async def test_collaborative_member_searches_current_and_only_accessible_shared_spaces(
    db_session: AsyncSession, monkeypatch
):
    owner = User(email="memory-owner@example.com", nickname="Owner")
    member = User(email="memory-member@example.com", nickname="Member")
    outsider = User(email="memory-outsider@example.com", nickname="Outsider")
    db_session.add_all([owner, member, outsider])
    await db_session.flush()
    current_course = Space(
        user_id=owner.id,
        name="Current course",
        color="#111111",
        is_collaborative=True,
        memory_sharing_enabled=False,
    )
    joined_shared = Space(
        user_id=owner.id,
        name="Joined shared",
        color="#222222",
        is_collaborative=True,
        memory_sharing_enabled=True,
    )
    joined_private = Space(
        user_id=owner.id,
        name="Joined private",
        color="#333333",
        is_collaborative=True,
        memory_sharing_enabled=False,
    )
    inaccessible_shared = Space(
        user_id=outsider.id,
        name="Inaccessible shared",
        color="#444444",
        is_collaborative=True,
        memory_sharing_enabled=True,
    )
    db_session.add_all(
        [current_course, joined_shared, joined_private, inaccessible_shared]
    )
    await db_session.flush()
    db_session.add_all(
        [
            SpaceMember(
                space_id=space.id,
                user_id=member.id,
                role=SpaceMemberRole.MEMBER,
            )
            for space in (current_course, joined_shared, joined_private)
        ]
    )
    await db_session.commit()

    @asynccontextmanager
    async def scoped_session_override():
        yield db_session

    monkeypatch.setattr(
        retriever_module, "get_scoped_session", scoped_session_override
    )
    memory_service = CapturingMemoryService()
    monkeypatch.setattr(retriever_module, "MemoryService", lambda: memory_service)
    retriever = MemoryRetriever(member.id, current_course.id)

    searchable = await retriever._get_searchable_space_ids()
    await retriever.get_relevant_memories("路由协议")

    assert searchable[0] == current_course.id
    assert set(searchable) == {current_course.id, joined_shared.id}
    assert joined_private.id not in searchable
    assert inaccessible_shared.id not in searchable
    space_call = next(
        call
        for call in memory_service.calls
        if call["memory_type"].value == "space"
    )
    assert space_call["user_id"] == member.id
    assert set(space_call["space_ids"]) == {current_course.id, joined_shared.id}
