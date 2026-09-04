from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from assignments.schemas import (
    AnswerReviewItem,
    AssignmentGenerateRequest,
    AssignmentQuestionWrite,
    AssignmentUpdateRequest,
    SubmissionReviewRequest,
    UserAnswerItem,
)
from assignments.service import (
    AssignmentError,
    AssignmentService,
    utc_now,
    validate_question,
)
from db.models import (
    Assignment,
    AssignmentAnswer,
    AssignmentGradeAudit,
    AssignmentQuestion,
    AssignmentRecipient,
    AssignmentSubmission,
    Space,
    SpaceMember,
    SpaceMemberRole,
    User,
)


def _question(order=0):
    return AssignmentQuestionWrite(
        question_type="single_choice",
        question_stem="栈的特点是什么？",
        options=["先进先出", "后进先出"],
        correct_answer={"index": 1},
        max_score=4,
        order_index=order,
        grader_type="rule",
    )


def test_question_validation_rejects_out_of_range_answer_and_accepts_valid_oj():
    invalid = _question()
    invalid.correct_answer = {"index": 4}
    with pytest.raises(AssignmentError) as exc_info:
        validate_question(invalid)
    assert exc_info.value.code == "INVALID_CORRECT_ANSWER"

    oj = AssignmentQuestionWrite(
        question_type="code",
        question_stem="实现栈",
        correct_answer={
            "reference_solution": {"language": "python3", "source": "print(input())"},
            "explanation": "读取并输出",
        },
        max_score=10,
        order_index=0,
        grader_type="oj",
        public_config={
            "allowed_languages": ["python3", "cpp20"],
            "default_language": "python3",
            "samples": [{"input": "1\n", "output": "1\n"}],
        },
    )
    validated = validate_question(oj)
    assert validated["grader_type"] == "oj"
    assert validated["public_config"]["allowed_languages"] == ["python3", "cpp20"]


@pytest.fixture
async def assignment_context(db_session):
    teacher = User(id=uuid4(), email="teacher@example.com", nickname="老师", password_hash="x")
    student_a = User(id=uuid4(), email="a@example.com", nickname="甲", password_hash="x")
    student_b = User(id=uuid4(), email="b@example.com", nickname="乙", password_hash="x")
    excluded_teacher = User(id=uuid4(), email="other@example.com", nickname="其他老师", password_hash="x")
    db_session.add_all([teacher, student_a, student_b, excluded_teacher])
    await db_session.flush()
    space = Space(
        id=uuid4(), user_id=teacher.id, name="操作系统", color="#123456", is_collaborative=True
    )
    db_session.add(space)
    await db_session.flush()
    db_session.add_all([
        SpaceMember(space_id=space.id, user_id=teacher.id, role=SpaceMemberRole.TEACHER, color="#111111"),
        SpaceMember(space_id=space.id, user_id=student_a.id, role=SpaceMemberRole.MEMBER, color="#222222"),
        SpaceMember(space_id=space.id, user_id=student_b.id, role=SpaceMemberRole.MEMBER, color="#333333"),
        SpaceMember(space_id=space.id, user_id=excluded_teacher.id, role=SpaceMemberRole.TEACHER, color="#444444"),
    ])
    assignment = Assignment(
        space_id=space.id, teacher_user_id=teacher.id, title="第一次作业",
        instructions="完成选择题", difficulty="medium", status="draft",
        due_at=utc_now() + timedelta(days=2), total_questions=1, total_score=4,
    )
    db_session.add(assignment)
    await db_session.flush()
    db_session.add(AssignmentQuestion(
        assignment_id=assignment.id, question_type="single_choice",
        question_stem="栈的特点是什么？", options=["先进先出", "后进先出"],
        correct_answer={"index": 1}, rubric=None, max_score=4,
        order_index=0, grader_type="rule", grader_config={"private": True},
    ))
    await db_session.flush()
    return teacher, student_a, student_b, excluded_teacher, space, assignment


def _generation_request() -> AssignmentGenerateRequest:
    return AssignmentGenerateRequest(
        title="进程调度练习",
        instructions="覆盖常见调度算法",
        difficulty="medium",
        due_at=utc_now() + timedelta(days=1),
        question_configs=[
            {"question_type": "single_choice", "count": 1, "score": 5},
        ],
    )


@pytest.mark.asyncio
async def test_generation_job_snapshots_target_space_name(db_session, assignment_context):
    teacher, _, _, _, space, _ = assignment_context

    job = await AssignmentService(db_session).create_generation_job(
        space.id, teacher.id, _generation_request()
    )

    assert job.input_data["space_name"] == "操作系统"
    generated_assignment = await db_session.get(Assignment, job.assignment_id)
    assert generated_assignment is not None
    assert generated_assignment.space_id == space.id

    space.name = "操作系统（新名称）"
    await db_session.commit()
    persisted_job = await db_session.get(type(job), job.id)
    assert persisted_job.input_data["space_name"] == "操作系统"


@pytest.mark.asyncio
async def test_generation_job_rejects_missing_space_with_existing_error_semantics(
    db_session, assignment_context
):
    teacher, _, _, _, _, _ = assignment_context

    with pytest.raises(AssignmentError) as exc_info:
        await AssignmentService(db_session).create_generation_job(
            uuid4(), teacher.id, _generation_request()
        )

    assert exc_info.value.code == "SPACE_NOT_FOUND"
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_teacher_can_delete_draft_assignment_and_cascade_questions(db_session, assignment_context):
    teacher, _, _, _, _, assignment = assignment_context

    await AssignmentService(db_session).delete_assignment(assignment.id, teacher.id)

    assert await db_session.get(Assignment, assignment.id) is None
    assert not (await db_session.execute(
        select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment.id)
    )).scalars().all()


@pytest.mark.asyncio
async def test_teacher_cannot_delete_published_or_closed_assignment(db_session, assignment_context):
    teacher, _, _, _, _, assignment = assignment_context
    service = AssignmentService(db_session)

    await service.publish(assignment.id, teacher.id)
    with pytest.raises(AssignmentError) as published_error:
        await service.delete_assignment(assignment.id, teacher.id)
    assert published_error.value.code == "ASSIGNMENT_DELETE_LOCKED"

    await service.close(assignment.id, teacher.id)
    with pytest.raises(AssignmentError) as closed_error:
        await service.delete_assignment(assignment.id, teacher.id)
    assert closed_error.value.code == "ASSIGNMENT_DELETE_LOCKED"


@pytest.mark.asyncio
async def test_publish_snapshots_members_only(db_session, assignment_context):
    teacher, student_a, student_b, excluded_teacher, _, assignment = assignment_context
    result = await AssignmentService(db_session).publish(assignment.id, teacher.id)
    assert result["status"] == "published"
    recipient_ids = set((await db_session.execute(
        select(AssignmentRecipient.user_id).where(AssignmentRecipient.assignment_id == assignment.id)
    )).scalars().all())
    assert recipient_ids == {student_a.id, student_b.id}
    assert excluded_teacher.id not in recipient_ids


@pytest.mark.asyncio
async def test_student_detail_hides_private_answers_until_close(db_session, assignment_context):
    teacher, student, _, _, _, assignment = assignment_context
    await AssignmentService(db_session).publish(assignment.id, teacher.id)
    before = await AssignmentService(db_session).get_student_detail(student.id, assignment.id)
    assert before["answers_revealed"] is False
    assert before["questions"][0]["correct_answer"] is None
    assert before["questions"][0]["rubric"] is None
    assert "grader_config" not in before["questions"][0]

    await AssignmentService(db_session).close(assignment.id, teacher.id)
    after = await AssignmentService(db_session).get_student_detail(student.id, assignment.id)
    assert after["answers_revealed"] is True
    assert after["questions"][0]["correct_answer"] == {"index": 1}


@pytest.mark.asyncio
async def test_draft_then_single_submit_locks_attempt(db_session, assignment_context):
    teacher, student, _, _, _, assignment = assignment_context
    await AssignmentService(db_session).publish(assignment.id, teacher.id)
    question_id = await db_session.scalar(select(AssignmentQuestion.id).where(
        AssignmentQuestion.assignment_id == assignment.id
    ))
    answer = UserAnswerItem(question_id=question_id, answer={"index": 1})
    service = AssignmentService(db_session)
    draft = await service.save_draft(student.id, assignment.id, [answer], 0)
    assert draft.status == "in_progress"
    submission, job = await service.submit(student.id, assignment.id, [answer])
    assert submission.status == "pending"
    assert job.job_type == "grading"
    with pytest.raises(AssignmentError) as exc_info:
        await service.submit(student.id, assignment.id, [answer])
    assert exc_info.value.code == "ALREADY_SUBMITTED"


@pytest.mark.asyncio
async def test_student_cannot_access_assignment_without_recipient_snapshot(db_session, assignment_context):
    teacher, _, _, excluded_teacher, _, assignment = assignment_context
    await AssignmentService(db_session).publish(assignment.id, teacher.id)
    with pytest.raises(AssignmentError) as exc_info:
        await AssignmentService(db_session).get_student_detail(excluded_teacher.id, assignment.id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_deadline_blocks_draft_and_submission(db_session, assignment_context):
    teacher, student, _, _, _, assignment = assignment_context
    await AssignmentService(db_session).publish(assignment.id, teacher.id)
    question_id = await db_session.scalar(select(AssignmentQuestion.id).where(
        AssignmentQuestion.assignment_id == assignment.id
    ))
    assignment.due_at = utc_now() - timedelta(seconds=1)
    await db_session.flush()
    answer = UserAnswerItem(question_id=question_id, answer={"index": 1})

    with pytest.raises(AssignmentError) as draft_error:
        await AssignmentService(db_session).save_draft(student.id, assignment.id, [answer], 0)
    assert draft_error.value.code == "ASSIGNMENT_CLOSED"

    with pytest.raises(AssignmentError) as submit_error:
        await AssignmentService(db_session).submit(student.id, assignment.id, [answer])
    assert submit_error.value.code == "ASSIGNMENT_CLOSED"


@pytest.mark.asyncio
async def test_published_assignment_allows_metadata_extension_but_locks_questions(
    db_session, assignment_context
):
    teacher, _, _, _, _, assignment = assignment_context
    published = await AssignmentService(db_session).publish(assignment.id, teacher.id)
    extended_due = assignment.due_at + timedelta(days=1)
    updated = await AssignmentService(db_session).update_assignment(
        assignment.id,
        teacher.id,
        AssignmentUpdateRequest(
            version=published["version"],
            title="第一次作业（修订说明）",
            instructions="题目不变，截止时间延长一天",
            due_at=extended_due,
        ),
    )
    assert updated["title"] == "第一次作业（修订说明）"
    assert updated["due_at"] == extended_due

    with pytest.raises(AssignmentError) as exc_info:
        await AssignmentService(db_session).update_assignment(
            assignment.id,
            teacher.id,
            AssignmentUpdateRequest(version=updated["version"], questions=[_question()]),
        )
    assert exc_info.value.code == "QUESTIONS_LOCKED"


@pytest.mark.asyncio
async def test_ordinary_draft_upsert_preserves_oj_private_link(db_session, assignment_context):
    teacher, _, _, _, _, assignment = assignment_context
    question = await db_session.scalar(select(AssignmentQuestion).where(
        AssignmentQuestion.assignment_id == assignment.id
    ))
    question.question_type = "code"
    question.question_stem = "输出输入值"
    question.options = None
    question.correct_answer = {
        "reference_solution": {"language": "python3", "source": "print(input())"},
        "explanation": "读取后输出",
    }
    question.grader_type = "oj"
    question.public_config = {
        "allowed_languages": ["python3"], "default_language": "python3",
        "starter_code": {}, "input_description": "整数", "output_description": "整数",
        "samples": [{"input": "1\n", "output": "1\n"}], "time_limit_ms": 2000,
        "memory_limit_mb": 256, "output_limit_kb": 64, "compare_mode": "standard",
        "float_absolute_tolerance": 1e-6, "float_relative_tolerance": 1e-6,
    }
    question.grader_config = {
        "problem_draft_id": "draft-1", "checksum": "abc",
        "problem_version_id": "version-1", "validated_checksum": "abc",
    }
    await db_session.flush()

    updated = await AssignmentService(db_session).update_assignment(
        assignment.id,
        teacher.id,
        AssignmentUpdateRequest(
            version=assignment.version,
            questions=[AssignmentQuestionWrite(
                id=question.id, question_type="code", question_stem="输出输入值（更新）",
                correct_answer=question.correct_answer, max_score=10, order_index=0,
                grader_type="oj", public_config=question.public_config,
            )],
        ),
    )
    assert updated["questions"][0]["id"] == question.id
    assert updated["questions"][0]["grader_config"]["problem_draft_id"] == "draft-1"


@pytest.mark.asyncio
async def test_oj_publish_requires_current_validation_and_student_never_gets_private_link(
    db_session, assignment_context, monkeypatch
):
    monkeypatch.setattr("config.get_settings", lambda: SimpleNamespace(oj_enabled=True))
    teacher, student, _, _, _, assignment = assignment_context
    question = await db_session.scalar(select(AssignmentQuestion).where(
        AssignmentQuestion.assignment_id == assignment.id
    ))
    question.question_type = "code"
    question.question_stem = "输出输入值"
    question.options = None
    question.correct_answer = {
        "reference_solution": {"language": "python3", "source": "print(input())"},
        "explanation": "读取后输出",
    }
    question.grader_type = "oj"
    question.public_config = {
        "allowed_languages": ["python3"], "default_language": "python3",
        "starter_code": {}, "input_description": "整数", "output_description": "整数",
        "samples": [{"input": "1\n", "output": "1\n"}], "time_limit_ms": 2000,
        "memory_limit_mb": 256, "output_limit_kb": 64, "compare_mode": "standard",
        "float_absolute_tolerance": 1e-6, "float_relative_tolerance": 1e-6,
    }
    question.grader_config = {
        "problem_draft_id": "private-draft", "checksum": "new",
        "problem_version_id": "old-version", "validated_checksum": "old",
    }
    await db_session.flush()
    with pytest.raises(AssignmentError) as exc_info:
        await AssignmentService(db_session).publish(assignment.id, teacher.id)
    assert exc_info.value.code == "OJ_NOT_VALIDATED"

    question.grader_config = {
        **question.grader_config,
        "problem_version_id": "version-2", "validated_checksum": "new",
    }
    await db_session.flush()
    await AssignmentService(db_session).publish(assignment.id, teacher.id)
    detail = await AssignmentService(db_session).get_student_detail(student.id, assignment.id)
    student_question = detail["questions"][0]
    assert student_question["public_config"]["samples"][0]["input"] == "1\n"
    assert student_question["correct_answer"] is None
    assert "grader_config" not in student_question
    assert "private-draft" not in str(student_question)

    monkeypatch.setattr("config.get_settings", lambda: SimpleNamespace(oj_enabled=False))
    with pytest.raises(AssignmentError) as disabled_error:
        await AssignmentService(db_session).submit(
            student.id,
            assignment.id,
            [
                UserAnswerItem(
                    question_id=question.id,
                    answer={"language": "python3", "source": "print(input())"},
                )
            ],
        )
    assert disabled_error.value.code == "OJ_DISABLED"


@pytest.mark.asyncio
async def test_teacher_review_preserves_ai_score_and_writes_audit(
    db_session, assignment_context, monkeypatch
):
    teacher, student, _, _, _, assignment = assignment_context
    await AssignmentService(db_session).publish(assignment.id, teacher.id)
    question = await db_session.scalar(select(AssignmentQuestion).where(
        AssignmentQuestion.assignment_id == assignment.id
    ))
    submission = AssignmentSubmission(
        assignment_id=assignment.id,
        user_id=student.id,
        status="completed",
        answers_raw={str(question.id): {"index": 1}},
        provisional_score=4,
        submitted_at=utc_now(),
    )
    db_session.add(submission)
    await db_session.flush()
    graded_answer = AssignmentAnswer(
        submission_id=submission.id,
        question_id=question.id,
        user_answer={"index": 1},
        auto_score=4,
        status="correct",
    )
    db_session.add(graded_answer)
    await db_session.flush()

    async def ignore_notification(*args, **kwargs):
        return None

    import notifications.queue as notification_queue
    from notifications.service import NotificationService

    monkeypatch.setattr(NotificationService, "create_and_push", staticmethod(ignore_notification))
    monkeypatch.setattr(notification_queue, "push_notification", ignore_notification)

    result = await AssignmentService(db_session).review_submission(
        submission.id,
        teacher.id,
        SubmissionReviewRequest(
            answers=[AnswerReviewItem(answer_id=graded_answer.id, score=3, comment="步骤不完整")],
            teacher_feedback="请补充复杂度分析",
            confirm_remaining=True,
        ),
    )

    assert result["provisional_score"] == pytest.approx(4)
    assert result["final_score"] == pytest.approx(3)
    assert result["submission_status"] == "reviewed"
    assert result["teacher_feedback"] == "请补充复杂度分析"
    audit = await db_session.scalar(select(AssignmentGradeAudit).where(
        AssignmentGradeAudit.submission_id == submission.id
    ))
    assert audit.previous_score == pytest.approx(4)
    assert audit.new_score == pytest.approx(3)
