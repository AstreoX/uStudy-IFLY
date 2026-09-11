"""Centralized tier limits configuration — single source of truth."""

from dataclasses import dataclass

from db.models import SubscriptionTier


@dataclass(frozen=True)
class TierLimits:
    max_spaces: int | None  # None = unlimited
    daily_messages: int | None  # None = unlimited
    allowed_model_ids: tuple[str, ...]
    storage_per_space_bytes: int
    max_upload_file_bytes: int


TIER_LIMITS: dict[SubscriptionTier, TierLimits] = {
    SubscriptionTier.FREE: TierLimits(
        max_spaces=1,
        daily_messages=20,
        allowed_model_ids=("deepseek-v4.1-flash", "glm-5.3-flash"),
        storage_per_space_bytes=30 * 1024 * 1024,  # 30 MB
        max_upload_file_bytes=50 * 1024 * 1024,  # 50 MB
    ),
    SubscriptionTier.BASIC: TierLimits(
        max_spaces=5,
        daily_messages=150,
        allowed_model_ids=("deepseek-v4.1-flash", "glm-5.3-flash"),
        storage_per_space_bytes=300 * 1024 * 1024,  # 300 MB
        max_upload_file_bytes=200 * 1024 * 1024,  # 200 MB
    ),
    SubscriptionTier.PREMIUM: TierLimits(
        max_spaces=None,
        daily_messages=None,
        allowed_model_ids=("deepseek-v4.1-flash", "glm-5.3-flash"),
        storage_per_space_bytes=2 * 1024 * 1024 * 1024,  # 2 GB
        max_upload_file_bytes=500 * 1024 * 1024,  # 500 MB
    ),
    SubscriptionTier.ALPHA: TierLimits(
        max_spaces=None,
        daily_messages=None,
        allowed_model_ids=("deepseek-v4.1-flash", "glm-5.3-flash"),
        storage_per_space_bytes=2 * 1024 * 1024 * 1024,  # 2 GB
        max_upload_file_bytes=500 * 1024 * 1024,  # 500 MB
    ),
    SubscriptionTier.ULTRA: TierLimits(
        max_spaces=None,
        daily_messages=None,
        allowed_model_ids=("deepseek-v4.1-flash", "glm-5.3-flash"),
        storage_per_space_bytes=2 * 1024 * 1024 * 1024,  # 2 GB
        max_upload_file_bytes=500 * 1024 * 1024,  # 500 MB
    ),
}


def get_tier_limits(tier: SubscriptionTier) -> TierLimits:
    """Get limits for a given tier, defaulting to FREE if unknown."""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
