"""Structured quota exception classes with frontend-friendly error data."""

from typing import Any


class QuotaExceededError(Exception):
    """Base class for quota-related errors."""

    def __init__(
        self,
        code: str,
        message: str,
        detail: dict[str, Any],
        status_code: int = 403,
    ) -> None:
        self.code = code
        self.message = message
        self.detail = detail
        self.status_code = status_code
        super().__init__(message)

    def to_response_body(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            **self.detail,
        }


class DailyMessageQuotaExceeded(QuotaExceededError):
    def __init__(self, used: int, limit: int, tier: str) -> None:
        super().__init__(
            code="DAILY_MESSAGE_QUOTA_EXCEEDED",
            message=f"今日对话次数已达上限（{used}/{limit}），请明天再试或升级订阅",
            detail={
                "quota_type": "daily_messages",
                "used": used,
                "limit": limit,
                "tier": tier,
                "upgrade_needed": True,
            },
            status_code=429,
        )


class SpaceCountQuotaExceeded(QuotaExceededError):
    def __init__(self, used: int, limit: int, tier: str) -> None:
        super().__init__(
            code="SPACE_COUNT_QUOTA_EXCEEDED",
            message=f"学习空间数量已达上限（{used}/{limit}），请升级订阅以创建更多空间",
            detail={
                "quota_type": "space_count",
                "used": used,
                "limit": limit,
                "tier": tier,
                "upgrade_needed": True,
            },
        )


class ModelNotAllowedForTier(QuotaExceededError):
    def __init__(self, model_id: str, tier: str, allowed_models: list[str]) -> None:
        super().__init__(
            code="MODEL_NOT_ALLOWED",
            message=f"当前订阅等级不支持使用模型 {model_id}，请升级订阅",
            detail={
                "quota_type": "model_access",
                "requested_model": model_id,
                "allowed_models": allowed_models,
                "tier": tier,
                "upgrade_needed": True,
            },
        )


class StorageQuotaExceeded(QuotaExceededError):
    def __init__(
        self,
        used_bytes: int,
        limit_bytes: int,
        tier: str,
        new_file_bytes: int,
    ) -> None:
        used_mb = round(used_bytes / (1024 * 1024), 1)
        limit_mb = round(limit_bytes / (1024 * 1024), 1)
        super().__init__(
            code="STORAGE_QUOTA_EXCEEDED",
            message=f"空间存储已达上限（{used_mb}MB/{limit_mb}MB），请删除文件或升级订阅",
            detail={
                "quota_type": "storage",
                "used_bytes": used_bytes,
                "limit_bytes": limit_bytes,
                "new_file_bytes": new_file_bytes,
                "tier": tier,
                "upgrade_needed": True,
            },
        )
