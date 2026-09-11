"""Chat Models Configuration - Allowed models registry and helpers"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from db.models import SubscriptionTier

LEGACY_MODEL_IDS: dict[str, str] = {
    "kimi-k2.5": "glm-5.3-flash",
    "mimo-v2-omni": "glm-5.3-flash",
    "qwen3.6-plus": "glm-5.3-flash",
    "glm-5v-turbo": "glm-5.3-flash",
    "gemini-3.1-pro": "glm-5.3-flash",
}

ALLOWED_MODELS: dict[str, dict[str, Any]] = {
    "deepseek-v4.1-flash": {
        "model_id": "deepseek/deepseek-v4.1-flash",
        "display_name": "DeepSeek V4.1 Flash",
        "description": "OpenRouter 多模态推理模型",
        "is_default": True,
        "max_output_tokens": 65536,
        "supports_thinking": True,
    },
    "glm-5.3-flash": {
        "model_id": "z-ai/glm-5.3-flash",
        "display_name": "GLM 5.3 Flash",
        "description": "OpenRouter 多模态推理模型",
        "is_default": False,
        "max_output_tokens": 65536,
        "supports_thinking": True,
    },
}

DEFAULT_MODEL_ID = "deepseek-v4.1-flash"


def normalize_model_id(model_id: str | None) -> str | None:
    """Map legacy model IDs to the current canonical model ID."""
    if model_id is None:
        return None
    return LEGACY_MODEL_IDS.get(model_id, model_id)


def get_model_id(model_id: str | None) -> str:
    """Resolve a model_id to the configured provider model string.

    Falls back to the default model when model_id is None or not found.
    """
    model_id = normalize_model_id(model_id)
    if model_id and model_id in ALLOWED_MODELS:
        return ALLOWED_MODELS[model_id]["model_id"]
    return ALLOWED_MODELS[DEFAULT_MODEL_ID]["model_id"]


def get_max_output_tokens(model_id: str | None) -> int:
    """Return max_output_tokens for a model, defaulting to 65536."""
    model_id = normalize_model_id(model_id)
    if model_id and model_id in ALLOWED_MODELS:
        return ALLOWED_MODELS[model_id].get("max_output_tokens", 65536)
    return ALLOWED_MODELS[DEFAULT_MODEL_ID].get("max_output_tokens", 65536)


def get_supports_thinking(model_id: str | None) -> bool:
    """Check whether a model supports the reasoning/thinking parameter."""
    model_id = normalize_model_id(model_id)
    if model_id and model_id in ALLOWED_MODELS:
        return ALLOWED_MODELS[model_id].get("supports_thinking", False)
    return False


def validate_model_id(model_id: str) -> bool:
    """Check whether a model_id is in the allowed set."""
    return normalize_model_id(model_id) in ALLOWED_MODELS


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
            "supports_thinking": info.get("supports_thinking", False),
            "locked": allowed_ids is not None and mid not in allowed_ids,
        }
        for mid, info in ALLOWED_MODELS.items()
    ]
