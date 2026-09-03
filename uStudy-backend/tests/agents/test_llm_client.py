"""DashScope LLM 客户端单元测试"""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio


def _load_llm_client_module():
    """Load client.py directly without importing agents.__init__ heavy deps."""
    if "agents" not in sys.modules:
        agents_mod = types.ModuleType("agents")
        agents_mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules["agents"] = agents_mod
    if "agents.llm" not in sys.modules:
        llm_mod = types.ModuleType("agents.llm")
        llm_mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules["agents.llm"] = llm_mod

    if "db" not in sys.modules:
        sys.modules["db"] = types.ModuleType("db")
    if "db.database" not in sys.modules:
        db_mod = types.ModuleType("db.database")

        class _Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

        db_mod.get_scoped_session = lambda: _Session()  # type: ignore[attr-defined]
        sys.modules["db.database"] = db_mod

    if "usage" not in sys.modules:
        usage_mod = types.ModuleType("usage")
        usage_mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules["usage"] = usage_mod
    if "usage.metering" not in sys.modules:
        usage_metering_mod = types.ModuleType("usage.metering")

        class _UsageContext:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class _UsageResult:
            def to_dict(self):
                return {}

        async def _record_and_charge_usage(**kwargs):
            return None

        usage_metering_mod.UsageContext = _UsageContext  # type: ignore[attr-defined]
        usage_metering_mod.UsageResult = _UsageResult  # type: ignore[attr-defined]
        usage_metering_mod.record_and_charge_usage = _record_and_charge_usage  # type: ignore[attr-defined]
        sys.modules["usage.metering"] = usage_metering_mod
    if "usage.models" not in sys.modules:
        usage_models_mod = types.ModuleType("usage.models")

        class _AiRequestLog:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        usage_models_mod.AiRequestLog = _AiRequestLog  # type: ignore[attr-defined]
        sys.modules["usage.models"] = usage_models_mod

    module_path = Path(__file__).parent.parent.parent / "agents" / "llm" / "client.py"
    spec = importlib.util.spec_from_file_location("agents.llm.client", module_path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agents.llm.client"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_llm_client_mod = _load_llm_client_module()
LLMClient = _llm_client_mod.LLMClient
LLMClientError = _llm_client_mod.LLMClientError


class TestLLMClientInit:
    """客户端初始化测试"""

    def test_init_without_api_key_raises_error(self):
        """测试未配置 API Key 时抛出错误"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                llm_default_model="minimax/minimax-m2.5",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            with pytest.raises(
                LLMClientError, match="OPENROUTER_API_KEY 未配置"
            ):
                LLMClient()

    def test_init_with_valid_api_key(self):
        """测试配置有效 API Key 时正常初始化"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-test-key",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                llm_default_model="qwen3.6-plus",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            client = LLMClient()
            assert client.api_key == "sk-test-key"
            assert client.model == "qwen3.6-plus"
            assert client.timeout == 120

    def test_openrouter_model_uses_openrouter_credentials(self):
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-dashscope",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                openrouter_api_key="sk-or-test",
                openrouter_base_url="https://openrouter.ai/api/v1",
                openrouter_bridge_url="",
                llm_default_model="z-ai/glm-5.3-flash",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )

            client = LLMClient()

            assert client.model == "z-ai/glm-5.3-flash"
            assert client.base_url == "https://openrouter.ai/api/v1"
            assert client.api_key == "sk-or-test"
            assert client.is_openrouter is True

    def test_minimax_model_uses_minimax_credentials(self):
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-dashscope",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                minimax_api_key="sk-minimax-test",
                minimax_base_url="https://api.minimaxi.com/v1",
                llm_default_model="MiniMax-M2.7-highspeed",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )

            client = LLMClient()

            assert client.base_url == "https://api.minimaxi.com/v1"
            assert client.api_key == "sk-minimax-test"
            assert client.is_minimax is True
            assert client.is_openrouter is False

    def test_minimax_model_requires_its_own_api_key(self):
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-dashscope",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                minimax_api_key="",
                minimax_base_url="https://api.minimaxi.com/v1",
                llm_default_model="MiniMax-M2.7-highspeed",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )

            with pytest.raises(LLMClientError, match="MINIMAX_API_KEY 未配置"):
                LLMClient()

    def test_init_with_timeout_override(self):
        """测试可为长任务单独覆盖超时时间"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-test-key",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                llm_default_model="qwen3.6-plus",
                llm_timeout_seconds=20,
                llm_max_retries=3,
            )
            client = LLMClient(timeout_seconds=300)
            assert client.timeout == 300

    def test_stream_timeout_uses_long_read_timeout(self):
        """测试流式调用使用独立的长读超时配置"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-test-key",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                llm_default_model="qwen3.6-plus",
                llm_timeout_seconds=60,
                llm_stream_connect_timeout_seconds=10,
                llm_stream_read_timeout_seconds=180,
                llm_stream_write_timeout_seconds=30,
                llm_stream_pool_timeout_seconds=30,
                llm_max_retries=3,
            )
            client = LLMClient()
            timeout = client._get_stream_client_kwargs()["timeout"]

            assert timeout.connect == 10
            assert timeout.read == 180
            assert timeout.write == 30
            assert timeout.pool == 30


class TestLLMClientHeaders:
    """请求头测试"""

    @pytest.fixture
    def client(self) -> LLMClient:
        """创建客户端实例"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-test-key",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                llm_default_model="qwen3.6-plus",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            return LLMClient()

    def test_request_headers_correct(self, client: LLMClient):
        """测试请求头正确"""
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer sk-test-key"
        assert "HTTP-Referer" not in headers
        assert "X-Title" not in headers
        assert headers["Content-Type"] == "application/json"


class TestLLMClientComplete:
    """非流式补全测试"""

    @pytest_asyncio.fixture
    async def client(self) -> LLMClient:
        """创建客户端实例"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-test-key",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                llm_default_model="qwen3.6-plus",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            return LLMClient()

    def _create_mock_response(self, status_code: int, json_data: dict) -> httpx.Response:
        """创建带有 request 的 mock response"""
        request = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        response = httpx.Response(status_code, json=json_data, request=request)
        return response

    @pytest.mark.asyncio
    async def test_successful_api_call(self, client: LLMClient):
        """测试成功的 API 调用"""
        mock_response = self._create_mock_response(
            200,
            {"choices": [{"message": {"content": "Hello, World!"}}]},
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await client.complete(
                messages=[{"role": "user", "content": "Say hello"}]
            )

            assert result == "Hello, World!"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_body_format(self, client: LLMClient):
        """测试请求体格式"""
        mock_response = self._create_mock_response(
            200,
            {"choices": [{"message": {"content": "response"}}]},
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await client.complete(
                messages=[{"role": "user", "content": "test"}],
                temperature=0.5,
                max_tokens=2048,
            )

            call_kwargs = mock_post.call_args
            request_json = call_kwargs.kwargs["json"]

            assert request_json["model"] == "qwen3.6-plus"
            assert request_json["messages"] == [{"role": "user", "content": "test"}]
            assert request_json["temperature"] == 0.5
            assert request_json["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_minimax_request_splits_reasoning_and_omits_dashscope_flag(self):
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-dashscope",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                minimax_api_key="sk-minimax-test",
                minimax_base_url="https://api.minimaxi.com/v1",
                llm_default_model="MiniMax-M2.7-highspeed",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            client = LLMClient()

        response = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "response"}}]},
            request=httpx.Request(
                "POST", "https://api.minimaxi.com/v1/chat/completions"
            ),
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = response

            await client.complete(
                messages=[{"role": "user", "content": "test"}],
                enable_thinking=False,
            )

            request_json = mock_post.call_args.kwargs["json"]
            assert request_json["reasoning_split"] is True
            assert "enable_thinking" not in request_json

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, client: LLMClient):
        """测试超时重试"""
        mock_response = self._create_mock_response(
            200,
            {"choices": [{"message": {"content": "success after retry"}}]},
        )

        call_count = 0

        async def mock_post_with_timeout(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Connection timeout")
            return mock_response

        with patch("httpx.AsyncClient.post", side_effect=mock_post_with_timeout):
            result = await client.complete(
                messages=[{"role": "user", "content": "test"}]
            )

            assert result == "success after retry"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_500_error(self, client: LLMClient):
        """测试服务器错误重试"""
        request = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        error_response = httpx.Response(500, text="Internal Server Error", request=request)
        success_response = self._create_mock_response(
            200,
            {"choices": [{"message": {"content": "success"}}]},
        )

        call_count = 0

        async def mock_post_with_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.HTTPStatusError(
                    "Server Error", request=request, response=error_response
                )
            return success_response

        with patch("httpx.AsyncClient.post", side_effect=mock_post_with_error):
            result = await client.complete(
                messages=[{"role": "user", "content": "test"}]
            )

            assert result == "success"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, client: LLMClient):
        """测试超过最大重试次数"""

        async def mock_post_always_timeout(*args, **kwargs):
            raise httpx.TimeoutException("Connection timeout")

        with patch("httpx.AsyncClient.post", side_effect=mock_post_always_timeout):
            with pytest.raises(httpx.TimeoutException):
                await client.complete(messages=[{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_no_retry_on_400_error(self, client: LLMClient):
        """测试 400 请求错误不会重试"""
        request = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        error_response = httpx.Response(400, text="Bad Request", request=request)

        call_count = 0

        async def mock_post_400(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.HTTPStatusError(
                "Bad Request", request=request, response=error_response
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post_400):
            with pytest.raises(httpx.HTTPStatusError):
                await client.complete(messages=[{"role": "user", "content": "test"}])

            assert call_count == 1

    @pytest.mark.asyncio
    async def test_invalid_api_key_401(self, client: LLMClient):
        """测试无效 API Key 返回 401"""
        request = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        error_response = httpx.Response(401, text="Unauthorized", request=request)

        async def mock_post_401(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "Unauthorized", request=request, response=error_response
            )

        with patch("httpx.AsyncClient.post", side_effect=mock_post_401):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.complete(messages=[{"role": "user", "content": "test"}])

            assert exc_info.value.response.status_code == 401

    @pytest.mark.asyncio
    async def test_rate_limit_429(self, client: LLMClient):
        """测试限流处理 429"""
        request = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
        rate_limit_response = httpx.Response(429, text="Rate Limit Exceeded", request=request)
        success_response = self._create_mock_response(
            200,
            {"choices": [{"message": {"content": "success"}}]},
        )

        call_count = 0

        async def mock_post_rate_limit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.HTTPStatusError(
                    "Rate Limit",
                    request=request,
                    response=rate_limit_response,
                )
            return success_response

        with patch("httpx.AsyncClient.post", side_effect=mock_post_rate_limit):
            result = await client.complete(
                messages=[{"role": "user", "content": "test"}]
            )

            assert result == "success"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_malformed_response(self, client: LLMClient):
        """测试响应格式错误"""
        malformed_response = self._create_mock_response(
            200,
            {"unexpected": "format"},
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = malformed_response

            with pytest.raises(Exception, match="LLM 响应缺少 choices"):
                await client.complete(messages=[{"role": "user", "content": "test"}])


class TestLLMClientStreamComplete:
    """流式补全测试"""

    @pytest_asyncio.fixture
    async def client(self) -> LLMClient:
        """创建客户端实例"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                dashscope_api_key="sk-test-key",
                dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                llm_default_model="qwen3.6-plus",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            return LLMClient()

    @pytest.mark.asyncio
    async def test_stream_complete_yields_content(self, client: LLMClient):
        """测试流式补全产生内容"""
        # 模拟 SSE 流式响应
        stream_data = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": " World"}}]}',
            'data: {"choices": [{"delta": {"content": "!"}}]}',
            "data: [DONE]",
        ]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        async def mock_aiter_lines():
            for line in stream_data:
                yield line

        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient.stream", return_value=mock_stream_context):
            chunks = []
            async for chunk in client.stream_complete(
                messages=[{"role": "user", "content": "test"}]
            ):
                chunks.append(chunk)

            assert chunks == ["Hello", " World", "!"]

    @pytest.mark.asyncio
    async def test_stream_complete_request_format(self, client: LLMClient):
        """测试流式请求格式包含 stream=True"""
        stream_data = ["data: [DONE]"]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        async def mock_aiter_lines():
            for line in stream_data:
                yield line

        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient.stream", return_value=mock_stream_context) as mock_stream:
            async for _ in client.stream_complete(
                messages=[{"role": "user", "content": "test"}]
            ):
                pass

            # 验证 stream=True 在请求中
            call_kwargs = mock_stream.call_args
            request_json = call_kwargs.kwargs["json"]
            assert request_json["stream"] is True

    @pytest.mark.asyncio
    async def test_stream_complete_skips_usage_chunk_without_choices(self, client: LLMClient):
        """测试 include_usage 的空 choices 片段不会中断流式生成"""
        stream_data = [
            'data: {"choices": [{"delta": {"content": "<html>"}}]}',
            'data: {"choices": []}',
            (
                'data: {"usage": {"prompt_tokens": 1, "completion_tokens": 2, '
                '"total_tokens": 3}, "choices": []}'
            ),
            'data: {"choices": [{"delta": {"content": "</html>"}}]}',
            "data: [DONE]",
        ]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        async def mock_aiter_lines():
            for line in stream_data:
                yield line

        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient.stream", return_value=mock_stream_context):
            chunks = []
            async for chunk in client.stream_complete(
                messages=[{"role": "user", "content": "test"}]
            ):
                chunks.append(chunk)

            assert chunks == ["<html>", "</html>"]

    @pytest.mark.asyncio
    async def test_stream_complete_no_retry_on_400_error(self, client: LLMClient):
        """测试流式 400 请求错误不会重试"""
        request = httpx.Request(
            "POST",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        error_response = httpx.Response(400, text="Bad Request", request=request)
        status_error = httpx.HTTPStatusError(
            "Bad Request",
            request=request,
            response=error_response,
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=status_error)

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient.stream", return_value=mock_stream_context) as mock_stream:
            with pytest.raises(httpx.HTTPStatusError):
                async for _ in client.stream_complete(
                    messages=[{"role": "user", "content": "test"}]
                ):
                    pass

            assert mock_stream.call_count == 1
