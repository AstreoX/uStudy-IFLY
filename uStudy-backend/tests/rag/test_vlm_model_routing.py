from unittest.mock import AsyncMock

import httpx
import pytest

from config import Settings
from rag.vlm_processor import VLMProcessor


@pytest.mark.parametrize("model,base,key", [
    ("deepseek/deepseek-v4.1-flash", "https://openrouter.ai/api/v1", "test-openrouter"),
    ("qwen3.6-plus", "https://dashscope.aliyuncs.com/compatible-mode/v1", "test-dashscope"),
])
async def test_visual_request_uses_matching_provider(monkeypatch, model, base, key):
    settings = Settings(
        _env_file=None, vlm_model=model,
        openrouter_api_key="test-openrouter", openrouter_bridge_url="",
        dashscope_api_key="test-dashscope",
    )
    monkeypatch.setattr("rag.vlm_processor.get_settings", lambda: settings)
    monkeypatch.setattr("agents.llm.client.get_settings", lambda: settings)
    post = AsyncMock(return_value=httpx.Response(
        200, json={"choices": [{"message": {"content": "BINARY TREE"}}]},
        request=httpx.Request("POST", base + "/chat/completions"),
    ))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    monkeypatch.setattr("rag.vlm_processor.record_ai_request_log", AsyncMock())
    result = await VLMProcessor().ocr_page_image(b"\x89PNG\r\n\x1a\n")
    assert result == "BINARY TREE"
    assert post.call_args.args[0] == base + "/chat/completions"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer " + key
    assert post.call_args.kwargs["json"]["model"] == model
