from datetime import datetime, timezone

import pytest
from db.models import (
    Folder,
    FolderContentType,
    Note,
    Quiz,
    QuizAttempt,
    Space,
    SpaceMember,
    SpaceMemberRole,
    StudyActivityLog,
    User,
)
from folders.schemas import MoveItemsRequest
from folders.service import FolderNotFoundError, FolderService
from notes.exceptions import NoteNotFoundError
from notes.schemas import NoteUpdate
from notes.service import NoteService
from quizzes.service import QuizNotFoundError, QuizService
from spaces.service import SpaceService
from sqlalchemy.ext.asyncio import AsyncSession
from teacher.service import TeacherAnalyticsService


async def _seed_acl_context(db: AsyncSession):
    owner = User(email="acl-owner@example.com", nickname="Owner")
    teacher = User(email="acl-teacher@example.com", nickname="Teacher")
    creator = User(email="acl-creator@example.com", nickname="Creator")
    other = User(email="acl-other@example.com", nickname="Other")
    db.add_all([owner, teacher, creator, other])
    await db.flush()

    space = Space(
        user_id=owner.id,
        name="ACL course",
        color="#123456",
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
            ),
            SpaceMember(
                space_id=space.id,
                user_id=teacher.id,
                role=SpaceMemberRole.TEACHER,
            ),
            SpaceMember(
                space_id=space.id,
                user_id=creator.id,
                role=SpaceMemberRole.MEMBER,
            ),
            SpaceMember(
                space_id=space.id,
                user_id=other.id,
                role=SpaceMemberRole.MEMBER,
            ),
        ]
    )
    await db.commit()
    return owner, teacher, creator, other, space


@pytest.mark.asyncio
async def test_private_note_creator_writes_teacher_reads_and_other_gets_404(
    db_session: AsyncSession,
):
    owner, teacher, creator, other, space = await _seed_acl_context(db_session)
    note = Note(
        space_id=space.id,
        title="private-note-secret",
        content="creator only",
        creator_user_id=creator.id,
        visibility="private",
    )
    shared = Note(
        space_id=space.id,
        title="shared-note",
        creator_user_id=creator.id,
    )
    db_session.add_all([note, shared])
    await db_session.commit()

    service = NoteService(db_session)
    assert (await service.get_note(creator.id, space.id, note.id)).id == note.id
    assert (await service.get_note(owner.id, space.id, note.id)).id == note.id
    assert (await service.get_note(teacher.id, space.id, note.id)).id == note.id

    with pytest.raises(NoteNotFoundError):
        await service.get_note(other.id, space.id, note.id)
    with pytest.raises(NoteNotFoundError):
        await service.update_note(
            teacher.id, space.id, note.id, NoteUpdate(title="must-not-change")
        )

    creator_rows = await service.list_notes(creator.id, space.id)
    teacher_rows = await service.list_notes(teacher.id, space.id)
    other_rows = await service.list_notes(other.id, space.id)
    assert {row.id for row in creator_rows} == {note.id, shared.id}
    assert {row.id for row in teacher_rows} == {note.id, shared.id}
    assert {row.id for row in other_rows} == {shared.id}


@pytest.mark.asyncio
async def test_private_quiz_hidden_from_teacher_and_other_standard_queries(
    db_session: AsyncSession,
):
    _, teacher, creator, other, space = await _seed_acl_context(db_session)
    private_quiz = Quiz(
        space_id=space.id,
        title="private-quiz-secret",
        topic="secret",
        total_questions=0,
        creator_user_id=creator.id,
        visibility="private",
    )
    shared_quiz = Quiz(
        space_id=space.id,
        title="shared-quiz",
        topic="shared",
        total_questions=0,
        creator_user_id=creator.id,
    )
    db_session.add_all([private_quiz, shared_quiz])
    await db_session.commit()

    service = QuizService(db_session)
    assert (
        await service.get_quiz_detail(creator.id, private_quiz.id)
    ).id == private_quiz.id
    for hidden_from in (teacher, other):
        with pytest.raises(QuizNotFoundError):
            await service.get_quiz_detail(hidden_from.id, private_quiz.id)

    creator_rows = await service.get_quizzes_by_space(creator.id, space.id)
    teacher_rows = await service.get_quizzes_by_space(teacher.id, space.id)
    other_rows = await service.get_quizzes_by_space(other.id, space.id)
    assert {row.id for row in creator_rows} == {private_quiz.id, shared_quiz.id}
    assert {row.id for row in teacher_rows} == {shared_quiz.id}
    assert {row.id for row in other_rows} == {shared_quiz.id}


@pytest.mark.asyncio
async def test_private_folders_counts_and_bulk_moves_do_not_bypass_acl(
    db_session: AsyncSession,
):
    _, teacher, creator, other, space = await _seed_acl_context(db_session)
    private_note_folder = Folder(
        space_id=space.id,
        content_type=FolderContentType.NOTES,
        name="private notes",
        creator_user_id=creator.id,
        visibility="private",
    )
    private_quiz_folder = Folder(
        space_id=space.id,
        content_type=FolderContentType.QUIZZES,
        name="private quizzes",
        creator_user_id=creator.id,
        visibility="private",
    )
    shared_note_target = Folder(
        space_id=space.id,
        content_type=FolderContentType.NOTES,
        name="shared notes",
        creator_user_id=creator.id,
    )
    shared_quiz_target = Folder(
        space_id=space.id,
        content_type=FolderContentType.QUIZZES,
        name="shared quizzes",
        creator_user_id=creator.id,
    )
    db_session.add_all(
        [
            private_note_folder,
            private_quiz_folder,
            shared_note_target,
            shared_quiz_target,
        ]
    )
    await db_session.flush()
    private_note = Note(
        space_id=space.id,
        folder_id=private_note_folder.id,
        title="private note",
        creator_user_id=creator.id,
        visibility="private",
    )
    private_quiz = Quiz(
        space_id=space.id,
        folder_id=private_quiz_folder.id,
        title="private quiz",
        topic="private",
        total_questions=0,
        creator_user_id=creator.id,
        visibility="private",
    )
    db_session.add_all([private_note, private_quiz])
    await db_session.commit()

    service = FolderService(db_session)
    creator_note_folders = await service.list_folders(
        creator.id, space.id, FolderContentType.NOTES
    )
    teacher_note_folders = await service.list_folders(
        teacher.id, space.id, FolderContentType.NOTES
    )
    other_note_folders = await service.list_folders(
        other.id, space.id, FolderContentType.NOTES
    )
    assert {row.id for row in creator_note_folders} == {
        private_note_folder.id,
        shared_note_target.id,
    }
    assert (
        next(
            row for row in teacher_note_folders if row.id == private_note_folder.id
        ).items_count
        == 1
    )
    assert {row.id for row in other_note_folders} == {shared_note_target.id}

    teacher_quiz_folders = await service.list_folders(
        teacher.id, space.id, FolderContentType.QUIZZES
    )
    assert {row.id for row in teacher_quiz_folders} == {shared_quiz_target.id}

    with pytest.raises(FolderNotFoundError):
        await service.move_notes(
            other.id,
            space.id,
            MoveItemsRequest(
                item_ids=[private_note.id], target_folder_id=shared_note_target.id
            ),
        )
    with pytest.raises(FolderNotFoundError):
        await service.move_quizzes(
            teacher.id,
            space.id,
            MoveItemsRequest(
                item_ids=[private_quiz.id], target_folder_id=shared_quiz_target.id
            ),
        )

    assert (
        await service.move_notes(
            creator.id,
            space.id,
            MoveItemsRequest(
                item_ids=[private_note.id], target_folder_id=shared_note_target.id
            ),
        )
        == 1
    )


@pytest.mark.asyncio
async def test_teacher_detail_keeps_private_quiz_aggregate_but_hides_details(
    db_session: AsyncSession,
):
    _, _, creator, _, space = await _seed_acl_context(db_session)
    now = datetime.now(timezone.utc)
    private_quiz = Quiz(
        space_id=space.id,
        title="private-quiz-title-secret",
        topic="private-topic-secret",
        total_questions=0,
        creator_user_id=creator.id,
        visibility="private",
    )
    shared_quiz = Quiz(
        space_id=space.id,
        title="shared-quiz-title",
        topic="shared",
        total_questions=0,
        creator_user_id=creator.id,
    )
    db_session.add_all([private_quiz, shared_quiz])
    await db_session.flush()
    for quiz in (private_quiz, shared_quiz):
        db_session.add(
            QuizAttempt(
                quiz_id=quiz.id,
                user_id=creator.id,
                status="completed",
                score=8,
                total_score=10,
                strengths=[
                    "private-feedback-secret" if quiz is private_quiz else "shared"
                ],
                weaknesses=[],
                suggestions=[],
                question_results=[],
                submitted_at=now,
            )
        )
    db_session.add_all(
        [
            StudyActivityLog(
                user_id=creator.id,
                space_id=space.id,
                title="private-quiz-activity-secret",
                summary="private-quiz-summary-secret",
                activity_type="测验",
                source="quiz",
                message_count=0,
                activity_date=now.date(),
                activity_time=now,
            ),
            StudyActivityLog(
                user_id=creator.id,
                space_id=space.id,
                title="conversation summary",
                summary="visible conversation summary",
                activity_type="学习新知识",
                source="conversation",
                message_count=1,
                activity_date=now.date(),
                activity_time=now,
            ),
        ]
    )
    await db_session.commit()

    service = TeacherAnalyticsService(db_session, space.id, 7)
    student_row = next(
        item
        for item in (
            await service.get_students(
                search=None, page=1, page_size=20, sort="last_active"
            )
        ).items
        if item.user_id == creator.id
    )
    assert student_row.quiz_attempt_count == 2

    detail = await service.get_student_detail(creator.id)
    assert detail is not None
    payload = detail.model_dump_json()
    assert "shared-quiz-title" in payload
    assert "visible conversation summary" in payload
    assert "private-quiz-title-secret" not in payload
    assert "private-feedback-secret" not in payload
    assert "private-quiz-summary-secret" not in payload


@pytest.mark.asyncio
async def test_leaderboard_excludes_private_notes_and_quizzes(
    db_session: AsyncSession,
):
    _, _, creator, other, space = await _seed_acl_context(db_session)
    shared_quiz = Quiz(
        space_id=space.id,
        title="shared leaderboard quiz",
        topic="shared",
        total_questions=0,
        creator_user_id=creator.id,
    )
    private_quiz = Quiz(
        space_id=space.id,
        title="private leaderboard quiz",
        topic="private",
        total_questions=0,
        creator_user_id=creator.id,
        visibility="private",
    )
    db_session.add_all([shared_quiz, private_quiz])
    await db_session.flush()
    for quiz in (shared_quiz, private_quiz):
        db_session.add(
            QuizAttempt(
                quiz_id=quiz.id,
                user_id=creator.id,
                status="completed",
                score=8,
                total_score=10,
                strengths=[],
                weaknesses=[],
                suggestions=[],
                question_results=[],
            )
        )
    db_session.add_all(
        [
            Note(
                space_id=space.id,
                title="shared leaderboard note",
                creator_user_id=creator.id,
            ),
            Note(
                space_id=space.id,
                title="private leaderboard note",
                creator_user_id=creator.id,
                visibility="private",
            ),
        ]
    )
    await db_session.commit()

    rows = await SpaceService(db_session).get_space_leaderboard(other.id, space.id)
    creator_row = next(row for row in rows if row["user_id"] == str(creator.id))
    assert creator_row["quiz_count"] == 1
    assert creator_row["notes_count"] == 1
