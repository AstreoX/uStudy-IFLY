"""Search settings Pydantic schemas."""

from pydantic import BaseModel


class SearchSettingsResponse(BaseModel):
    """Response schema for search settings."""

    web_search_enabled: bool = True
    academic_search_enabled: bool = True
    encyclopedia_search_enabled: bool = True
    course_search_enabled: bool = True


class SearchSettingsUpdate(BaseModel):
    """Partial update schema for search settings."""

    web_search_enabled: bool | None = None
    academic_search_enabled: bool | None = None
    encyclopedia_search_enabled: bool | None = None
    course_search_enabled: bool | None = None
