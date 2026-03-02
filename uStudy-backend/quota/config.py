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
        allowed_model_ids=("grok-4-fast",),
        storage_per_space_bytes=30 * 1024 * 1024,  # 30 MB
        max_upload_file_bytes=10 * 1024 * 1024,  # 10 MB
    ),
    SubscriptionTier.BASIC: TierLimits(
        max_spaces=5,
        daily_messages=150,
        allowed_model_ids=("grok-4-fast", "kimi-k2.5"),
        storage_per_space_bytes=200 * 1024 * 1024,  # 200 MB
        max_upload_file_bytes=50 * 1024 * 1024,  # 50 MB
    ),
    SubscriptionTier.PREMIUM: TierLimits(
        max_spaces=None,
        daily_messages=None,
        allowed_model_ids=("grok-4-fast", "kimi-k2.5", "gemini-3.1-pro"),
        storage_per_space_bytes=500 * 1024 * 1024,  # 500 MB
        max_upload_file_bytes=100 * 1024 * 1024,  # 100 MB
    ),
    SubscriptionTier.ALPHA: TierLimits(
        max_spaces=None,
        daily_messages=None,
        allowed_model_ids=("grok-4-fast", "kimi-k2.5", "gemini-3.1-pro"),
        storage_per_space_bytes=500 * 1024 * 1024,  # 500 MB
        max_upload_file_bytes=100 * 1024 * 1024,  # 100 MB
    ),
}


def get_tier_limits(tier: SubscriptionTier) -> TierLimits:
    """Get limits for a given tier, defaulting to FREE if unknown."""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
