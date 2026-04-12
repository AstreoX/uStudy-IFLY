from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CalendarEventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    start_time: datetime
    end_time: datetime
    details: Optional[str] = Field(None, max_length=5000)
    external_id: Optional[str] = Field(None, max_length=100)
    source_conversation_id: Optional[UUID] = None


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    details: Optional[str] = Field(None, max_length=5000)
    external_id: Optional[str] = Field(None, max_length=100)


class CalendarEventResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    start_time: datetime
    end_time: datetime
    details: Optional[str] = None
    external_id: Optional[str] = None
    source_conversation_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
