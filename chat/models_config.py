"""Chat Models Configuration - Allowed models registry and helpers"""

from typing import Any

ALLOWED_MODELS: dict[str, dict[str, Any]] = {
    "minimax-m2.5": {
        "openrouter_id": "minimax/minimax-m2.5",
        "display_name": "MiniMax M2.5",
        "description": "快速响应，适合日常对话",
        "is_default": True,
    },
    "qwen3-max-thinking": {
        "openrouter_id": "qwen/qwen3-max-thinking",
        "display_name": "Qwen3 Max Thinking",
        "description": "更强推理能力，适合复杂问题",
    },
    "glm-5": {
        "openrouter_id": "z-ai/glm-5",
        "display_name": "GLM 5",
        "description": "智谱最新模型，低幻觉率",
    },
}

DEFAULT_MODEL_ID = "minimax-m2.5"


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


def get_available_models() -> list[dict[str, Any]]:
    """Return the list of available models for the frontend."""
    return [
        {
            "id": mid,
            "display_name": info["display_name"],
            "description": info["description"],
            "is_default": info.get("is_default", False),
        }
        for mid, info in ALLOWED_MODELS.items()
    ]
