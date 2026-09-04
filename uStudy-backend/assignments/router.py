"""Student and course-space teacher assignment APIs."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from assignments.schemas import (
    AssignmentDetailResponse,
    AssignmentDraftRequest,
    AssignmentDraftResponse,
    AssignmentGenerateRequest,
    AssignmentJobResponse,
    AssignmentListItemResponse,
    AssignmentSubmissionResponse,
    AssignmentSubmitRequest,
    AssignmentSubmitResponse,
    AssignmentTeacherResponse,
    AssignmentUpdateRequest,
    OjCapabilitiesResponse,
    OjProblemResponse,
    OjProblemWriteRequest,
    OjRunResponse,
    OjSampleRunAcceptedResponse,
    OjSampleRunRequest,
    OjValidationResponse,
    RecipientDeadlineUpdateRequest,
    SubmissionReviewRequest,
    TeacherSubmissionListResponse,
)
from assignments.service import AssignmentError, AssignmentService, utc_now
from assignments.tasks import dispatch_job
from auth.dependencies import get_current_user
from db.database import get_db
from db.models import Assignment, AssignmentSubmission, User
from teacher.dependencies import require_course_teacher

student_router = APIRouter(prefix="/api/assignments", tags=["assignments"])
teacher_router = APIRouter(
    prefix="/api/teacher/spaces/{space_id}/assignments", tags=["teacher-assignments"]
)


def _http_error(exc: AssignmentError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@student_router.get("", response_model=list[AssignmentListItemResponse])
async def list_assignments(
    space_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AssignmentService(db).list_student_assignments(user.id, space_id)


@student_router.get("/oj/capabilities", response_model=OjCapabilitiesResponse)
async def get_oj_capabilities(
    _: User = Depends(get_current_user),
):
    from config import get_settings

    return {
        "enabled": get_settings().oj_enabled,
        "languages": ["python3", "cpp20"],
    }


@student_router.get("/{assignment_id}", response_model=AssignmentDetailResponse)
async def get_assignment(
    assignment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await AssignmentService(db).get_student_detail(user.id, assignment_id)
    except AssignmentError as exc:
        raise _http_error(exc)


@student_router.put("/{assignment_id}/draft", response_model=AssignmentDraftResponse)
async def save_assignment_draft(
    assignment_id: UUID,
    request: AssignmentDraftRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        submission = await AssignmentService(db).save_draft(
            user.id, assignment_id, request.answers, request.current_question_index
        )
        return {
            "assignment_id": assignment_id, "submission_id": submission.id,
            "submission_status": "in_progress", "draft_updated_at": submission.draft_updated_at,
        }
    except AssignmentError as exc:
        raise _http_error(exc)


@student_router.post(
    "/{assignment_id}/submit", response_model=AssignmentSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_assignment(
    assignment_id: UUID,
    request: AssignmentSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        submission, job = await AssignmentService(db).submit(user.id, assignment_id, request.answers)
        dispatch_job(job.id)
        return {
            "assignment_id": assignment_id, "submission_id": submission.id,
            "job_id": job.id, "submission_status": "pending",
            "message": "作业已提交，AI 正在批改",
        }
    except AssignmentError as exc:
        raise _http_error(exc)


@student_router.get(
    "/{assignment_id}/submission", response_model=AssignmentSubmissionResponse
)
async def get_assignment_submission(
    assignment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await AssignmentService(db).get_student_submission(user.id, assignment_id)
    except AssignmentError as exc:
        raise _http_error(exc)


@student_router.post(
    "/{assignment_id}/questions/{question_id}/sample-runs",
    response_model=OjSampleRunAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_oj_sample_run(
    assignment_id: UUID,
    question_id: UUID,
    request: OjSampleRunRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        run = await AssignmentService(db).create_sample_run(
            user.id, assignment_id, question_id, request
        )
        return {"run_id": run.id, "status": run.status}
    except AssignmentError as exc:
        raise _http_error(exc)


@student_router.get(
    "/{assignment_id}/sample-runs/{run_id}", response_model=OjRunResponse
)
async def get_oj_sample_run(
    assignment_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await AssignmentService(db).get_sample_run(user.id, assignment_id, run_id)
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.get("", response_model=list[AssignmentTeacherResponse])
async def list_teacher_assignments(
    space_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    return await AssignmentService(db).list_teacher_assignments(space_id, teacher.id)


@teacher_router.post(
    "/generate", response_model=AssignmentJobResponse, status_code=status.HTTP_202_ACCEPTED
)
async def generate_assignment(
    space_id: UUID,
    request: AssignmentGenerateRequest,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await AssignmentService(db).create_generation_job(space_id, teacher.id, request)
        dispatch_job(job.id)
        return job
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.get("/jobs/{job_id}", response_model=AssignmentJobResponse)
async def get_assignment_job(
    space_id: UUID,
    job_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await AssignmentService(db).get_job(job_id, teacher.id)
        if job.assignment_id:
            assignment = await db.get(Assignment, job.assignment_id)
            if assignment is None or assignment.space_id != space_id:
                raise AssignmentError("JOB_NOT_FOUND", "任务不存在", 404)
        return job
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.post(
    "/jobs/{job_id}/questions/{question_index}/retry",
    response_model=AssignmentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_assignment_question(
    space_id: UUID,
    job_id: UUID,
    question_index: int,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Retry exactly one failed AI-generated question."""
    try:
        if question_index < 0:
            raise AssignmentError("QUESTION_NOT_FOUND", "题目序号无效", 422)
        service = AssignmentService(db)
        job = await service.get_job(job_id, teacher.id)
        if job.job_type != "generation" or job.assignment_id is None:
            raise AssignmentError("JOB_NOT_FOUND", "生成任务不存在", 404)
        assignment = await db.get(Assignment, job.assignment_id)
        if assignment is None or assignment.space_id != space_id:
            raise AssignmentError("JOB_NOT_FOUND", "任务不存在", 404)
        if job.status not in {"partial_failed", "failed"}:
            raise AssignmentError("JOB_NOT_RETRYABLE", "任务仍在处理中，请等待当前进度完成", 409)
        failures = [item for item in (job.output_data or {}).get("failed_questions", [])
                    if isinstance(item, dict) and int(item.get("index", -1)) == question_index]
        if not failures:
            raise AssignmentError("QUESTION_NOT_RETRYABLE", "该题没有可重试的失败记录", 409)
        input_data = dict(job.input_data or {})
        input_data["retry_question_index"] = question_index
        job.input_data = input_data
        job.status = "pending"
        job.available_at = utc_now()
        job.completed_at = None
        job.lease_expires_at = None
        job.error_message = None
        await db.commit()
        dispatch_job(job.id)
        return job
    except AssignmentError as exc:
        raise _http_error(exc)


# Keep static /submissions routes before /{assignment_id} so FastAPI never
# attempts to parse the literal word "submissions" as a UUID.
@teacher_router.get(
    "/submissions/{submission_id}", response_model=AssignmentSubmissionResponse
)
async def get_teacher_submission(
    space_id: UUID,
    submission_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await AssignmentService(db).get_teacher_submission(submission_id, teacher.id)
        assignment = await db.get(Assignment, result["assignment_id"])
        if assignment is None or assignment.space_id != space_id:
            raise AssignmentError("SUBMISSION_NOT_FOUND", "答卷不存在", 404)
        return result
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.patch(
    "/submissions/{submission_id}/review", response_model=AssignmentSubmissionResponse
)
async def review_teacher_submission(
    space_id: UUID,
    submission_id: UUID,
    request: SubmissionReviewRequest,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        submission = await db.get(AssignmentSubmission, submission_id)
        assignment = await db.get(Assignment, submission.assignment_id) if submission else None
        if assignment is None or assignment.space_id != space_id:
            raise AssignmentError("SUBMISSION_NOT_FOUND", "答卷不存在", 404)
        return await AssignmentService(db).review_submission(submission_id, teacher.id, request)
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.post(
    "/submissions/{submission_id}/regrade", response_model=AssignmentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regrade_teacher_submission(
    space_id: UUID,
    submission_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        submission = await db.get(AssignmentSubmission, submission_id)
        assignment = await db.get(Assignment, submission.assignment_id) if submission else None
        if assignment is None or assignment.space_id != space_id:
            raise AssignmentError("SUBMISSION_NOT_FOUND", "答卷不存在", 404)
        job = await AssignmentService(db).regrade(submission_id, teacher.id)
        dispatch_job(job.id)
        return job
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.get(
    "/{assignment_id}/questions/{question_id}/oj-problem", response_model=OjProblemResponse
)
async def get_teacher_oj_problem(
    space_id: UUID,
    assignment_id: UUID,
    question_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return await AssignmentService(db).get_oj_problem(assignment_id, question_id, teacher.id)
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.put(
    "/{assignment_id}/questions/{question_id}/oj-problem", response_model=OjProblemResponse
)
async def put_teacher_oj_problem(
    space_id: UUID,
    assignment_id: UUID,
    question_id: UUID,
    request: OjProblemWriteRequest,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return await AssignmentService(db).put_oj_problem(
            assignment_id, question_id, teacher.id, request
        )
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.post(
    "/{assignment_id}/questions/{question_id}/oj-problem/import",
    response_model=OjProblemResponse,
)
async def import_teacher_oj_problem(
    space_id: UUID,
    assignment_id: UUID,
    question_id: UUID,
    file: UploadFile = File(...),
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        # Read one byte over the hard limit so oversize uploads are rejected
        # without buffering an unbounded body in application memory.
        content = await file.read(20 * 1024 * 1024 + 1)
        return await AssignmentService(db).import_oj_problem(
            assignment_id, question_id, teacher.id, file.filename or "tests.zip", content
        )
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.post(
    "/{assignment_id}/questions/{question_id}/oj-problem/validate",
    response_model=OjValidationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def validate_teacher_oj_problem(
    space_id: UUID,
    assignment_id: UUID,
    question_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        job = await AssignmentService(db).create_oj_validation_job(
            assignment_id, question_id, teacher.id
        )
        dispatch_job(job.id)
        return {"job_id": job.id}
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.get("/{assignment_id}", response_model=AssignmentTeacherResponse)
async def get_teacher_assignment(
    space_id: UUID,
    assignment_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return await AssignmentService(db).serialize_teacher_assignment(assignment)
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.patch("/{assignment_id}", response_model=AssignmentTeacherResponse)
async def update_teacher_assignment(
    space_id: UUID,
    assignment_id: UUID,
    request: AssignmentUpdateRequest,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return await AssignmentService(db).update_assignment(assignment_id, teacher.id, request)
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_teacher_assignment(
    space_id: UUID,
    assignment_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        await AssignmentService(db).delete_assignment(assignment_id, teacher.id)
        return
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.post("/{assignment_id}/publish", response_model=AssignmentTeacherResponse)
async def publish_assignment(
    space_id: UUID,
    assignment_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return await AssignmentService(db).publish(assignment_id, teacher.id)
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.post("/{assignment_id}/close", response_model=AssignmentTeacherResponse)
async def close_assignment(
    space_id: UUID,
    assignment_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return await AssignmentService(db).close(assignment_id, teacher.id)
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.get(
    "/{assignment_id}/submissions", response_model=TeacherSubmissionListResponse
)
async def list_assignment_submissions(
    space_id: UUID,
    assignment_id: UUID,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return await AssignmentService(db).list_teacher_submissions(assignment_id, teacher.id)
    except AssignmentError as exc:
        raise _http_error(exc)


@teacher_router.patch("/{assignment_id}/recipients/{student_id}/deadline")
async def extend_assignment_deadline(
    space_id: UUID,
    assignment_id: UUID,
    student_id: UUID,
    request: RecipientDeadlineUpdateRequest,
    teacher: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
):
    try:
        assignment = await AssignmentService(db).get_teacher_assignment(assignment_id, teacher.id)
        if assignment.space_id != space_id:
            raise AssignmentError("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        return await AssignmentService(db).extend_deadline(
            assignment_id, student_id, teacher.id, request.due_at
        )
    except AssignmentError as exc:
        raise _http_error(exc)
