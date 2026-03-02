"""Chat Models Configuration - Allowed models registry and helpers"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from db.models import SubscriptionTier

ALLOWED_MODELS: dict[str, dict[str, Any]] = {
    "grok-4-fast": {
        "openrouter_id": "x-ai/grok-4-fast",
        "display_name": "Grok 4 Fast",
        "description": "快速响应，适合日常对话",
        "is_default": True,
    },
    "kimi-k2.5": {
        "openrouter_id": "moonshotai/kimi-k2.5",
        "display_name": "Kimi K2.5",
        "description": "更强推理能力，适合复杂问题",
    },
    "gemini-3.1-pro": {
        "openrouter_id": "google/gemini-3.1-pro-preview",
        "display_name": "Gemini 3.1 Pro",
        "description": "Google 最新模型，综合能力强",
        "use_bridge": True,
    },
}

DEFAULT_MODEL_ID = "grok-4-fast"


def get_openrouter_model(model_id: str | None) -> str:
    """Resolve a model_id to an OpenRouter model string.

    Falls back to the default model when model_id is None or not found.
    """
    if model_id and model_id in ALLOWED_MODELS:
        return ALLOWED_MODELS[model_id]["openrouter_id"]
    return ALLOWED_MODELS[DEFAULT_MODEL_ID]["openrouter_id"]


def validate_model_id(model_id: str) -> bool:
    """Check whether a model_id is in the allowed set."""
    return model_id in ALLOWED_MODELS


def get_available_models(
    tier: SubscriptionTier | None = None,
) -> list[dict[str, Any]]:
    """Return the list of available models for the frontend.

    When tier is provided, only models allowed for that tier are returned.
    """
    if tier is not None:
        from quota.config import get_tier_limits

        allowed_ids = set(get_tier_limits(tier).allowed_model_ids)
    else:
        allowed_ids = None

    return [
        {
            "id": mid,
            "display_name": info["display_name"],
            "description": info["description"],
            "is_default": info.get("is_default", False),
            "locked": allowed_ids is not None and mid not in allowed_ids,
        }
        for mid, info in ALLOWED_MODELS.items()
    ]
