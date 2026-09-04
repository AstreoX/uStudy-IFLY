"""Defense-in-depth authorization tests for graph chat tools."""

from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import chat.tools.graph_tools as graph_tools
from chat.service import _resolve_space_graph_edit_permission
from chat.tools.graph_tools import GraphToolExecutor
from db.models import Edge, EdgeType, Node, Space, SpaceMember, SpaceMemberRole, User
from experiment.course_catalog import COMPUTER_NETWORKS_SPACE_ID
from graph.service import GraphService


async def _seed_managed_course(db: AsyncSession):
    owner = User(email="graph-owner@example.com", nickname="Owner")
    first = User(email="graph-first@example.com", nickname="First")
    second = User(email="graph-second@example.com", nickname="Second")
    db.add_all([owner, first, second])
    await db.flush()
    space = Space(
        id=COMPUTER_NETWORKS_SPACE_ID,
        user_id=owner.id,
        name="计算机网络",
        color="#3366FF",
        is_collaborative=True,
    )
    db.add(space)
    await db.flush()
    db.add_all(
        [
            SpaceMember(
                space_id=space.id,
                user_id=owner.id,
                role=SpaceMemberRole.OWNER,
                can_edit_graph=True,
            ),
            SpaceMember(
                space_id=space.id,
                user_id=first.id,
                role=SpaceMemberRole.MEMBER,
                can_edit_graph=True,
            ),
            SpaceMember(
                space_id=space.id,
                user_id=second.id,
                role=SpaceMemberRole.MEMBER,
                can_edit_graph=False,
            ),
        ]
    )
    await db.commit()
    return owner, first, second, space


@pytest.mark.asyncio
async def test_managed_member_stale_edit_flag_cannot_write_through_chat_tool(
    db_session: AsyncSession, monkeypatch
):
    owner, member, _, space = await _seed_managed_course(db_session)
    root = Node(space_id=space.id, label="网络体系结构")
    db_session.add(root)
    await db_session.commit()

    assert await _resolve_space_graph_edit_permission(db_session, space, owner.id)
    assert not await _resolve_space_graph_edit_permission(db_session, space, member.id)

    @asynccontextmanager
    async def scoped_session_override():
        yield db_session

    monkeypatch.setattr(graph_tools, "get_scoped_session", scoped_session_override)
    executor = GraphToolExecutor(
        space.id,
        user_id=member.id,
        is_collaborative=True,
        can_edit_graph=True,
    )
    result = await executor.execute("delete_node", {"node_name": root.label})

    assert result.success is False
    assert "权限不足" in result.message
    assert await db_session.get(Node, root.id) is not None

    owner_executor = GraphToolExecutor(
        space.id,
        user_id=owner.id,
        is_collaborative=True,
        can_edit_graph=False,
    )
    owner_result = await owner_executor.execute(
        "add_node", {"label": "传输层", "from_node": root.label}
    )
    assert owner_result.success is True


@pytest.mark.asyncio
async def test_extend_learning_path_only_reads_current_users_path(
    db_session: AsyncSession,
):
    _, first, second, space = await _seed_managed_course(db_session)
    nodes = {
        label: Node(space_id=space.id, label=label)
        for label in ("A", "B", "C", "D", "E")
    }
    db_session.add_all(nodes.values())
    await db_session.flush()
    db_session.add_all(
        [
            Edge(
                space_id=space.id,
                from_node_id=nodes["A"].id,
                to_node_id=nodes["B"].id,
                type=EdgeType.LEARNING_PATH,
                user_id=first.id,
            ),
            Edge(
                space_id=space.id,
                from_node_id=nodes["C"].id,
                to_node_id=nodes["D"].id,
                type=EdgeType.LEARNING_PATH,
                user_id=second.id,
            ),
        ]
    )
    await db_session.commit()

    executor = GraphToolExecutor(
        space.id, user_id=first.id, is_collaborative=True
    )
    result = await executor._extend_learning_path(
        {"node_sequence": ["D", "E"]}, GraphService(db_session)
    )

    assert result.success is False
    assert "不是当前路径末尾" in result.message
    leaked_edge = await db_session.scalar(
        select(Edge.id).where(
            Edge.space_id == space.id,
            Edge.from_node_id == nodes["D"].id,
            Edge.to_node_id == nodes["E"].id,
            Edge.user_id == first.id,
        )
    )
    assert leaked_edge is None


@pytest.mark.asyncio
async def test_update_learning_path_segment_preserves_other_users_edges(
    db_session: AsyncSession,
):
    _, first, second, space = await _seed_managed_course(db_session)
    nodes = {
        label: Node(space_id=space.id, label=label)
        for label in ("A", "B", "C", "D")
    }
    db_session.add_all(nodes.values())
    await db_session.flush()
    for user_id in (first.id, second.id):
        db_session.add_all(
            [
                Edge(
                    space_id=space.id,
                    from_node_id=nodes["A"].id,
                    to_node_id=nodes["B"].id,
                    type=EdgeType.LEARNING_PATH,
                    user_id=user_id,
                ),
                Edge(
                    space_id=space.id,
                    from_node_id=nodes["B"].id,
                    to_node_id=nodes["D"].id,
                    type=EdgeType.LEARNING_PATH,
                    user_id=user_id,
                ),
            ]
        )
    await db_session.commit()

    executor = GraphToolExecutor(
        space.id, user_id=first.id, is_collaborative=True
    )
    result = await executor._update_learning_path_segment(
        {"node_sequence": ["A", "C", "D"]}, GraphService(db_session)
    )

    assert result.success is True
    remaining = list(
        (
            await db_session.execute(
                select(Edge).where(
                    Edge.space_id == space.id,
                    Edge.type == EdgeType.LEARNING_PATH,
                )
            )
        ).scalars()
    )
    pairs_by_user = {
        user_id: {
            (edge.from_node_id, edge.to_node_id)
            for edge in remaining
            if edge.user_id == user_id
        }
        for user_id in (first.id, second.id)
    }
    assert pairs_by_user[first.id] == {
        (nodes["A"].id, nodes["C"].id),
        (nodes["C"].id, nodes["D"].id),
    }
    assert pairs_by_user[second.id] == {
        (nodes["A"].id, nodes["B"].id),
        (nodes["B"].id, nodes["D"].id),
    }
