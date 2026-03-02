"""Assessment API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from assessment.schemas import (
    ComprehensionScoreResponse,
    ContinuityCalendarResponse,
    ContinuityScoreResponse,
    DepthScoreResponse,
    FocusScoreResponse,
    KnowledgeStructureScoreResponse,
    ProfileStatsResponse,
    ReviewScoreResponse,
)
from assessment.service import (
    ComprehensionService,
    ContinuityService,
    DepthService,
    FocusService,
    KnowledgeStructureService,
    ProfileStatsService,
    ReviewAssessmentService,
)
from auth.dependencies import CurrentUser
from db.database import get_db

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.get("/profile-stats", response_model=ProfileStatsResponse)
async def get_profile_stats(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ProfileStatsResponse:
    """Get profile stats for the current user."""
    result = await ProfileStatsService.get_profile_stats(db, user.id)
    return ProfileStatsResponse(**result)


@router.get("/continuity", response_model=ContinuityScoreResponse)
async def get_continuity_score(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ContinuityScoreResponse:
    """Get continuity score and status for the current user."""
    result = await ContinuityService.get_continuity_score(db, user.id)
    return ContinuityScoreResponse(**result)


@router.get("/focus", response_model=FocusScoreResponse)
async def get_focus_score(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    week_offset: int = Query(default=0, ge=0, le=52),
) -> FocusScoreResponse:
    """Get focus score for the current user for a given week."""
    result = await FocusService.get_focus_score(db, user.id, week_offset)
    return FocusScoreResponse(**result)


@router.get("/depth", response_model=DepthScoreResponse)
async def get_depth_score(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    week_offset: int = Query(default=0, ge=0, le=52),
) -> DepthScoreResponse:
    """Get depth score for the current user for a given week."""
    result = await DepthService.get_depth_score(db, user.id, week_offset)
    return DepthScoreResponse(**result)


@router.get("/comprehension", response_model=ComprehensionScoreResponse)
async def get_comprehension_score(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ComprehensionScoreResponse:
    """Get comprehension score for the current user (global snapshot)."""
    result = await ComprehensionService.get_comprehension_score(db, user.id)
    return ComprehensionScoreResponse(**result)


@router.get("/knowledge-structure", response_model=KnowledgeStructureScoreResponse)
async def get_knowledge_structure_score(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> KnowledgeStructureScoreResponse:
    """Get knowledge structure score for the current user (global snapshot)."""
    result = await KnowledgeStructureService.get_knowledge_structure_score(db, user.id)
    return KnowledgeStructureScoreResponse(**result)


@router.get("/review", response_model=ReviewScoreResponse)
async def get_review_score(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ReviewScoreResponse:
    """Get review score for the current user."""
    result = await ReviewAssessmentService.get_review_score(db, user.id)
    return ReviewScoreResponse(**result)


@router.get("/continuity/calendar", response_model=ContinuityCalendarResponse)
async def get_continuity_calendar(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    months: int = Query(default=3, ge=1, le=12),
) -> ContinuityCalendarResponse:
    """Get study activity calendar for the last N months."""
    result = await ContinuityService.get_calendar(db, user.id, months)
    return ContinuityCalendarResponse(**result)
