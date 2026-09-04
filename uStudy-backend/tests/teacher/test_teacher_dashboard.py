from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import scripts.manage_experiment_accounts as account_script
from agents.mastery_update_agent import MasteryUpdateAgent
from db.models import (
    Edge,
    EdgeType,
    Node,
    NodeMasteryEvent,
    NodeUserMastery,
    Quiz,
    QuizAttempt,
    Space,
    SpaceMember,
    SpaceMemberRole,
    StudyActivityLog,
    User,
)
from experiment.default_course import DEFAULT_SPACE_ID
from graph.service import GraphService
from spaces.service import SpaceService
from teacher.dependencies import require_course_teacher
from teacher.service import TeacherAnalyticsService, build_period


async def seed_course(db: AsyncSession):
    teacher = User(email="teacher@example.com", nickname="Teacher")
    first = User(email="student-one@example.com", nickname="Student One")
    second = User(email="student-two@example.com", nickname="Student Two")
    db.add_all([teacher, first, second])
    await db.flush()
    space = Space(
        id=DEFAULT_SPACE_ID,
        user_id=teacher.id,
        name="数据结构",
        color="#3B82F6",
        is_collaborative=True,
    )
    db.add(space)
    await db.flush()
    db.add_all(
        [
            SpaceMember(
                space_id=space.id,
                user_id=teacher.id,
                role=SpaceMemberRole.TEACHER,
                can_edit_graph=False,
            ),
            SpaceMember(
                space_id=space.id,
                user_id=first.id,
                role=SpaceMemberRole.MEMBER,
                can_edit_graph=False,
            ),
            SpaceMember(
                space_id=space.id,
                user_id=second.id,
                role=SpaceMemberRole.MEMBER,
                can_edit_graph=False,
            ),
        ]
    )
    nodes = [
        Node(space_id=space.id, label="数据结构"),
        Node(space_id=space.id, label="线性表"),
    ]
    db.add_all(nodes)
    await db.commit()
    return teacher, first, second, space, nodes


def test_period_uses_shanghai_calendar_and_rejects_unknown_days():
    period = build_period(7, datetime(2026, 8, 25, 16, 30, tzinfo=timezone.utc))
    assert period.start_local.date().isoformat() == "2026-08-20"
    assert (period.end_local.date()).isoformat() == "2026-08-27"
    with pytest.raises(ValueError):
        build_period(14)


@pytest.mark.asyncio
async def test_teacher_authorization_excludes_students(db_session: AsyncSession):
    teacher, student, _, space, _ = await seed_course(db_session)
    assert await require_course_teacher(space.id, teacher, db_session) is teacher
    with pytest.raises(HTTPException) as exc_info:
        await require_course_teacher(space.id, student, db_session)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_teacher_authorization_accepts_any_space_but_only_exact_teacher_role(
    db_session: AsyncSession,
):
    owner = User(email="owner-role@example.com", nickname="Owner")
    teacher = User(email="teacher-role@example.com", nickname="Teacher")
    member = User(email="member-role@example.com", nickname="Member")
    other_teacher = User(email="other-teacher@example.com", nickname="Other Teacher")
    db_session.add_all([owner, teacher, member, other_teacher])
    await db_session.flush()
    course = Space(user_id=owner.id, name="算法", color="#123456")
    other_course = Space(user_id=owner.id, name="数据库", color="#654321")
    db_session.add_all([course, other_course])
    await db_session.flush()
    db_session.add_all(
        [
            SpaceMember(
                space_id=course.id,
                user_id=owner.id,
                role=SpaceMemberRole.OWNER,
            ),
            SpaceMember(
                space_id=course.id,
                user_id=teacher.id,
                role=SpaceMemberRole.TEACHER,
            ),
            SpaceMember(
                space_id=course.id,
                user_id=member.id,
                role=SpaceMemberRole.MEMBER,
            ),
            SpaceMember(
                space_id=other_course.id,
                user_id=other_teacher.id,
                role=SpaceMemberRole.TEACHER,
            ),
        ]
    )
    await db_session.commit()

    assert await require_course_teacher(course.id, teacher, db_session) is teacher
    for unauthorized in (owner, member, other_teacher):
        with pytest.raises(HTTPException) as exc_info:
            await require_course_teacher(course.id, unauthorized, db_session)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "TEACHER_REQUIRED"


@pytest.mark.asyncio
async def test_chapter_map_uses_top_level_children_of_a_single_generic_root(
    db_session: AsyncSession,
):
    teacher = User(email="chapter-teacher@example.com", nickname="Teacher")
    db_session.add(teacher)
    await db_session.flush()
    course = Space(user_id=teacher.id, name="算法", color="#123456")
    db_session.add(course)
    await db_session.flush()
    root = Node(space_id=course.id, label="算法课程")
    sorting = Node(space_id=course.id, label="排序")
    quicksort = Node(space_id=course.id, label="快速排序")
    graph = Node(space_id=course.id, label="图算法")
    db_session.add_all([root, sorting, quicksort, graph])
    await db_session.flush()
    db_session.add_all(
        [
            Edge(
                space_id=course.id,
                from_node_id=root.id,
                to_node_id=sorting.id,
                type=EdgeType.KNOWLEDGE_TREE,
            ),
            Edge(
                space_id=course.id,
                from_node_id=sorting.id,
                to_node_id=quicksort.id,
                type=EdgeType.KNOWLEDGE_TREE,
            ),
            Edge(
                space_id=course.id,
                from_node_id=root.id,
                to_node_id=graph.id,
                type=EdgeType.KNOWLEDGE_TREE,
            ),
        ]
    )
    await db_session.commit()

    chapter_map = await TeacherAnalyticsService(db_session, course.id, 7)._chapter_map(
        [(node.id, node.label) for node in (root, sorting, quicksort, graph)]
    )

    assert chapter_map == {
        root.id: "算法课程",
        sorting.id: "排序",
        quicksort.id: "排序",
        graph.id: "图算法",
    }


@pytest.mark.asyncio
async def test_chapter_map_handles_forests_isolates_and_cycles(
    db_session: AsyncSession,
):
    teacher = User(email="forest-teacher@example.com", nickname="Teacher")
    db_session.add(teacher)
    await db_session.flush()
    course = Space(user_id=teacher.id, name="综合课程", color="#123456")
    db_session.add(course)
    await db_session.flush()
    root_a = Node(space_id=course.id, label="甲章")
    child_a = Node(space_id=course.id, label="甲节")
    root_b = Node(space_id=course.id, label="乙章")
    child_b = Node(space_id=course.id, label="乙节")
    isolated = Node(space_id=course.id, label="独立主题")
    cycle_a = Node(space_id=course.id, label="循环甲")
    cycle_b = Node(space_id=course.id, label="循环乙")
    nodes = [root_a, child_a, root_b, child_b, isolated, cycle_a, cycle_b]
    db_session.add_all(nodes)
    await db_session.flush()
    db_session.add_all(
        [
            Edge(
                space_id=course.id,
                from_node_id=root_a.id,
                to_node_id=child_a.id,
                type=EdgeType.KNOWLEDGE_TREE,
            ),
            Edge(
                space_id=course.id,
                from_node_id=root_b.id,
                to_node_id=child_b.id,
                type=EdgeType.KNOWLEDGE_TREE,
            ),
            Edge(
                space_id=course.id,
                from_node_id=cycle_a.id,
                to_node_id=cycle_b.id,
                type=EdgeType.KNOWLEDGE_TREE,
            ),
            Edge(
                space_id=course.id,
                from_node_id=cycle_b.id,
                to_node_id=cycle_a.id,
                type=EdgeType.KNOWLEDGE_TREE,
            ),
        ]
    )
    await db_session.commit()

    chapter_map = await TeacherAnalyticsService(db_session, course.id, 7)._chapter_map(
        [(node.id, node.label) for node in nodes]
    )

    assert chapter_map[root_a.id] == "甲章"
    assert chapter_map[child_a.id] == "甲章"
    assert chapter_map[root_b.id] == "乙章"
    assert chapter_map[child_b.id] == "乙章"
    assert chapter_map[isolated.id] == "独立主题"
    assert chapter_map[cycle_a.id] == chapter_map[cycle_b.id]
    assert chapter_map[cycle_a.id] in {"循环甲", "循环乙"}


@pytest.mark.asyncio
async def test_overview_uses_students_only_and_keeps_missing_mastery_null_safe(
    db_session: AsyncSession,
):
    teacher, first, _, space, nodes = await seed_course(db_session)
    now = datetime.now(timezone.utc)
    db_session.add(
        NodeUserMastery(node_id=nodes[1].id, user_id=first.id, mastery=80)
    )
    db_session.add(
        NodeMasteryEvent(
            space_id=space.id,
            node_id=nodes[1].id,
            user_id=first.id,
            previous_mastery=None,
            new_mastery=80,
            source="baseline",
            created_at=now,
        )
    )
    db_session.add(
        StudyActivityLog(
            user_id=first.id,
            space_id=space.id,
            title="线性表学习",
            summary="理解了顺序表与链表的差异",
            activity_type="学习新知识",
            subject_name="数据结构",
            message_count=4,
            source="conversation",
            activity_date=now.date(),
            activity_time=now,
        )
    )
    db_session.add(
        StudyActivityLog(
            user_id=first.id,
            space_id=space.id,
            title="线性表测验活动",
            summary="完成了一次测验",
            activity_type="测验",
            subject_name="数据结构",
            message_count=0,
            source="quiz",
            activity_date=now.date(),
            activity_time=now,
        )
    )
    quiz = Quiz(space_id=space.id, title="线性表测验", topic="线性表", total_questions=1)
    db_session.add(quiz)
    await db_session.flush()
    db_session.add(
        QuizAttempt(
            quiz_id=quiz.id,
            user_id=first.id,
            status="completed",
            score=8,
            total_score=10,
            strengths=["基础概念"],
            weaknesses=[],
            suggestions=[],
            question_results=[],
            submitted_at=now,
        )
    )
    await db_session.commit()

    overview = await TeacherAnalyticsService(db_session, space.id, 7).get_overview()
    assert overview.students_total == 2
    assert overview.active_students == 1
    assert overview.active_rate == 50.0
    assert overview.knowledge_coverage == 25.0
    assert overview.avg_mastery == 80.0
    assert overview.quiz_participants == 1
    assert overview.quiz_accuracy == 80.0
    assert len(overview.daily_activity) == 7
    assert len(overview.activity_calendar) == 90
    today = overview.daily_activity[-1]
    assert today.active_students == 1
    assert today.active_rate == 50.0
    assert today.activity_count == 2
    assert sum(item.count for item in today.activity_mix) == today.activity_count
    assert {item.activity_type for item in today.activity_mix} == {"学习新知识", "测验"}
    assert sum(item.count for item in overview.activity_mix) == sum(
        item.activity_count for item in overview.daily_activity
    )
    assert teacher.id not in {
        row.user_id
        for row in (
            await db_session.execute(select(NodeUserMastery))
        ).scalars()
    }


@pytest.mark.asyncio
async def test_student_detail_returns_summaries_without_raw_answers(
    db_session: AsyncSession,
):
    _, student, _, space, _ = await seed_course(db_session)
    now = datetime.now(timezone.utc)
    quiz = Quiz(space_id=space.id, title="安全测验", topic="图", total_questions=1)
    db_session.add(quiz)
    await db_session.flush()
    db_session.add(
        QuizAttempt(
            quiz_id=quiz.id,
            user_id=student.id,
            status="completed",
            score=5,
            total_score=10,
            strengths=["遍历"],
            weaknesses=["SECRET-WEAKNESS-SUMMARY"],
            suggestions=["复习邻接表"],
            question_results=[{"correct_answer": "RAW-CORRECT-SECRET"}],
            user_answers_raw={"answer": "RAW-ANSWER-SECRET"},
            submitted_at=now,
        )
    )
    db_session.add(
        StudyActivityLog(
            user_id=student.id,
            space_id=space.id,
            title="图的遍历",
            summary="学习摘要可见",
            activity_type="学习新知识",
            message_count=3,
            source="conversation",
            activity_date=now.date(),
            activity_time=now,
        )
    )
    await db_session.commit()

    detail = await TeacherAnalyticsService(db_session, space.id, 7).get_student_detail(student.id)
    payload = detail.model_dump_json()
    assert "学习摘要可见" in payload
    assert "SECRET-WEAKNESS-SUMMARY" in payload
    assert "RAW-CORRECT-SECRET" not in payload
    assert "RAW-ANSWER-SECRET" not in payload
    assert "email" not in detail.student.model_dump()


@pytest.mark.asyncio
async def test_collaborative_mastery_writes_only_real_change_events(
    db_session: AsyncSession,
):
    _, student, _, space, nodes = await seed_course(db_session)
    service = GraphService(db_session)
    await service.update_mastery(space.id, nodes[1].id, 60, student.id, True)
    await service.update_mastery(space.id, nodes[1].id, 60, student.id, True)
    await service.update_mastery(space.id, nodes[1].id, 85, student.id, True)

    events = list(
        (
            await db_session.execute(
                select(NodeMasteryEvent)
                .where(NodeMasteryEvent.user_id == student.id)
                .order_by(NodeMasteryEvent.created_at, NodeMasteryEvent.id)
            )
        ).scalars()
    )
    assert [(item.previous_mastery, item.new_mastery) for item in events] == [
        (None, 60),
        (60, 85),
    ]
    assert all(item.source == "chat_tool" for item in events)


@pytest.mark.asyncio
async def test_quiz_mastery_path_records_reason_and_uses_database_previous_value(
    db_session: AsyncSession,
):
    _, student, _, space, nodes = await seed_course(db_session)
    agent = MasteryUpdateAgent(space.id, student.id, True)
    graph_nodes = [{"id": str(nodes[1].id), "label": nodes[1].label, "mastery": None}]
    plan = [{"node_name": nodes[1].label, "new_mastery": 72, "reason": "测验理解改善"}]
    await agent._execute_updates(db_session, graph_nodes, plan)
    # The prompt snapshot is intentionally stale; event creation must use the
    # current database value and avoid a duplicate event.
    await agent._execute_updates(db_session, graph_nodes, plan)

    events = list(
        (
            await db_session.execute(
                select(NodeMasteryEvent).where(NodeMasteryEvent.user_id == student.id)
            )
        ).scalars()
    )
    assert len(events) == 1
    assert events[0].source == "quiz_evaluation"
    assert events[0].previous_mastery is None
    assert events[0].new_mastery == 72
    assert events[0].reason == "测验理解改善"


@pytest.mark.asyncio
async def test_set_role_promotes_existing_member_without_graph_edit_permission(
    db_session: AsyncSession,
    monkeypatch,
):
    _, student, _, space, _ = await seed_course(db_session)

    @asynccontextmanager
    async def scoped_session_override():
        yield db_session

    monkeypatch.setattr(account_script, "get_scoped_session", scoped_session_override)
    await account_script.set_course_role(student.email, "teacher")
    member = await db_session.scalar(
        select(SpaceMember).where(
            SpaceMember.space_id == space.id,
            SpaceMember.user_id == student.id,
        )
    )
    assert member.role == SpaceMemberRole.TEACHER
    assert member.can_edit_graph is False


@pytest.mark.asyncio
async def test_teacher_is_excluded_from_student_members_and_leaderboard(
    db_session: AsyncSession,
):
    teacher, student, second, space, _ = await seed_course(db_session)
    service = SpaceService(db_session)
    members = await service.get_space_members(student.id, space.id)
    leaderboard = await service.get_space_leaderboard(student.id, space.id)
    expected_ids = {str(student.id), str(second.id)}
    assert {item["user_id"] for item in members} == expected_ids
    assert {item["user_id"] for item in leaderboard} == expected_ids
    assert str(teacher.id) not in expected_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [7, 30, 90])
async def test_activity_calendar_is_always_90_contiguous_days(
    db_session: AsyncSession,
    days: int,
):
    _, _, _, space, _ = await seed_course(db_session)
    overview = await TeacherAnalyticsService(db_session, space.id, days).get_overview()
    assert len(overview.daily_activity) == days
    assert len(overview.activity_calendar) == 90
    assert (
        overview.activity_calendar[-1].date - overview.activity_calendar[0].date
    ).days == 89
    assert all(point.activity_count == 0 for point in overview.activity_calendar)
    assert all(point.active_rate == 0.0 for point in overview.activity_calendar)


@pytest.mark.asyncio
async def test_activity_calendar_has_null_rate_when_course_has_no_students(
    db_session: AsyncSession,
):
    owner = User(email="empty-teacher@example.com", nickname="Empty Teacher")
    db_session.add(owner)
    await db_session.flush()
    space = Space(
        id=DEFAULT_SPACE_ID,
        user_id=owner.id,
        name="数据结构",
        color="#3B82F6",
        is_collaborative=True,
    )
    db_session.add(space)
    await db_session.flush()
    db_session.add(
        SpaceMember(
            space_id=space.id,
            user_id=owner.id,
            role=SpaceMemberRole.TEACHER,
            can_edit_graph=False,
        )
    )
    await db_session.commit()

    overview = await TeacherAnalyticsService(db_session, space.id, 7).get_overview()
    assert overview.students_total == 0
    assert len(overview.activity_calendar) == 90
    assert all(point.active_rate is None for point in overview.activity_calendar)
