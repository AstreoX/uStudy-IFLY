"""Pydantic models for quota status API responses."""

from pydantic import BaseModel


class QuotaUsage(BaseModel):
    used: int
    limit: int | None  # None = unlimited
    remaining: int | None  # None = unlimited


class StorageUsage(BaseModel):
    used_bytes: int
    limit_bytes: int
    remaining_bytes: int


class QuotaStatusResponse(BaseModel):
    tier: str
    daily_messages: QuotaUsage
    space_count: QuotaUsage
    allowed_models: list[str]
    storage_per_space_bytes: int
