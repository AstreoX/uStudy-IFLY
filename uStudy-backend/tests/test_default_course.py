"""Fixed collaborative Data Structures course tests."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.schemas import LoginRequest, RegisterRequest
from auth.service import login, register
from chat.service import ChatService
from core.security import hash_password
from db.models import (
    Edge,
    EdgeType,
    Node,
    NodeUserMastery,
    Space,
    SpaceMember,
    SubscriptionTier,
    User,
)
from experiment.default_course import (
    ADVANCED_CONNECTIONS,
    DEFAULT_SPACE_ID,
    KNOWLEDGE_TREE,
    SYSTEM_USER_ID,
    TREE_CONNECTIONS,
    ensure_default_course,
)
from graph.service import GraphService
from spaces.schemas import SpaceUpdate
from spaces.authorization import verify_space_graph_edit_access
from spaces.service import SpaceAccessDeniedError, SpaceService


async def add_student(db: AsyncSession, email: str, nickname: str) -> User:
    user = User(
        email=email,
        nickname=nickname,
        subscription_tier=SubscriptionTier.ALPHA,
        subscription_expires_at=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_default_course_seed_is_exact_and_idempotent(db_session: AsyncSession):
    first = await add_student(db_session, "first@example.com", "First")
    second = await add_student(db_session, "second@example.com", "Second")

    await ensure_default_course(db_session)
    await ensure_default_course(db_session)

    space = await db_session.get(Space, DEFAULT_SPACE_ID)
    assert space is not None
    assert space.name == "数据结构"
    assert space.is_collaborative is True
    assert len(KNOWLEDGE_TREE) == 73
    assert len(TREE_CONNECTIONS) == 65
    assert len(ADVANCED_CONNECTIONS) == 15

    nodes = (
        await db_session.execute(select(Node).where(Node.space_id == DEFAULT_SPACE_ID))
    ).scalars().all()
    edges = (
        await db_session.execute(select(Edge).where(Edge.space_id == DEFAULT_SPACE_ID))
    ).scalars().all()
    assert len(nodes) == 73
    assert all(node.mastery is None for node in nodes)
    assert sum(edge.type == EdgeType.KNOWLEDGE_TREE for edge in edges) == 65
    assert sum(edge.type == EdgeType.ADVANCED for edge in edges) == 15
    assert sum(edge.type == EdgeType.LEARNING_PATH for edge in edges) == 0

    labels = {node.label for node in nodes}
    assert labels == {label for _, label in KNOWLEDGE_TREE}
    assert all(source in labels and target in labels for source, target in ADVANCED_CONNECTIONS)

    members = (
        await db_session.execute(
            select(SpaceMember).where(SpaceMember.space_id == DEFAULT_SPACE_ID)
        )
    ).scalars().all()
    assert {member.user_id for member in members} == {
        SYSTEM_USER_ID,
        first.id,
        second.id,
    }
    assert all(
        member.can_edit_graph is False
        for member in members
        if member.user_id != SYSTEM_USER_ID
    )


@pytest.mark.asyncio
async def test_collaborative_mastery_is_isolated_per_student(db_session: AsyncSession):
    first = await add_student(db_session, "mastery1@example.com", "Mastery 1")
    second = await add_student(db_session, "mastery2@example.com", "Mastery 2")
    await ensure_default_course(db_session)

    node = await db_session.scalar(
        select(Node).where(
            Node.space_id == DEFAULT_SPACE_ID,
            Node.label == "时间复杂度",
        )
    )
    db_session.add_all(
        [
            NodeUserMastery(node_id=node.id, user_id=first.id, mastery=25),
            NodeUserMastery(node_id=node.id, user_id=second.id, mastery=90),
        ]
    )
    await db_session.commit()

    first_graph = await GraphService(db_session).get_graph(
        DEFAULT_SPACE_ID, user_id=first.id, is_collaborative=True
    )
    second_graph = await GraphService(db_session).get_graph(
        DEFAULT_SPACE_ID, user_id=second.id, is_collaborative=True
    )
    first_node = next(item for item in first_graph["nodes"] if item["label"] == "时间复杂度")
    second_node = next(item for item in second_graph["nodes"] if item["label"] == "时间复杂度")
    assert first_node["mastery"] == 25
    assert second_node["mastery"] == 90


@pytest.mark.asyncio
async def test_students_cannot_mutate_or_leave_default_course(db_session: AsyncSession):
    student = await add_student(db_session, "readonly@example.com", "Read Only")
    await ensure_default_course(db_session)
    service = SpaceService(db_session)

    with pytest.raises(SpaceAccessDeniedError):
        await service.update_space(
            student.id,
            DEFAULT_SPACE_ID,
            SpaceUpdate(name="Changed"),
        )
    with pytest.raises(SpaceAccessDeniedError):
        await service.delete_space(student.id, DEFAULT_SPACE_ID)
    with pytest.raises(SpaceAccessDeniedError):
        await verify_space_graph_edit_access(db_session, DEFAULT_SPACE_ID, student.id)

    visible_members = await service.get_space_members(student.id, DEFAULT_SPACE_ID)
    assert all(item["user_id"] != str(SYSTEM_USER_ID) for item in visible_members)


@pytest.mark.asyncio
async def test_registration_and_login_auto_join_default_course(db_session: AsyncSession):
    await ensure_default_course(db_session)

    registered = await register(
        db_session,
        RegisterRequest(
            email="registered@example.com",
            password="Password123",
            nickname="Registered",
        ),
    )
    registered_membership = await db_session.scalar(
        select(SpaceMember.id).where(
            SpaceMember.space_id == DEFAULT_SPACE_ID,
            SpaceMember.user_id == registered.id,
        )
    )
    assert registered_membership is not None

    existing = User(
        email="existing-login@example.com",
        nickname="Existing Login",
        password_hash=hash_password("Password123"),
        subscription_tier=SubscriptionTier.ALPHA,
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)
    await login(
        db_session,
        LoginRequest(identifier=existing.email, password="Password123"),
    )
    login_membership = await db_session.scalar(
        select(SpaceMember.id).where(
            SpaceMember.space_id == DEFAULT_SPACE_ID,
            SpaceMember.user_id == existing.id,
        )
    )
    assert login_membership is not None


@pytest.mark.asyncio
async def test_space_chat_conversation_remains_available(db_session: AsyncSession):
    student = await add_student(db_session, "space-chat@example.com", "Space Chat")
    await ensure_default_course(db_session)
    conversation = await ChatService(db_session).create_conversation(
        student.id,
        DEFAULT_SPACE_ID,
        "数据结构学习",
    )
    assert conversation.space_id == DEFAULT_SPACE_ID
