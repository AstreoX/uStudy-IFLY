from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from calendar_events.schemas import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventResponse,
)
from calendar_events.service import (
    CalendarEventService,
    CalendarEventNotFoundError,
    CalendarEventAccessDeniedError,
)

router = APIRouter(
    prefix="/api/calendar/events",
    tags=["calendar"],
)


@router.get(
    "",
    response_model=List[CalendarEventResponse],
    summary="获取日期范围内的日历事件",
)
async def get_events(
    start_date: datetime = Query(..., description="范围起始时间"),
    end_date: datetime = Query(..., description="范围结束时间"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CalendarEventResponse]:
    service = CalendarEventService(db)
    return await service.get_events_in_range(user.id, start_date, end_date)


@router.get(
    "/{event_id}",
    response_model=CalendarEventResponse,
    summary="获取单个日历事件",
)
async def get_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    service = CalendarEventService(db)
    try:
        return await service.get_event(user.id, event_id)
    except CalendarEventNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EVENT_NOT_FOUND", "message": "日历事件不存在"},
        )
    except CalendarEventAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "EVENT_ACCESS_DENIED", "message": "无权访问该日历事件"},
        )


@router.post(
    "",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建日历事件",
)
async def create_event(
    request: CalendarEventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    service = CalendarEventService(db)
    return await service.create_event(user.id, request)


@router.patch(
    "/{event_id}",
    response_model=CalendarEventResponse,
    summary="更新日历事件",
)
async def update_event(
    event_id: UUID,
    request: CalendarEventUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarEventResponse:
    service = CalendarEventService(db)
    try:
        return await service.update_event(user.id, event_id, request)
    except CalendarEventNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EVENT_NOT_FOUND", "message": "日历事件不存在"},
        )
    except CalendarEventAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "EVENT_ACCESS_DENIED", "message": "无权访问该日历事件"},
        )


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除日历事件",
)
async def delete_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = CalendarEventService(db)
    try:
        await service.delete_event(user.id, event_id)
    except CalendarEventNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EVENT_NOT_FOUND", "message": "日历事件不存在"},
        )
    except CalendarEventAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "EVENT_ACCESS_DENIED", "message": "无权访问该日历事件"},
        )
