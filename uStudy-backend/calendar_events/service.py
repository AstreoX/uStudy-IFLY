import logging
from datetime import datetime
from typing import List
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CalendarEvent
from calendar_events.schemas import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventResponse,
)

logger = logging.getLogger(__name__)


class CalendarEventNotFoundError(Exception):
    pass


class CalendarEventAccessDeniedError(Exception):
    pass


class CalendarEventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, user_id: UUID, request: CalendarEventCreate) -> CalendarEventResponse:
        event = CalendarEvent(
            user_id=user_id,
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
            details=request.details,
            external_id=request.external_id,
            source_conversation_id=request.source_conversation_id,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return CalendarEventResponse.model_validate(event)

    async def get_events_in_range(
        self, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> List[CalendarEventResponse]:
        stmt = (
            select(CalendarEvent)
            .where(
                and_(
                    CalendarEvent.user_id == user_id,
                    CalendarEvent.start_time < end_date,
                    CalendarEvent.end_time > start_date,
                )
            )
            .order_by(CalendarEvent.start_time)
        )
        result = await self.db.execute(stmt)
        events = result.scalars().all()
        return [CalendarEventResponse.model_validate(e) for e in events]

    async def get_event(self, user_id: UUID, event_id: UUID) -> CalendarEventResponse:
        event = await self._get_owned_event(user_id, event_id)
        return CalendarEventResponse.model_validate(event)

    async def update_event(
        self, user_id: UUID, event_id: UUID, request: CalendarEventUpdate
    ) -> CalendarEventResponse:
        event = await self._get_owned_event(user_id, event_id)
        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(event, key, value)
        await self.db.commit()
        await self.db.refresh(event)
        return CalendarEventResponse.model_validate(event)

    async def delete_event(self, user_id: UUID, event_id: UUID) -> None:
        event = await self._get_owned_event(user_id, event_id)
        await self.db.delete(event)
        await self.db.commit()

    async def _get_owned_event(self, user_id: UUID, event_id: UUID) -> CalendarEvent:
        stmt = select(CalendarEvent).where(CalendarEvent.id == event_id)
        result = await self.db.execute(stmt)
        event = result.scalar_one_or_none()
        if not event:
            raise CalendarEventNotFoundError()
        if event.user_id != user_id:
            raise CalendarEventAccessDeniedError()
        return event
