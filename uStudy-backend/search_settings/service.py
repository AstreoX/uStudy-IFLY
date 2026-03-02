"""Search settings service layer."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_scoped_session
from db.models import UserSearchSettings
from search_settings.schemas import SearchSettingsUpdate

logger = logging.getLogger(__name__)


class SearchSettingsService:
    """Service for managing user search channel settings."""

    @staticmethod
    async def get_or_create(user_id: UUID, db: AsyncSession) -> UserSearchSettings:
        """Get user's search settings, creating defaults if none exist."""
        result = await db.execute(
            select(UserSearchSettings).where(UserSearchSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        if not settings:
            settings = UserSearchSettings(user_id=user_id)
            db.add(settings)
            await db.commit()
            await db.refresh(settings)

        return settings

    @staticmethod
    async def update(
        user_id: UUID, data: SearchSettingsUpdate, db: AsyncSession
    ) -> UserSearchSettings:
        """Partial update of user's search settings."""
        result = await db.execute(
            select(UserSearchSettings).where(UserSearchSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        if not settings:
            settings = UserSearchSettings(user_id=user_id)
            db.add(settings)
            await db.flush()

        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(settings, key, value)

        await db.commit()
        await db.refresh(settings)
        return settings

    @staticmethod
    async def get_enabled_channels(user_id: UUID) -> dict[str, bool]:
        """
        Get enabled search channels for a user.

        Uses standalone get_scoped_session() for use outside FastAPI request lifecycle
        (e.g., from orchestrator/service).
        """
        async with get_scoped_session() as db:
            result = await db.execute(
                select(UserSearchSettings).where(
                    UserSearchSettings.user_id == user_id
                )
            )
            settings = result.scalar_one_or_none()

        # Return defaults if no settings exist
        if not settings:
            return {
                "web_search_enabled": True,
                "academic_search_enabled": True,
                "encyclopedia_search_enabled": True,
                "course_search_enabled": True,
            }

        return {
            "web_search_enabled": settings.web_search_enabled,
            "academic_search_enabled": settings.academic_search_enabled,
            "encyclopedia_search_enabled": settings.encyclopedia_search_enabled,
            "course_search_enabled": settings.course_search_enabled,
        }
