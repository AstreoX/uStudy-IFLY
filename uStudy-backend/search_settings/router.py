"""Search settings API router."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from search_settings.schemas import SearchSettingsResponse, SearchSettingsUpdate
from search_settings.service import SearchSettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search-settings", tags=["search-settings"])


@router.get("", response_model=SearchSettingsResponse)
async def get_search_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchSettingsResponse:
    """Get current user's search channel settings."""
    settings = await SearchSettingsService.get_or_create(user.id, db)
    return SearchSettingsResponse(
        web_search_enabled=settings.web_search_enabled,
        academic_search_enabled=settings.academic_search_enabled,
        encyclopedia_search_enabled=settings.encyclopedia_search_enabled,
        course_search_enabled=settings.course_search_enabled,
    )


@router.patch("", response_model=SearchSettingsResponse)
async def update_search_settings(
    data: SearchSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchSettingsResponse:
    """Partial update of user's search channel settings."""
    settings = await SearchSettingsService.update(user.id, data, db)
    return SearchSettingsResponse(
        web_search_enabled=settings.web_search_enabled,
        academic_search_enabled=settings.academic_search_enabled,
        encyclopedia_search_enabled=settings.encyclopedia_search_enabled,
        course_search_enabled=settings.course_search_enabled,
    )
