"""Assessment aggregates use per-user mastery in collaborative courses."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from assessment.service import (
    ComprehensionService,
    DepthService,
    KnowledgeStructureService,
    ProfileStatsService,
    _get_user_node_masteries,
)
from db.models import (
    Edge,
    EdgeType,
    Node,
    NodeUserMastery,
    Space,
    SpaceMember,
    SpaceMemberRole,
    User,
)


@pytest.mark.asyncio
async def test_assessment_combines_personal_and_accessible_collaborative_mastery(
    db_session: AsyncSession,
):
    user = User(email="assessment-user@example.com", nickname="Learner")
    teacher = User(email="assessment-teacher@example.com", nickname="Teacher")
    other = User(email="assessment-other@example.com", nickname="Other")
    db_session.add_all([user, teacher, other])
    await db_session.flush()

    personal = Space(
        user_id=user.id,
        name="Personal",
        color="#111111",
        is_collaborative=False,
    )
    joined_course = Space(
        user_id=teacher.id,
        name="Joined course",
        color="#222222",
        is_collaborative=True,
    )
    owned_course = Space(
        user_id=user.id,
        name="Owned course",
        color="#333333",
        is_collaborative=True,
    )
    inaccessible_course = Space(
        user_id=other.id,
        name="Inaccessible course",
        color="#444444",
        is_collaborative=True,
    )
    db_session.add_all(
        [personal, joined_course, owned_course, inaccessible_course]
    )
    await db_session.flush()
    db_session.add_all(
        [
            SpaceMember(
                space_id=joined_course.id,
                user_id=user.id,
                role=SpaceMemberRole.MEMBER,
            ),
            SpaceMember(
                space_id=owned_course.id,
                user_id=user.id,
                role=SpaceMemberRole.OWNER,
            ),
        ]
    )

    personal_first = Node(space_id=personal.id, label="P1", mastery=40)
    personal_second = Node(space_id=personal.id, label="P2", mastery=None)
    joined_first = Node(space_id=joined_course.id, label="C1", mastery=99)
    joined_second = Node(space_id=joined_course.id, label="C2", mastery=99)
    owned_node = Node(space_id=owned_course.id, label="O1", mastery=99)
    inaccessible_node = Node(
        space_id=inaccessible_course.id, label="X1", mastery=99
    )
    db_session.add_all(
        [
            personal_first,
            personal_second,
            joined_first,
            joined_second,
            owned_node,
            inaccessible_node,
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            NodeUserMastery(
                node_id=joined_first.id, user_id=user.id, mastery=80
            ),
            NodeUserMastery(
                node_id=joined_second.id, user_id=other.id, mastery=100
            ),
            NodeUserMastery(node_id=owned_node.id, user_id=user.id, mastery=30),
            NodeUserMastery(
                node_id=inaccessible_node.id, user_id=user.id, mastery=100
            ),
            Edge(
                space_id=joined_course.id,
                from_node_id=joined_first.id,
                to_node_id=joined_second.id,
                type=EdgeType.KNOWLEDGE_TREE,
            ),
            Edge(
                space_id=joined_course.id,
                from_node_id=joined_second.id,
                to_node_id=joined_first.id,
                type=EdgeType.ADVANCED,
            ),
        ]
    )
    await db_session.commit()

    mastery_rows = await _get_user_node_masteries(db_session, user.id)
    mastery_by_node = {node_id: mastery for node_id, _, mastery in mastery_rows}
    assert mastery_by_node == {
        personal_first.id: 40,
        personal_second.id: None,
        joined_first.id: 80,
        joined_second.id: None,
        owned_node.id: 30,
    }

    profile = await ProfileStatsService.get_profile_stats(db_session, user.id)
    depth = await DepthService.get_depth_score(db_session, user.id)
    comprehension = await ComprehensionService.get_comprehension_score(
        db_session, user.id
    )
    structure = await KnowledgeStructureService.get_knowledge_structure_score(
        db_session, user.id
    )

    assert profile["avg_mastery"] == 50.0
    assert profile["node_coverage_percent"] == 60.0
    assert depth["mastery_score"] == 50.0
    assert depth["studied_node_count"] == 3
    assert depth["total_node_count"] == 5
    assert comprehension["high_mastery_node_count"] == 1
    assert comprehension["total_node_count"] == 5
    assert comprehension["mastery_ratio"] == 20.0
    assert structure["qualifying_parent_count"] == 1
    assert structure["total_node_count"] == 5
    assert structure["advanced_edge_count"] == 1
