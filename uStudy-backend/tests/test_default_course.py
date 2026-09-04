"""Fixed collaborative Data Structures course tests."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.schemas import LoginRequest, RegisterRequest
from auth.service import login, register
from chat.service import ChatService
from core.security import hash_password
from db.models import (
    Edge,
    EdgeType,
    LearningPathEvent,
    Node,
    NodeUserMastery,
    Space,
    SpaceMember,
    SpaceMemberRole,
    SubscriptionTier,
    User,
)
from experiment.default_course import (
    DEFAULT_SPACE_ID,
    SYSTEM_USER_ID,
    _parse_course_definition,
    ensure_default_course,
    ensure_managed_course_memberships,
    managed_course_membership_id,
)
from experiment.course_catalog import (
    COMPUTER_NETWORKS_SPACE_ID,
    OPERATING_SYSTEMS_SPACE_ID,
)
from graph.service import GraphService
from spaces.authorization import verify_space_graph_edit_access
from spaces.schemas import SpaceUpdate
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
    course_graph = _parse_course_definition()

    nodes = (
        await db_session.execute(select(Node).where(Node.space_id == DEFAULT_SPACE_ID))
    ).scalars().all()
    edges = (
        await db_session.execute(select(Edge).where(Edge.space_id == DEFAULT_SPACE_ID))
    ).scalars().all()
    assert len(nodes) == 74
    assert all(node.mastery is None for node in nodes)
    assert sum(edge.type == EdgeType.KNOWLEDGE_TREE for edge in edges) == 73
    assert sum(edge.type == EdgeType.ADVANCED for edge in edges) == 15
    assert sum(edge.type == EdgeType.LEARNING_PATH for edge in edges) == 0

    labels = {node.label for node in nodes}
    assert labels == {node.label for node in course_graph.nodes}
    assert all(
        edge.source_label in labels and edge.target_label in labels
        for edge in course_graph.edges
    )

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
async def test_experiment_space_list_returns_all_memberships_in_updated_order(
    db_session: AsyncSession,
):
    viewer = await add_student(db_session, "spaces-viewer@example.com", "Viewer")
    await ensure_default_course(db_session)
    other = await add_student(db_session, "spaces-owner@example.com", "Other Owner")

    default_space = await db_session.get(Space, DEFAULT_SPACE_ID)
    default_space.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    owned = Space(
        user_id=viewer.id,
        name="Owned",
        color="#111111",
        updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    taught = Space(
        user_id=other.id,
        name="Taught",
        color="#222222",
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    joined = Space(
        user_id=other.id,
        name="Joined",
        color="#333333",
        updated_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    hidden = Space(
        user_id=other.id,
        name="Hidden",
        color="#444444",
        updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    db_session.add_all([owned, taught, joined, hidden])
    await db_session.flush()
    db_session.add_all(
        [
            SpaceMember(
                space_id=owned.id,
                user_id=viewer.id,
                role=SpaceMemberRole.OWNER,
            ),
            SpaceMember(
                space_id=taught.id,
                user_id=viewer.id,
                role=SpaceMemberRole.TEACHER,
            ),
            SpaceMember(
                space_id=joined.id,
                user_id=viewer.id,
                role=SpaceMemberRole.MEMBER,
            ),
        ]
    )
    await db_session.commit()

    spaces = await SpaceService(db_session).get_user_spaces(viewer.id)

    assert [space.id for space in spaces] == [
        owned.id,
        taught.id,
        joined.id,
        DEFAULT_SPACE_ID,
    ]
    assert {space.id: space.user_role for space in spaces} == {
        owned.id: "owner",
        taught.id: "teacher",
        joined.id: "member",
        DEFAULT_SPACE_ID: "member",
    }
    assert hidden.id not in {space.id for space in spaces}


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


@pytest.mark.asyncio
async def test_managed_courses_auto_join_without_downgrading_roles(
    db_session: AsyncSession,
):
    owner = await add_student(db_session, "catalog-owner@example.com", "Owner")
    student = await add_student(db_session, "catalog-student@example.com", "Student")
    delegated = await add_student(db_session, "catalog-teacher@example.com", "Teacher")
    db_session.add_all(
        [
            Space(
                id=COMPUTER_NETWORKS_SPACE_ID,
                user_id=owner.id,
                name="计算机网络",
                color="#123456",
                is_collaborative=True,
            ),
            Space(
                id=OPERATING_SYSTEMS_SPACE_ID,
                user_id=owner.id,
                name="计算机操作系统",
                color="#654321",
                is_collaborative=True,
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        SpaceMember(
            space_id=COMPUTER_NETWORKS_SPACE_ID,
            user_id=delegated.id,
            role=SpaceMemberRole.TEACHER,
        )
    )
    await db_session.commit()

    joined = await ensure_managed_course_memberships(db_session, student.id)
    await ensure_managed_course_memberships(db_session, delegated.id)
    await ensure_managed_course_memberships(db_session, student.id)
    await db_session.commit()

    assert joined == {COMPUTER_NETWORKS_SPACE_ID, OPERATING_SYSTEMS_SPACE_ID}
    memberships = list(
        (
            await db_session.execute(
                select(SpaceMember).where(
                    SpaceMember.user_id.in_([student.id, delegated.id]),
                    SpaceMember.space_id.in_(
                        [COMPUTER_NETWORKS_SPACE_ID, OPERATING_SYSTEMS_SPACE_ID]
                    ),
                )
            )
        ).scalars()
    )
    membership_map = {
        (member.user_id, member.space_id): member for member in memberships
    }
    assert len(memberships) == 4
    assert (
        membership_map[(delegated.id, COMPUTER_NETWORKS_SPACE_ID)].role
        == SpaceMemberRole.TEACHER
    )
    for space_id in (COMPUTER_NETWORKS_SPACE_ID, OPERATING_SYSTEMS_SPACE_ID):
        member = membership_map[(student.id, space_id)]
        assert member.id == managed_course_membership_id(space_id, student.id)
        assert member.role == SpaceMemberRole.MEMBER


@pytest.mark.asyncio
async def test_default_seed_keeps_real_owner_and_repairs_unique_owner_membership(
    db_session: AsyncSession,
):
    teacher = await add_student(db_session, "real-owner@example.com", "Real Owner")
    stale_owner = await add_student(db_session, "stale-owner@example.com", "Stale Owner")
    system_user = User(
        id=SYSTEM_USER_ID,
        username="course_system",
        email="course-system@experiment.invalid",
        nickname="课程管理员",
        subscription_tier=SubscriptionTier.ALPHA,
    )
    db_session.add(system_user)
    await db_session.flush()
    db_session.add(
        Space(
            id=DEFAULT_SPACE_ID,
            user_id=teacher.id,
            name="旧名称",
            color="#112233",
            is_collaborative=True,
        )
    )
    await db_session.flush()
    db_session.add_all(
        [
            SpaceMember(
                space_id=DEFAULT_SPACE_ID,
                user_id=SYSTEM_USER_ID,
                role=SpaceMemberRole.OWNER,
            ),
            SpaceMember(
                space_id=DEFAULT_SPACE_ID,
                user_id=stale_owner.id,
                role=SpaceMemberRole.OWNER,
            ),
        ]
    )
    await db_session.commit()

    await ensure_default_course(db_session)

    space = await db_session.get(Space, DEFAULT_SPACE_ID)
    members = list(
        (
            await db_session.execute(
                select(SpaceMember).where(SpaceMember.space_id == DEFAULT_SPACE_ID)
            )
        ).scalars()
    )
    assert space.user_id == teacher.id
    assert space.name == "数据结构"
    assert all(member.user_id != SYSTEM_USER_ID for member in members)
    owner_members = [
        member for member in members if member.role == SpaceMemberRole.OWNER
    ]
    assert [member.user_id for member in owner_members] == [teacher.id]
    assert owner_members[0].can_edit_graph is True
    assert next(member for member in members if member.user_id == stale_owner.id).role == (
        SpaceMemberRole.MEMBER
    )


@pytest.mark.asyncio
async def test_managed_course_owner_can_update_settings_but_not_name_or_delete(
    db_session: AsyncSession,
):
    owner = await add_student(db_session, "managed-owner@example.com", "Owner")
    member = await add_student(db_session, "managed-member@example.com", "Member")
    space = Space(
        id=COMPUTER_NETWORKS_SPACE_ID,
        user_id=owner.id,
        name="计算机网络",
        color="#123456",
        is_collaborative=True,
    )
    db_session.add(space)
    await db_session.flush()
    db_session.add_all(
        [
            SpaceMember(
                space_id=space.id,
                user_id=owner.id,
                role=SpaceMemberRole.OWNER,
            ),
            SpaceMember(
                space_id=space.id,
                user_id=member.id,
                role=SpaceMemberRole.MEMBER,
            ),
        ]
    )
    await db_session.commit()
    service = SpaceService(db_session)

    response = await service.update_space(
        owner.id,
        space.id,
        SpaceUpdate(description="课程说明", review_mode=2),
    )
    assert response.description == "课程说明"
    assert response.review_mode == 2
    assert response.is_managed_course is True

    with pytest.raises(SpaceAccessDeniedError):
        await service.update_space(owner.id, space.id, SpaceUpdate(name="新名称"))
    with pytest.raises(SpaceAccessDeniedError):
        await service.update_space(
            member.id, space.id, SpaceUpdate(description="越权修改")
        )
    with pytest.raises(SpaceAccessDeniedError):
        await service.delete_space(owner.id, space.id)
    with pytest.raises(SpaceAccessDeniedError):
        await service.remove_member(member.id, space.id, member.id)
    with pytest.raises(SpaceAccessDeniedError):
        await service.update_member_permission(
            owner.id, space.id, member.id, can_edit_graph=True
        )
    membership = await db_session.scalar(
        select(SpaceMember).where(
            SpaceMember.space_id == space.id,
            SpaceMember.user_id == member.id,
        )
    )
    membership.can_edit_graph = True
    await db_session.commit()
    with pytest.raises(SpaceAccessDeniedError):
        await verify_space_graph_edit_access(db_session, space.id, member.id)


@pytest.mark.asyncio
async def test_cross_student_graph_and_path_events_require_teacher_access(
    db_session: AsyncSession,
):
    owner = await add_student(db_session, "path-owner@example.com", "Owner")
    first = await add_student(db_session, "path-first@example.com", "First")
    second = await add_student(db_session, "path-second@example.com", "Second")
    space = Space(
        id=OPERATING_SYSTEMS_SPACE_ID,
        user_id=owner.id,
        name="计算机操作系统",
        color="#123456",
        is_collaborative=True,
    )
    db_session.add(space)
    await db_session.flush()
    db_session.add_all(
        [
            SpaceMember(
                space_id=space.id,
                user_id=user_id,
                role=role,
            )
            for user_id, role in (
                (owner.id, SpaceMemberRole.OWNER),
                (first.id, SpaceMemberRole.MEMBER),
                (second.id, SpaceMemberRole.MEMBER),
            )
        ]
    )
    node = Node(space_id=space.id, label="进程")
    db_session.add(node)
    await db_session.flush()
    db_session.add_all(
        [
            NodeUserMastery(node_id=node.id, user_id=first.id, mastery=20),
            NodeUserMastery(node_id=node.id, user_id=second.id, mastery=90),
            LearningPathEvent(
                id=uuid4(),
                space_id=space.id,
                user_id=first.id,
                new_node_names=["线程"],
                trigger_info={"source": "first"},
            ),
            LearningPathEvent(
                id=uuid4(),
                space_id=space.id,
                user_id=second.id,
                new_node_names=["死锁"],
                trigger_info={"source": "second"},
            ),
        ]
    )
    await db_session.commit()
    service = SpaceService(db_session)

    own_events = await service.get_learning_path_events(first.id, space.id)
    assert [event.new_node_names for event in own_events] == [["线程"]]
    with pytest.raises(SpaceAccessDeniedError):
        await service.get_space_graph(first.id, space.id, target_user_id=second.id)
    with pytest.raises(SpaceAccessDeniedError):
        await service.get_learning_path_events(
            first.id, space.id, target_user_id=second.id
        )

    selected_graph = await service.get_space_graph(
        owner.id, space.id, target_user_id=second.id
    )
    selected_events = await service.get_learning_path_events(
        owner.id, space.id, target_user_id=second.id
    )
    assert selected_graph.nodes[0].mastery == 90
    assert [event.new_node_names for event in selected_events] == [["死锁"]]
