"""Business rules and serialization for teacher assignments."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from assignments.oj import OjClient, OjManagerError, sanitize_run_result
from assignments.schemas import (
    AssignmentGenerateRequest,
    AssignmentQuestionWrite,
    AssignmentUpdateRequest,
    OjCodeAnswer,
    OjProblemWriteRequest,
    OjSampleRunRequest,
)
from db.models import (
    Assignment,
    AssignmentAnswer,
    AssignmentGradeAudit,
    AssignmentJob,
    AssignmentOjRun,
    AssignmentQuestion,
    AssignmentRecipient,
    AssignmentSubmission,
    SpaceMember,
    SpaceMemberRole,
    User,
)


class AssignmentError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _answer_map(items: list[Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        key = str(item.question_id)
        if key in result:
            raise AssignmentError("DUPLICATE_ANSWER", "同一道题不能提交多个答案", 422)
        result[key] = item.answer
    return result


def validate_question(question: AssignmentQuestionWrite | dict[str, Any]) -> dict[str, Any]:
    raw = question.model_dump() if isinstance(question, AssignmentQuestionWrite) else dict(question)
    fields = {
        "id", "question_type", "question_stem", "options", "correct_answer",
        "rubric", "max_score", "order_index", "grader_type", "public_config", "grader_config",
    }
    data = {key: raw.get(key) for key in fields if key in raw}
    qtype = data.get("question_type")
    grader = data.get("grader_type") or ("ai" if qtype == "short_answer" else "rule")
    data["grader_type"] = grader
    if qtype not in {"single_choice", "multiple_choice", "true_false", "short_answer", "code"}:
        raise AssignmentError("INVALID_QUESTION_TYPE", "不支持的题型", 422)
    options = data.get("options")
    correct = data.get("correct_answer") or {}
    if qtype in {"single_choice", "multiple_choice"}:
        if not isinstance(options, list) or len(options) < 2 or any(not str(x).strip() for x in options):
            raise AssignmentError("INVALID_OPTIONS", "选择题至少需要两个非空选项", 422)
        indices = [correct.get("index")] if qtype == "single_choice" else correct.get("indices")
        if not isinstance(indices, list) or not indices or any(
            not isinstance(index, int) or index < 0 or index >= len(options) for index in indices
        ):
            raise AssignmentError("INVALID_CORRECT_ANSWER", "选择题答案索引无效", 422)
        if qtype == "multiple_choice" and len(set(indices)) != len(indices):
            raise AssignmentError("INVALID_CORRECT_ANSWER", "多选题答案索引不能重复", 422)
        if grader != "rule":
            raise AssignmentError("INVALID_GRADER", "客观题必须使用规则评分", 422)
    elif qtype == "true_false":
        if not isinstance(correct.get("value"), bool) or grader != "rule":
            raise AssignmentError("INVALID_CORRECT_ANSWER", "判断题需要布尔答案并使用规则评分", 422)
        data["options"] = None
    elif qtype == "short_answer":
        reference = correct.get("reference") or correct.get("text")
        if not isinstance(reference, str) or not reference.strip():
            raise AssignmentError("INVALID_REFERENCE_ANSWER", "简答题必须提供参考答案", 422)
        if not data.get("rubric") or grader != "ai":
            raise AssignmentError("INVALID_RUBRIC", "简答题必须提供评分标准并使用 AI 评分", 422)
        data["options"] = None
    else:
        if grader != "oj":
            raise AssignmentError("INVALID_GRADER", "编程题必须使用 OJ 评分", 422)
        try:
            from assignments.schemas import OjPublicConfig

            config = OjPublicConfig.model_validate(data.get("public_config") or {})
        except ValueError as exc:
            raise AssignmentError("INVALID_OJ_CONFIG", "编程题公开配置无效", 422) from exc
        data["public_config"] = config.model_dump(mode="json")
        reference = correct.get("reference_solution")
        try:
            public_solution = OjCodeAnswer.model_validate(reference)
        except ValueError as exc:
            raise AssignmentError(
                "INVALID_REFERENCE_SOLUTION", "编程题必须提供可公开的参考代码", 422
            ) from exc
        if public_solution.language not in config.allowed_languages:
            raise AssignmentError(
                "INVALID_REFERENCE_SOLUTION", "参考代码语言必须属于允许语言", 422
            )
        data["correct_answer"] = {
            "reference_solution": public_solution.model_dump(mode="json"),
            "explanation": str(correct.get("explanation") or "")[:20000],
        }
        data["options"] = None
    if float(data.get("max_score", 0)) <= 0:
        raise AssignmentError("INVALID_SCORE", "题目分值必须大于 0", 422)
    return data


def validate_question_set(questions: list[AssignmentQuestionWrite | dict[str, Any]]) -> list[dict[str, Any]]:
    if not questions:
        raise AssignmentError("QUESTIONS_REQUIRED", "作业至少需要一道题", 422)
    validated = [validate_question(question) for question in questions]
    orders = [item["order_index"] for item in validated]
    if len(orders) != len(set(orders)):
        raise AssignmentError("DUPLICATE_QUESTION_ORDER", "题目顺序不能重复", 422)
    return sorted(validated, key=lambda item: item["order_index"])


def effective_due_at(assignment: Assignment, recipient: AssignmentRecipient) -> datetime:
    return recipient.due_at_override or assignment.due_at


def answers_revealed(assignment: Assignment, due_at: datetime, now: datetime | None = None) -> bool:
    now = now or utc_now()
    return assignment.status == "closed" or as_utc(now) >= as_utc(due_at)


class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_generation_job(
        self, space_id: UUID, teacher_id: UUID, request: AssignmentGenerateRequest
    ) -> AssignmentJob:
        if any(item.question_type == "code" and item.count for item in request.question_configs):
            from config import get_settings

            if not get_settings().oj_enabled:
                raise AssignmentError("OJ_DISABLED", "OJ 功能尚未启用", 503)
        if as_utc(request.due_at) <= utc_now():
            raise AssignmentError("INVALID_DUE_AT", "截止时间必须晚于当前时间", 422)
        assignment = Assignment(
            space_id=space_id,
            teacher_user_id=teacher_id,
            title=request.title.strip(),
            instructions=request.instructions.strip(),
            difficulty=request.difficulty,
            status="draft",
            due_at=request.due_at,
        )
        self.db.add(assignment)
        await self.db.flush()
        job = AssignmentJob(
            assignment_id=assignment.id,
            requested_by_user_id=teacher_id,
            job_type="generation",
            status="pending",
            input_data={
                "title": request.title,
                "instructions": request.instructions,
                "difficulty": request.difficulty,
                "question_configs": [item.model_dump() for item in request.question_configs],
            },
        )
        self.db.add(job)
        await self.db.commit()
        return job

    async def get_job(self, job_id: UUID, teacher_id: UUID) -> AssignmentJob:
        job = await self.db.get(AssignmentJob, job_id)
        if job is None or job.requested_by_user_id != teacher_id:
            raise AssignmentError("JOB_NOT_FOUND", "任务不存在", 404)
        return job

    async def get_teacher_assignment(self, assignment_id: UUID, teacher_id: UUID) -> Assignment:
        assignment = await self.db.get(Assignment, assignment_id)
        if assignment is None or assignment.teacher_user_id != teacher_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return assignment

    async def list_teacher_assignments(self, space_id: UUID, teacher_id: UUID) -> list[dict[str, Any]]:
        assignments = (await self.db.execute(
            select(Assignment).where(
                Assignment.space_id == space_id, Assignment.teacher_user_id == teacher_id
            ).order_by(Assignment.created_at.desc())
        )).scalars().all()
        return [await self.serialize_teacher_assignment(item) for item in assignments]

    async def serialize_teacher_assignment(self, assignment: Assignment) -> dict[str, Any]:
        # updated_at is an on-update SQL expression and SQLAlchemy expires it
        # after flush; refresh explicitly to avoid implicit async lazy I/O.
        await self.db.refresh(assignment)
        questions = (await self.db.execute(
            select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment.id)
            .order_by(AssignmentQuestion.order_index)
        )).scalars().all()
        generation_progress = None
        if assignment.status == "draft":
            latest_job = await self.db.scalar(
                select(AssignmentJob)
                .where(
                    AssignmentJob.assignment_id == assignment.id,
                    AssignmentJob.job_type == "generation",
                )
                .order_by(AssignmentJob.created_at.desc())
                .limit(1)
            )
            if latest_job is not None:
                generation_progress = {
                    "job_id": latest_job.id,
                    "status": latest_job.status,
                    "output_data": latest_job.output_data or {},
                    "error_message": latest_job.error_message,
                }
        return {
            "id": assignment.id, "space_id": assignment.space_id,
            "teacher_user_id": assignment.teacher_user_id, "title": assignment.title,
            "instructions": assignment.instructions, "difficulty": assignment.difficulty,
            "status": assignment.status, "due_at": assignment.due_at, "version": assignment.version,
            "total_questions": assignment.total_questions, "total_score": assignment.total_score,
            "published_at": assignment.published_at, "closed_at": assignment.closed_at,
            "created_at": assignment.created_at, "updated_at": assignment.updated_at,
            "generation_progress": generation_progress,
            "questions": [
                {"id": q.id, "question_type": q.question_type, "question_stem": q.question_stem,
                 "options": q.options, "correct_answer": q.correct_answer, "rubric": q.rubric,
                 "max_score": q.max_score, "order_index": q.order_index,
                 "grader_type": q.grader_type, "public_config": q.public_config,
                 "grader_config": q.grader_config}
                for q in questions
            ],
        }

    async def update_assignment(
        self, assignment_id: UUID, teacher_id: UUID, request: AssignmentUpdateRequest
    ) -> dict[str, Any]:
        assignment = await self.db.scalar(select(Assignment).where(
            Assignment.id == assignment_id, Assignment.teacher_user_id == teacher_id
        ).with_for_update().execution_options(populate_existing=True))
        if assignment is None:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        if assignment.version != request.version:
            raise AssignmentError("VERSION_CONFLICT", "作业已被其他操作更新，请刷新后重试", 409)
        if request.due_at is not None:
            if as_utc(request.due_at) <= utc_now():
                raise AssignmentError("INVALID_DUE_AT", "截止时间必须晚于当前时间", 422)
            if assignment.status != "draft" and as_utc(request.due_at) < as_utc(assignment.due_at):
                raise AssignmentError("DUE_AT_CANNOT_SHRINK", "发布后只能延长截止时间", 409)
            assignment.due_at = request.due_at
        if request.title is not None:
            assignment.title = request.title.strip()
        if request.instructions is not None:
            assignment.instructions = request.instructions.strip()
        if request.difficulty is not None:
            assignment.difficulty = request.difficulty
        if request.questions is not None:
            if assignment.status != "draft":
                raise AssignmentError("QUESTIONS_LOCKED", "发布后不能修改题目、答案或分值", 409)
            questions = validate_question_set(request.questions)
            existing = (await self.db.execute(select(AssignmentQuestion).where(
                AssignmentQuestion.assignment_id == assignment.id
            ))).scalars().all()
            by_id = {item.id: item for item in existing}
            requested_ids = {item["id"] for item in questions if item.get("id") is not None}
            if any(item_id not in by_id for item_id in requested_ids):
                raise AssignmentError("INVALID_QUESTION_ID", "题目 ID 不属于当前作业", 422)
            # Move current rows out of the unique order range before swaps.
            for index, current in enumerate(existing):
                current.order_index = -index - 1
            await self.db.flush()
            for current in existing:
                if current.id not in requested_ids:
                    await self.db.delete(current)
            writable = {
                "question_type", "question_stem", "options", "correct_answer", "rubric",
                "max_score", "order_index", "grader_type", "public_config", "grader_config",
            }
            for item in questions:
                item_id = item.pop("id", None)
                values = {key: value for key, value in item.items() if key in writable}
                if item_id is None:
                    if values.get("question_type") == "code":
                        values["grader_config"] = None
                    self.db.add(AssignmentQuestion(assignment_id=assignment.id, **values))
                else:
                    current = by_id[item_id]
                    if values.get("question_type") == "code" and current.question_type == "code":
                        # OJ draft/version linkage is managed only by the
                        # private OJ endpoints and survives ordinary saves.
                        values.pop("grader_config", None)
                        values.pop("public_config", None)
                        values["correct_answer"] = {
                            **(values.get("correct_answer") or {}),
                            "reference_solution": (current.correct_answer or {}).get(
                                "reference_solution"
                            ),
                        }
                    elif values.get("question_type") != current.question_type:
                        values["grader_config"] = None
                    for key, value in values.items():
                        setattr(current, key, value)
            assignment.total_questions = len(questions)
            assignment.total_score = sum(float(item["max_score"]) for item in questions)
        assignment.version += 1
        assignment.updated_at = utc_now()
        await self.db.flush()
        return await self.serialize_teacher_assignment(assignment)

    async def delete_assignment(self, assignment_id: UUID, teacher_id: UUID) -> None:
        """Delete a draft assignment and its dependent authoring records.

        Published and closed assignments are intentionally immutable from a
        lifecycle perspective so student records and grade history remain
        available for review.
        """
        assignment = await self.db.scalar(select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.teacher_user_id == teacher_id,
        ).with_for_update())
        if assignment is None:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        if assignment.status != "draft":
            raise AssignmentError(
                "ASSIGNMENT_DELETE_LOCKED",
                "已发布或已关闭的作业不能删除",
                409,
            )
        await self.db.delete(assignment)
        await self.db.commit()

    async def publish(self, assignment_id: UUID, teacher_id: UUID) -> dict[str, Any]:
        assignment = await self.db.scalar(select(Assignment).where(
            Assignment.id == assignment_id, Assignment.teacher_user_id == teacher_id
        ).with_for_update().execution_options(populate_existing=True))
        if assignment is None:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        if assignment.status != "draft":
            raise AssignmentError("ASSIGNMENT_ALREADY_PUBLISHED", "作业已经发布或关闭", 409)
        if as_utc(assignment.due_at) <= utc_now():
            raise AssignmentError("INVALID_DUE_AT", "截止时间必须晚于当前时间", 422)
        questions = (await self.db.execute(
            select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment.id)
        )).scalars().all()
        if len(questions) != int(assignment.total_questions or 0):
            raise AssignmentError(
                "QUESTIONS_INCOMPLETE", "仍有题目生成失败，请先重试失败题目后再发布", 422
            )
        if any(question.question_type == "code" for question in questions):
            from config import get_settings

            if not get_settings().oj_enabled:
                raise AssignmentError("OJ_DISABLED", "OJ 功能尚未启用", 503)
        validated = validate_question_set([
            {"id": q.id, "question_type": q.question_type, "question_stem": q.question_stem,
             "options": q.options, "correct_answer": q.correct_answer, "rubric": q.rubric,
             "max_score": q.max_score, "order_index": q.order_index,
             "grader_type": q.grader_type, "public_config": q.public_config,
             "grader_config": q.grader_config}
            for q in questions
        ])
        for question in questions:
            if question.question_type == "code":
                config = question.grader_config or {}
                if (
                    not config.get("problem_version_id")
                    or not config.get("checksum")
                    or config.get("validated_checksum") != config.get("checksum")
                ):
                    raise AssignmentError(
                        "OJ_NOT_VALIDATED", "编程题必须在当前版本验证通过后才能发布", 422
                    )
        member_ids = (await self.db.execute(
            select(SpaceMember.user_id).where(
                SpaceMember.space_id == assignment.space_id,
                SpaceMember.role == SpaceMemberRole.MEMBER,
            )
        )).scalars().all()
        if not member_ids:
            raise AssignmentError("NO_STUDENTS", "课程中没有可布置作业的学生", 422)
        for user_id in member_ids:
            self.db.add(AssignmentRecipient(assignment_id=assignment.id, user_id=user_id))
        assignment.status = "published"
        assignment.published_at = utc_now()
        assignment.version += 1
        assignment.total_questions = len(validated)
        assignment.total_score = sum(float(item["max_score"]) for item in validated)
        await self.db.flush()
        return await self.serialize_teacher_assignment(assignment)

    async def close(self, assignment_id: UUID, teacher_id: UUID) -> dict[str, Any]:
        assignment = await self.db.scalar(select(Assignment).where(
            Assignment.id == assignment_id, Assignment.teacher_user_id == teacher_id
        ).with_for_update().execution_options(populate_existing=True))
        if assignment is None:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        if assignment.status != "published":
            raise AssignmentError("ASSIGNMENT_NOT_OPEN", "只有已发布作业可以提前关闭", 409)
        assignment.status = "closed"
        assignment.closed_at = utc_now()
        assignment.version += 1
        await self.db.flush()
        return await self.serialize_teacher_assignment(assignment)

    async def _recipient_assignment(
        self, user_id: UUID, assignment_id: UUID
    ) -> tuple[Assignment, AssignmentRecipient]:
        row = (await self.db.execute(
            select(Assignment, AssignmentRecipient)
            .join(AssignmentRecipient, AssignmentRecipient.assignment_id == Assignment.id)
            .where(Assignment.id == assignment_id, AssignmentRecipient.user_id == user_id)
        )).first()
        if row is None:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在或未布置给你", 404)
        return row[0], row[1]

    async def list_student_assignments(self, user_id: UUID, space_id: UUID) -> list[dict[str, Any]]:
        rows = (await self.db.execute(
            select(Assignment, AssignmentRecipient, AssignmentSubmission)
            .join(AssignmentRecipient, AssignmentRecipient.assignment_id == Assignment.id)
            .outerjoin(
                AssignmentSubmission,
                (AssignmentSubmission.assignment_id == Assignment.id) & (AssignmentSubmission.user_id == user_id),
            )
            .where(
                Assignment.space_id == space_id,
                AssignmentRecipient.user_id == user_id,
                Assignment.status.in_(["published", "closed"]),
            )
            .order_by(Assignment.due_at.asc())
        )).all()
        items = []
        for assignment, recipient, submission in rows:
            due = effective_due_at(assignment, recipient)
            status = submission.status if submission else ("missed" if answers_revealed(assignment, due) else None)
            raw = submission.answers_raw if submission else {}
            items.append({
                "id": assignment.id, "item_kind": "assignment", "space_id": assignment.space_id,
                "title": assignment.title, "instructions": assignment.instructions,
                "difficulty": assignment.difficulty, "assignment_status": assignment.status,
                "submission_status": status, "due_at": assignment.due_at, "effective_due_at": due,
                "total_questions": assignment.total_questions, "total_score": assignment.total_score,
                "draft_answer_count": len([v for v in raw.values() if v not in (None, "", [], {})]) if submission and submission.status == "in_progress" else None,
                "provisional_score": submission.provisional_score if submission else None,
                "final_score": submission.final_score if submission else None,
                "answers_revealed": answers_revealed(assignment, due),
                "created_at": assignment.created_at, "published_at": assignment.published_at,
            })
        return items

    async def get_student_detail(self, user_id: UUID, assignment_id: UUID) -> dict[str, Any]:
        assignment, recipient = await self._recipient_assignment(user_id, assignment_id)
        if assignment.status not in {"published", "closed"}:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业尚未发布", 404)
        submission = await self.db.scalar(select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id, AssignmentSubmission.user_id == user_id
        ))
        questions = (await self.db.execute(
            select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment.id)
            .order_by(AssignmentQuestion.order_index)
        )).scalars().all()
        due = effective_due_at(assignment, recipient)
        reveal = answers_revealed(assignment, due)
        return {
            "id": assignment.id, "item_kind": "assignment", "space_id": assignment.space_id,
            "title": assignment.title, "instructions": assignment.instructions,
            "difficulty": assignment.difficulty, "assignment_status": assignment.status,
            "submission_status": submission.status if submission else ("missed" if reveal else None),
            "due_at": assignment.due_at, "effective_due_at": due,
            "total_questions": assignment.total_questions, "total_score": assignment.total_score,
            "provisional_score": submission.provisional_score if submission else None,
            "final_score": submission.final_score if submission else None, "answers_revealed": reveal,
            "questions": [self._student_question(q, reveal) for q in questions],
            "draft_answers": [
                {"question_id": UUID(key), "answer": value}
                for key, value in (submission.answers_raw or {}).items()
            ] if submission and submission.status == "in_progress" else [],
            "current_question_index": submission.current_question_index if submission and submission.status == "in_progress" else 0,
            "draft_updated_at": submission.draft_updated_at if submission and submission.status == "in_progress" else None,
        }

    @staticmethod
    def _student_question(question: AssignmentQuestion, reveal: bool) -> dict[str, Any]:
        return {
            "id": question.id, "question_type": question.question_type,
            "question_stem": question.question_stem, "options": question.options,
            "max_score": question.max_score, "order_index": question.order_index,
            "grader_type": question.grader_type,
            "public_config": question.public_config if question.question_type == "code" else None,
            "correct_answer": question.correct_answer if reveal else None,
            "rubric": question.rubric if reveal else None,
        }

    async def _validate_answer_ids(self, assignment_id: UUID, answer_map: dict[str, Any]) -> None:
        questions = (await self.db.execute(
            select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment_id)
        )).scalars().all()
        question_ids = {question.id for question in questions}
        try:
            submitted_ids = {UUID(key) for key in answer_map}
        except ValueError as exc:
            raise AssignmentError("INVALID_QUESTION_ID", "答案中包含无效题目 ID", 422) from exc
        if not submitted_ids.issubset(question_ids):
            raise AssignmentError("INVALID_QUESTION_ID", "答案中包含不属于该作业的题目", 422)
        by_id = {str(question.id): question for question in questions}
        for key, answer in answer_map.items():
            question = by_id[key]
            if question.question_type != "code" or answer in (None, {}, ""):
                continue
            try:
                code_answer = OjCodeAnswer.model_validate(answer)
            except ValueError as exc:
                raise AssignmentError("INVALID_CODE_ANSWER", "编程题答案格式无效", 422) from exc
            from config import get_settings

            if len(code_answer.source.encode("utf-8")) > get_settings().oj_source_max_bytes:
                raise AssignmentError("SOURCE_TOO_LARGE", "代码大小超过限制", 422)
            allowed = (question.public_config or {}).get("allowed_languages") or []
            if code_answer.language not in allowed:
                raise AssignmentError("LANGUAGE_NOT_ALLOWED", "该题不允许使用此语言", 422)

    async def save_draft(self, user_id: UUID, assignment_id: UUID, answers: list[Any], current_index: int):
        assignment, recipient = await self._recipient_assignment(user_id, assignment_id)
        due = effective_due_at(assignment, recipient)
        if assignment.status != "published" or utc_now() >= as_utc(due):
            raise AssignmentError("ASSIGNMENT_CLOSED", "作业已截止，无法保存", 409)
        answer_map = _answer_map(answers)
        await self._validate_answer_ids(assignment.id, answer_map)
        await self.db.execute(
            select(AssignmentRecipient.id).where(AssignmentRecipient.id == recipient.id).with_for_update()
        )
        submission = await self.db.scalar(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment.id,
                AssignmentSubmission.user_id == user_id,
            ).with_for_update()
        )
        if submission and submission.status != "in_progress":
            raise AssignmentError("SUBMISSION_LOCKED", "作业已提交，不能继续修改", 409)
        if submission is None:
            submission = AssignmentSubmission(assignment_id=assignment.id, user_id=user_id)
            self.db.add(submission)
        submission.answers_raw = answer_map
        submission.current_question_index = current_index
        submission.draft_updated_at = utc_now()
        await self.db.flush()
        return submission

    async def submit(self, user_id: UUID, assignment_id: UUID, answers: list[Any]) -> tuple[AssignmentSubmission, AssignmentJob]:
        assignment, recipient = await self._recipient_assignment(user_id, assignment_id)
        due = effective_due_at(assignment, recipient)
        if assignment.status != "published" or utc_now() >= as_utc(due):
            raise AssignmentError("ASSIGNMENT_CLOSED", "作业已截止，无法提交", 409)
        from config import get_settings

        if not get_settings().oj_enabled:
            code_count = await self.db.scalar(
                select(func.count()).select_from(AssignmentQuestion).where(
                    AssignmentQuestion.assignment_id == assignment.id,
                    AssignmentQuestion.question_type == "code",
                )
            )
            if int(code_count or 0) > 0:
                raise AssignmentError("OJ_DISABLED", "OJ 功能尚未启用，暂不能提交编程题作业", 503)
        answer_map = _answer_map(answers)
        await self._validate_answer_ids(assignment.id, answer_map)
        # The recipient row always exists and is the serialization lock for the
        # unique (assignment, user) submission. This also protects the no-draft
        # first-submit path from concurrent inserts.
        await self.db.execute(
            select(AssignmentRecipient.id).where(AssignmentRecipient.id == recipient.id).with_for_update()
        )
        submission = await self.db.scalar(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment.id,
                AssignmentSubmission.user_id == user_id,
            ).with_for_update()
        )
        if submission and submission.status != "in_progress":
            raise AssignmentError("ALREADY_SUBMITTED", "作业只能提交一次", 409)
        if submission is None:
            submission = AssignmentSubmission(assignment_id=assignment.id, user_id=user_id)
            self.db.add(submission)
            await self.db.flush()
        submission.answers_raw = answer_map
        submission.status = "pending"
        submission.submitted_at = utc_now()
        submission.grading_error = None
        job = AssignmentJob(
            assignment_id=assignment.id, submission_id=submission.id,
            requested_by_user_id=user_id, job_type="grading", status="pending", input_data={},
        )
        self.db.add(job)
        await self.db.commit()
        return submission, job

    async def serialize_submission(self, submission: AssignmentSubmission, reveal: bool) -> dict[str, Any]:
        assignment, recipient = await self._recipient_assignment(submission.user_id, submission.assignment_id)
        rows = (await self.db.execute(
            select(AssignmentAnswer, AssignmentQuestion)
            .join(AssignmentQuestion, AssignmentQuestion.id == AssignmentAnswer.question_id)
            .where(AssignmentAnswer.submission_id == submission.id)
            .order_by(AssignmentQuestion.order_index)
        )).all()
        due = effective_due_at(assignment, recipient)
        return {
            "id": submission.id, "assignment_id": assignment.id, "user_id": submission.user_id,
            "submission_status": submission.status, "provisional_score": submission.provisional_score,
            "final_score": submission.final_score, "total_score": assignment.total_score,
            "teacher_feedback": submission.teacher_feedback, "grading_error": submission.grading_error,
            "submitted_at": submission.submitted_at, "grading_completed_at": submission.grading_completed_at,
            "due_at": assignment.due_at, "effective_due_at": due, "answers_revealed": reveal,
            "question_results": [
                {"id": answer.id, "question_id": question.id, "order_index": question.order_index,
                 "question_type": question.question_type, "question_stem": question.question_stem,
                 "options": question.options, "max_score": question.max_score,
                 "user_answer": answer.user_answer, "status": answer.status,
                 "auto_score": answer.auto_score, "final_score": answer.final_score,
                 "feedback": answer.feedback, "reasoning": answer.reasoning if reveal else None,
                 "review_required": answer.review_required,
                 "grader_result": answer.grader_result, "oj_run_id": answer.oj_run_id,
                 "correct_answer": question.correct_answer if reveal else None,
                 "rubric": question.rubric if reveal else None}
                for answer, question in rows
            ],
        }

    async def get_student_submission(self, user_id: UUID, assignment_id: UUID) -> dict[str, Any]:
        assignment, recipient = await self._recipient_assignment(user_id, assignment_id)
        submission = await self.db.scalar(select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id, AssignmentSubmission.user_id == user_id
        ))
        if submission is None:
            raise AssignmentError("SUBMISSION_NOT_FOUND", "尚无答题记录", 404)
        return await self.serialize_submission(
            submission, answers_revealed(assignment, effective_due_at(assignment, recipient))
        )

    async def list_teacher_submissions(self, assignment_id: UUID, teacher_id: UUID) -> dict[str, Any]:
        assignment = await self.get_teacher_assignment(assignment_id, teacher_id)
        rows = (await self.db.execute(
            select(AssignmentRecipient, User, AssignmentSubmission)
            .join(User, User.id == AssignmentRecipient.user_id)
            .outerjoin(
                AssignmentSubmission,
                (AssignmentSubmission.assignment_id == assignment.id)
                & (AssignmentSubmission.user_id == AssignmentRecipient.user_id),
            )
            .where(AssignmentRecipient.assignment_id == assignment.id)
            .order_by(User.nickname)
        )).all()
        review_ids = set((await self.db.execute(
            select(AssignmentAnswer.submission_id).where(
                AssignmentAnswer.review_required.is_(True),
                AssignmentAnswer.submission_id.in_([s.id for _, _, s in rows if s]),
            )
        )).scalars().all()) if any(s for _, _, s in rows) else set()
        items = []
        for recipient, user, submission in rows:
            items.append({
                "submission_id": submission.id if submission else None,
                "recipient_id": recipient.id,
                "user_id": user.id, "student_name": user.nickname,
                "submission_status": submission.status if submission else ("missed" if answers_revealed(assignment, effective_due_at(assignment, recipient)) else "not_started"),
                "provisional_score": submission.provisional_score if submission else None,
                "final_score": submission.final_score if submission else None,
                "total_score": assignment.total_score,
                "review_required": bool(submission and submission.id in review_ids),
                "submitted_at": submission.submitted_at if submission else None,
                "effective_due_at": effective_due_at(assignment, recipient),
            })
        return {"assignment_id": assignment.id, "recipient_count": len(rows),
                "submitted_count": sum(1 for _, _, s in rows if s and s.status != "in_progress"), "items": items}

    async def get_teacher_submission(self, submission_id: UUID, teacher_id: UUID) -> dict[str, Any]:
        submission = await self.db.get(AssignmentSubmission, submission_id)
        if submission is None:
            raise AssignmentError("SUBMISSION_NOT_FOUND", "答卷不存在", 404)
        await self.get_teacher_assignment(submission.assignment_id, teacher_id)
        return await self.serialize_submission(submission, True)

    async def review_submission(self, submission_id: UUID, teacher_id: UUID, request: Any) -> dict[str, Any]:
        submission = await self.db.scalar(
            select(AssignmentSubmission).where(AssignmentSubmission.id == submission_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if submission is None:
            raise AssignmentError("SUBMISSION_NOT_FOUND", "答卷不存在", 404)
        assignment = await self.get_teacher_assignment(submission.assignment_id, teacher_id)
        if submission.status not in {"completed", "failed", "reviewed"}:
            raise AssignmentError("GRADING_IN_PROGRESS", "AI 批改尚未结束，暂不能复核", 409)
        answers = (await self.db.execute(
            select(AssignmentAnswer, AssignmentQuestion)
            .join(AssignmentQuestion, AssignmentQuestion.id == AssignmentAnswer.question_id)
            .where(AssignmentAnswer.submission_id == submission.id)
        )).all()
        by_id = {answer.id: (answer, question) for answer, question in answers}
        for item in request.answers:
            if item.answer_id not in by_id:
                raise AssignmentError("ANSWER_NOT_FOUND", "待改分答案不存在", 404)
            answer, question = by_id[item.answer_id]
            if item.score > question.max_score:
                raise AssignmentError("INVALID_SCORE", "改分不能超过题目满分", 422)
            previous = answer.final_score if answer.final_score is not None else answer.auto_score
            answer.final_score = item.score
            answer.review_required = False
            self.db.add(AssignmentGradeAudit(
                submission_id=submission.id, answer_id=answer.id, reviewer_user_id=teacher_id,
                previous_score=previous, new_score=item.score, comment=item.comment,
            ))
        if request.confirm_remaining:
            for answer, _ in answers:
                if answer.final_score is None and answer.auto_score is not None:
                    answer.final_score = answer.auto_score
                    answer.review_required = False
        if request.teacher_feedback is not None:
            submission.teacher_feedback = request.teacher_feedback
        final_values = [answer.final_score for answer, _ in answers]
        old_final = submission.final_score
        if answers and all(value is not None for value in final_values):
            submission.final_score = sum(float(value) for value in final_values if value is not None)
            submission.status = "reviewed"
        await self.db.commit()
        if submission.final_score is not None and submission.final_score != old_final:
            import logging

            from db.models import NotificationType
            from notifications.queue import push_notification
            from notifications.service import NotificationService
            try:
                await NotificationService.create_and_push(
                    submission.user_id, NotificationType.ASSIGNMENT_GRADE_UPDATED,
                    "作业成绩已更新", "教师已复核你的作业成绩",
                    {"assignment_id": str(submission.assignment_id), "submission_id": str(submission.id),
                     "action": "open_assignment_result"},
                )
                await push_notification(submission.user_id, {
                    "type": "assignment_grade_updated",
                    "data": {"assignment_id": str(submission.assignment_id),
                             "submission_id": str(submission.id),
                             "title": assignment.title if assignment else "教师作业",
                             "provisional_score": submission.provisional_score,
                             "final_score": submission.final_score,
                             "total_score": assignment.total_score if assignment else None,
                             "status": "reviewed"},
                })
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to send assignment grade update notification", exc_info=True
                )
        return await self.get_teacher_submission(submission.id, teacher_id)

    async def extend_deadline(
        self, assignment_id: UUID, student_id: UUID, teacher_id: UUID, due_at: datetime
    ) -> dict[str, Any]:
        assignment = await self.get_teacher_assignment(assignment_id, teacher_id)
        recipient = await self.db.scalar(select(AssignmentRecipient).where(
            AssignmentRecipient.assignment_id == assignment.id, AssignmentRecipient.user_id == student_id
        ).with_for_update())
        if recipient is None:
            raise AssignmentError("RECIPIENT_NOT_FOUND", "该学生不在本次作业接收名单中", 404)
        current = effective_due_at(assignment, recipient)
        if as_utc(due_at) <= as_utc(current) or as_utc(due_at) <= utc_now():
            raise AssignmentError("INVALID_EXTENSION", "个人截止时间只能向后延长", 422)
        recipient.due_at_override = due_at
        await self.db.flush()
        return {"assignment_id": assignment.id, "student_id": student_id, "effective_due_at": due_at}

    async def regrade(self, submission_id: UUID, teacher_id: UUID) -> AssignmentJob:
        submission = await self.db.scalar(
            select(AssignmentSubmission).where(AssignmentSubmission.id == submission_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if submission is None:
            raise AssignmentError("SUBMISSION_NOT_FOUND", "答卷不存在", 404)
        await self.get_teacher_assignment(submission.assignment_id, teacher_id)
        if submission.final_score is not None:
            raise AssignmentError("FINAL_SCORE_LOCKED", "教师最终成绩不能通过 AI 重批覆盖", 409)
        if submission.status != "failed":
            raise AssignmentError("REGRADING_NOT_ALLOWED", "当前答卷状态不能重批", 409)
        submission.status = "pending"
        submission.grading_error = None
        job = AssignmentJob(
            assignment_id=submission.assignment_id, submission_id=submission.id,
            requested_by_user_id=teacher_id, job_type="grading", status="pending", input_data={"manual_retry": True},
        )
        self.db.add(job)
        await self.db.commit()
        return job

    async def _teacher_oj_question(
        self, assignment_id: UUID, question_id: UUID, teacher_id: UUID
    ) -> tuple[Assignment, AssignmentQuestion]:
        assignment = await self.get_teacher_assignment(assignment_id, teacher_id)
        question = await self.db.scalar(select(AssignmentQuestion).where(
            AssignmentQuestion.id == question_id,
            AssignmentQuestion.assignment_id == assignment.id,
        ))
        if question is None or question.question_type != "code":
            raise AssignmentError("OJ_QUESTION_NOT_FOUND", "编程题不存在", 404)
        return assignment, question

    @staticmethod
    def _oj_error(exc: OjManagerError) -> AssignmentError:
        return AssignmentError(exc.code, str(exc), exc.status_code)

    async def get_oj_problem(
        self, assignment_id: UUID, question_id: UUID, teacher_id: UUID
    ) -> dict[str, Any]:
        assignment, question = await self._teacher_oj_question(assignment_id, question_id, teacher_id)
        draft_id = (question.grader_config or {}).get("problem_draft_id")
        if not draft_id:
            raise AssignmentError("OJ_DRAFT_NOT_FOUND", "该编程题尚未配置测试数据", 404)
        try:
            payload = await OjClient().get_draft(str(draft_id))
        except OjManagerError as exc:
            raise self._oj_error(exc) from exc
        return self._teacher_problem_payload(question, payload, assignment.version)

    @staticmethod
    def _teacher_problem_payload(
        question: AssignmentQuestion, manager_payload: dict[str, Any], assignment_version: int
    ) -> dict[str, Any]:
        config = question.grader_config or {}
        return {
            "draft_id": str(manager_payload.get("draft_id") or config.get("problem_draft_id")),
            "checksum": str(manager_payload.get("checksum") or config.get("checksum") or ""),
            "validated_checksum": config.get("validated_checksum"),
            "validation_status": config.get("validation_status", "unvalidated"),
            "assignment_version": assignment_version,
            "reference_solution": manager_payload.get("reference_solution") or {"language": "python3", "source": ""},
            "public_config": manager_payload.get("public_config") or question.public_config or {},
            "hidden_groups": manager_payload.get("hidden_groups") or [],
        }

    async def put_oj_problem(
        self, assignment_id: UUID, question_id: UUID, teacher_id: UUID,
        request: OjProblemWriteRequest,
    ) -> dict[str, Any]:
        assignment, question = await self._teacher_oj_question(assignment_id, question_id, teacher_id)
        if assignment.status != "draft":
            raise AssignmentError("QUESTIONS_LOCKED", "发布后不能修改 OJ 测试数据", 409)
        payload = request.model_dump(mode="json")
        config = dict(question.grader_config or {})
        try:
            if config.get("problem_draft_id"):
                result = await OjClient().update_draft(str(config["problem_draft_id"]), payload)
            else:
                result = await OjClient().create_draft(payload)
        except OjManagerError as exc:
            raise self._oj_error(exc) from exc
        checksum = str(result.get("checksum") or "")
        if not checksum or not result.get("draft_id"):
            raise AssignmentError("OJ_PROTOCOL_ERROR", "OJ 服务未返回题目版本", 503)
        question.public_config = request.public_config.model_dump(mode="json")
        question.correct_answer = {
            **(question.correct_answer or {}),
            "reference_solution": request.reference_solution.model_dump(mode="json"),
        }
        question.grader_config = {
            **config,
            "problem_draft_id": str(result["draft_id"]),
            "checksum": checksum,
            "validated_checksum": None,
            "problem_version_id": None,
            "validation_status": "unvalidated",
        }
        assignment.version += 1
        await self.db.commit()
        return self._teacher_problem_payload(question, result, assignment.version)

    async def import_oj_problem(
        self, assignment_id: UUID, question_id: UUID, teacher_id: UUID,
        filename: str, content: bytes,
    ) -> dict[str, Any]:
        assignment, question = await self._teacher_oj_question(assignment_id, question_id, teacher_id)
        if assignment.status != "draft":
            raise AssignmentError("QUESTIONS_LOCKED", "发布后不能导入 OJ 测试数据", 409)
        if len(content) > 20 * 1024 * 1024:
            raise AssignmentError("OJ_ZIP_TOO_LARGE", "测试数据压缩包不能超过 20MB", 413)
        if not filename.lower().endswith(".zip"):
            raise AssignmentError("INVALID_OJ_ARCHIVE", "仅支持 ZIP 测试数据", 422)
        config = dict(question.grader_config or {})
        draft_id = config.get("problem_draft_id")
        if not draft_id:
            raise AssignmentError("OJ_DRAFT_NOT_FOUND", "请先保存编程题测试配置", 409)
        try:
            result = await OjClient().import_draft(str(draft_id), filename, content)
        except OjManagerError as exc:
            raise self._oj_error(exc) from exc
        checksum = str(result.get("checksum") or "")
        question.grader_config = {
            **config, "checksum": checksum, "validated_checksum": None,
            "problem_version_id": None, "validation_status": "unvalidated",
        }
        if result.get("public_config"):
            question.public_config = result["public_config"]
        if result.get("reference_solution"):
            question.correct_answer = {
                **(question.correct_answer or {}),
                "reference_solution": result["reference_solution"],
            }
        assignment.version += 1
        await self.db.commit()
        return self._teacher_problem_payload(question, result, assignment.version)

    async def create_oj_validation_job(
        self, assignment_id: UUID, question_id: UUID, teacher_id: UUID
    ) -> AssignmentJob:
        assignment, question = await self._teacher_oj_question(assignment_id, question_id, teacher_id)
        if assignment.status != "draft":
            raise AssignmentError("QUESTIONS_LOCKED", "发布后不能重新验证 OJ 题目", 409)
        config = dict(question.grader_config or {})
        if not config.get("problem_draft_id") or not config.get("checksum"):
            raise AssignmentError("OJ_DRAFT_NOT_FOUND", "请先保存编程题测试配置", 409)
        config["validation_status"] = "pending"
        question.grader_config = config
        job = AssignmentJob(
            assignment_id=assignment.id, requested_by_user_id=teacher_id,
            job_type="oj_validation", status="pending",
            input_data={
                "question_id": str(question.id),
                "problem_draft_id": config["problem_draft_id"],
                "checksum": config["checksum"],
            },
        )
        self.db.add(job)
        await self.db.commit()
        return job

    async def create_sample_run(
        self, user_id: UUID, assignment_id: UUID, question_id: UUID,
        request: OjSampleRunRequest,
    ) -> AssignmentOjRun:
        from config import get_settings

        if not get_settings().oj_enabled:
            raise AssignmentError("OJ_DISABLED", "OJ 功能尚未启用", 503)
        assignment, recipient = await self._recipient_assignment(user_id, assignment_id)
        if assignment.status != "published" or utc_now() >= as_utc(effective_due_at(assignment, recipient)):
            raise AssignmentError("ASSIGNMENT_CLOSED", "作业已截止，不能运行样例", 409)
        question = await self.db.scalar(select(AssignmentQuestion).where(
            AssignmentQuestion.id == question_id,
            AssignmentQuestion.assignment_id == assignment.id,
        ))
        if question is None or question.question_type != "code":
            raise AssignmentError("OJ_QUESTION_NOT_FOUND", "编程题不存在", 404)
        await self._validate_answer_ids(assignment.id, {str(question.id): request.model_dump()})
        # Serialize sample-run admission across all application workers for
        # this user before applying concurrency and sliding-window limits.
        await self.db.execute(select(User.id).where(User.id == user_id).with_for_update())
        active = await self.db.scalar(select(func.count()).select_from(AssignmentOjRun).where(
            AssignmentOjRun.user_id == user_id,
            AssignmentOjRun.run_type == "sample",
            AssignmentOjRun.status.in_(["pending", "queued", "running"]),
        ))
        if active:
            raise AssignmentError("OJ_RUN_IN_PROGRESS", "当前已有样例运行任务", 429)
        cutoff = utc_now() - timedelta(minutes=1)
        recent = await self.db.scalar(select(func.count()).select_from(AssignmentOjRun).where(
            AssignmentOjRun.user_id == user_id,
            AssignmentOjRun.run_type == "sample",
            AssignmentOjRun.created_at >= cutoff,
        ))
        if int(recent or 0) >= get_settings().oj_sample_rate_per_minute:
            raise AssignmentError("OJ_RATE_LIMITED", "运行样例过于频繁，请稍后重试", 429)
        source_hash = sha256(request.source.encode("utf-8")).hexdigest()
        local = AssignmentOjRun(
            assignment_id=assignment.id, question_id=question.id, user_id=user_id,
            run_type="sample", language=request.language, source_hash=source_hash,
            source_code=request.source,
            source_expires_at=utc_now() + timedelta(hours=get_settings().oj_sample_retention_hours),
            idempotency_key=f"assignment-sample:{user_id}:{question.id}:{source_hash}:{utc_now().timestamp()}",
            status="pending",
        )
        self.db.add(local)
        await self.db.commit()
        try:
            remote = await OjClient().create_run({
                "run_type": "sample",
                "problem_version_id": (question.grader_config or {}).get("problem_version_id"),
                "language": request.language, "source": request.source,
                "idempotency_key": local.idempotency_key, "max_score": question.max_score,
            })
            local.manager_run_id = str(remote["run_id"])
            local.status = str(remote.get("status") or "pending")
        except OjManagerError as exc:
            local.status = "failed"
            local.error_message = exc.code
            local.completed_at = utc_now()
            await self.db.commit()
            raise self._oj_error(exc) from exc
        await self.db.commit()
        return local

    async def get_sample_run(
        self, user_id: UUID, assignment_id: UUID, run_id: UUID
    ) -> dict[str, Any]:
        run = await self.db.scalar(select(AssignmentOjRun).where(
            AssignmentOjRun.id == run_id,
            AssignmentOjRun.assignment_id == assignment_id,
            AssignmentOjRun.user_id == user_id,
            AssignmentOjRun.run_type == "sample",
        ))
        if run is None:
            raise AssignmentError("OJ_RUN_NOT_FOUND", "样例运行不存在", 404)
        if run.status not in {"completed", "failed"} and run.manager_run_id:
            await self.db.commit()
            try:
                remote = await OjClient().get_run(run.manager_run_id)
            except OjManagerError as exc:
                if not exc.retryable:
                    raise self._oj_error(exc) from exc
            else:
                run.status = str(remote.get("status") or run.status)
                run.result = sanitize_run_result(remote, include_samples=True)
                if run.status in {"completed", "failed"}:
                    run.completed_at = utc_now()
                await self.db.commit()
        result = dict(run.result or {})
        return {
            "run_id": run.id, "status": run.status,
            "verdict": result.get("verdict"), "score": result.get("score"),
            "groups": result.get("groups") or [], "samples": result.get("samples") or [],
            "compile_output": result.get("compile_output"), "time_ms": result.get("time_ms"),
            "memory_kb": result.get("memory_kb"), "created_at": run.created_at,
            "completed_at": run.completed_at,
        }
