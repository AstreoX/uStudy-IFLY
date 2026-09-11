"""Shared request and response models for the presentation sandbox services."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, HttpUrl, field_validator

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def validate_identifier(value: str) -> str:
    """Reject identifiers that could change Docker resource names or labels."""

    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError("must contain only letters, digits, dot, underscore or hyphen")
    return value


class AgentScope(BaseModel):
    run_id: str
    project_id: str
    user_id: str
    space_id: str

    @field_validator("run_id", "project_id", "user_id", "space_id")
    @classmethod
    def identifiers_are_safe(cls, value: str) -> str:
        return validate_identifier(value)


class RunCreateRequest(AgentScope):
    """Payload accepted by the internal sandbox manager."""

    run_id: str = Field(validation_alias=AliasChoices("run_id", "id"))
    gateway_url: HttpUrl
    capability_token: str = Field(min_length=16, max_length=4096)
    instruction: str = Field(
        min_length=1,
        max_length=131_072,
        validation_alias=AliasChoices("instruction", "prompt"),
    )
    # Legacy max_iterations/max_seconds fields are ignored by Pydantic.
    max_attempts: int = Field(default=5, ge=1, le=10)
    attempt: int = Field(default=1, ge=1, le=10)
    retry_backoff_seconds: list[int] = Field(
        default_factory=lambda: [2, 5, 10, 20, 30], min_length=1, max_length=10
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunCreated(BaseModel):
    run_id: str
    project_id: str
    container_name: str
    workspace_volume: str
    status: Literal["starting"] = "starting"


class RunStatus(BaseModel):
    run_id: str
    project_id: str | None = None
    container_name: str
    status: Literal[
        "starting", "running", "recovering", "succeeded", "failed", "cancelled", "unknown"
    ]
    attempt: int = 1
    max_attempts: int = 5
    retry_at: str | None = None
    exit_code: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
