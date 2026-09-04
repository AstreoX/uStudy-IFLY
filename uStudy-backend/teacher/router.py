"""Teacher-only analytics endpoints for course spaces."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import User
from teacher.dependencies import require_course_teacher
from teacher.presentations.router import router as presentations_router
from teacher.schemas import (
    KnowledgeResponse,
    OverviewResponse,
    StudentDetailResponse,
    StudentListResponse,
)
from teacher.service import TeacherAnalyticsService

router = APIRouter(prefix="/api/teacher", tags=["teacher"])

# Public presentation routes inherit this router's /api/teacher prefix. The
# sandbox capability gateway has an /api/internal prefix and is mounted
# separately in main.py so it is never exposed below the teacher API prefix.
router.include_router(presentations_router)


def _service(db: AsyncSession, space_id: UUID, days: int) -> TeacherAnalyticsService:
    if days not in {7, 30, 90}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_PERIOD", "message": "days 仅支持 7、30 或 90"},
        )
    return TeacherAnalyticsService(db, space_id, days)


@router.get("/spaces/{space_id}/overview", response_model=OverviewResponse)
async def get_overview(
    space_id: UUID,
    days: int = Query(7),
    _: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> OverviewResponse:
    return await _service(db, space_id, days).get_overview()


@router.get("/spaces/{space_id}/knowledge", response_model=KnowledgeResponse)
async def get_knowledge(
    space_id: UUID,
    days: int = Query(7),
    _: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeResponse:
    return await _service(db, space_id, days).get_knowledge()


@router.get("/spaces/{space_id}/students", response_model=StudentListResponse)
async def get_students(
    space_id: UUID,
    days: int = Query(7),
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: Literal["last_active", "coverage", "mastery", "quiz_accuracy"] = Query("last_active"),
    _: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> StudentListResponse:
    return await _service(db, space_id, days).get_students(search, page, page_size, sort)


@router.get(
    "/spaces/{space_id}/students/{student_id}",
    response_model=StudentDetailResponse,
)
async def get_student_detail(
    space_id: UUID,
    student_id: UUID,
    days: int = Query(7),
    _: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> StudentDetailResponse:
    detail = await _service(db, space_id, days).get_student_detail(student_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "该学生不属于当前课程空间"},
        )
    return detail
