"""Chat choices must not mutate defaults used by concurrent or background work."""

import pytest

from agents.llm.client import LLMClient
from chat.models_config import (
    DEFAULT_MODEL_ID,
    get_available_models,
    get_model_id,
    get_supports_thinking,
    validate_model_id,
)
from config import Settings
from db.models import SubscriptionTier
from teacher.presentations.gateway import _presentation_llm_client
from teacher.presentations.schemas import GatewayLLMRequest


@pytest.mark.parametrize("tier", list(SubscriptionTier))
def test_both_chat_models_available_with_deepseek_default(tier):
    models = get_available_models(tier)
    assert {m["id"] for m in models} == {"deepseek-v4.1-flash", "glm-5.3-flash"}
    assert all(not m["locked"] for m in models)
    assert [m["id"] for m in models if m["is_default"]] == [DEFAULT_MODEL_ID]
    assert DEFAULT_MODEL_ID == "deepseek-v4.1-flash"


@pytest.mark.parametrize(
    "choice,provider",
    [
        (None, "deepseek/deepseek-v4.1-flash"),
        ("unknown", "deepseek/deepseek-v4.1-flash"),
        ("deepseek-v4.1-flash", "deepseek/deepseek-v4.1-flash"),
        ("glm-5.3-flash", "z-ai/glm-5.3-flash"),
        ("kimi-k2.5", "z-ai/glm-5.3-flash"),
    ],
)
def test_chat_model_resolution(choice, provider):
    assert get_model_id(choice) == provider
    if choice not in (None, "unknown"):
        assert validate_model_id(choice)
        assert get_supports_thinking(choice)
    assert not validate_model_id("unknown")


def test_chat_switch_is_request_scoped_and_ppt_keeps_its_model(monkeypatch):
    monkeypatch.delenv("LLM_DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("PRESENTATION_LLM_MODEL", raising=False)
    settings = Settings(
        _env_file=None,
        openrouter_api_key="test-openrouter",
        openrouter_bridge_url="",
        minimax_api_key="test-minimax",
    )
    before = settings.model_dump()
    monkeypatch.setattr("agents.llm.client.get_settings", lambda: settings)
    monkeypatch.setattr("teacher.presentations.gateway.get_settings", lambda: settings)

    default_chat = LLMClient()
    glm_chat = LLMClient(model_override=get_model_id("glm-5.3-flash"))
    next_chat = LLMClient(model_override=get_model_id(None))
    background = LLMClient(model_override=settings.background_llm_model)
    ppt = _presentation_llm_client(request=GatewayLLMRequest(messages=[]), context=None)

    assert default_chat.model == next_chat.model == "deepseek/deepseek-v4.1-flash"
    assert default_chat.base_url == "https://openrouter.ai/api/v1"
    assert glm_chat.model == "z-ai/glm-5.3-flash"
    assert ppt.model == background.model == "deepseek/deepseek-v4.1-flash"
    for field, value in settings.model_dump().items():
        if field.endswith("_model") and field not in {
            "embedding_model", "rag_rerank_model", "image_generation_model"
        }:
            assert value == "deepseek/deepseek-v4.1-flash", field
    assert settings.model_dump() == before

    settings.presentation_llm_model = "dedicated/presentation-model"
    ppt = _presentation_llm_client(request=GatewayLLMRequest(messages=[]), context=None)
    assert ppt.model == "dedicated/presentation-model"
    explicit = _presentation_llm_client(
        request=GatewayLLMRequest(messages=[], model="explicit/task-model"), context=None
    )
    assert explicit.model == "explicit/task-model"
