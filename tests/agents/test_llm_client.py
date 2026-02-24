"""OpenRouter LLM 客户端单元测试"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from agents.llm.client import OpenRouterClient, OpenRouterClientError


class TestOpenRouterClientInit:
    """客户端初始化测试"""

    def test_init_without_api_key_raises_error(self):
        """测试未配置 API Key 时抛出错误"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openrouter_api_key="",
                openrouter_base_url="https://openrouter.ai/api/v1",
                openrouter_model="minimax/minimax-m2.5",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            with pytest.raises(
                OpenRouterClientError, match="OPENROUTER_API_KEY 未配置"
            ):
                OpenRouterClient()

    def test_init_with_valid_api_key(self):
        """测试配置有效 API Key 时正常初始化"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openrouter_api_key="sk-or-v1-test-key",
                openrouter_base_url="https://openrouter.ai/api/v1",
                openrouter_model="minimax/minimax-m2.5",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            client = OpenRouterClient()
            assert client.api_key == "sk-or-v1-test-key"
            assert client.model == "minimax/minimax-m2.5"
            assert client.timeout == 120


class TestOpenRouterClientHeaders:
    """请求头测试"""

    @pytest.fixture
    def client(self) -> OpenRouterClient:
        """创建客户端实例"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openrouter_api_key="sk-or-v1-test-key",
                openrouter_base_url="https://openrouter.ai/api/v1",
                openrouter_model="minimax/minimax-m2.5",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            return OpenRouterClient()

    def test_request_headers_correct(self, client: OpenRouterClient):
        """测试请求头正确"""
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer sk-or-v1-test-key"
        assert headers["HTTP-Referer"] == "https://ustudy.app"
        assert headers["X-Title"] == "uStudy"
        assert headers["Content-Type"] == "application/json"


class TestOpenRouterClientComplete:
    """非流式补全测试"""

    @pytest_asyncio.fixture
    async def client(self) -> OpenRouterClient:
        """创建客户端实例"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openrouter_api_key="sk-or-v1-test-key",
                openrouter_base_url="https://openrouter.ai/api/v1",
                openrouter_model="minimax/minimax-m2.5",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            return OpenRouterClient()

    def _create_mock_response(self, status_code: int, json_data: dict) -> httpx.Response:
        """创建带有 request 的 mock response"""
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        response = httpx.Response(status_code, json=json_data, request=request)
        return response

    @pytest.mark.asyncio
    async def test_successful_api_call(self, client: OpenRouterClient):
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
    async def test_request_body_format(self, client: OpenRouterClient):
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

            assert request_json["model"] == "minimax/minimax-m2.5"
            assert request_json["messages"] == [{"role": "user", "content": "test"}]
            assert request_json["temperature"] == 0.5
            assert request_json["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, client: OpenRouterClient):
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
    async def test_retry_on_500_error(self, client: OpenRouterClient):
        """测试服务器错误重试"""
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
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
    async def test_max_retries_exceeded(self, client: OpenRouterClient):
        """测试超过最大重试次数"""

        async def mock_post_always_timeout(*args, **kwargs):
            raise httpx.TimeoutException("Connection timeout")

        with patch("httpx.AsyncClient.post", side_effect=mock_post_always_timeout):
            with pytest.raises(httpx.TimeoutException):
                await client.complete(messages=[{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_retry_on_400_error(self, client: OpenRouterClient):
        """测试 400 错误会触发重试（HTTPStatusError 触发重试机制）"""
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
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

            # 400 错误也会触发重试（根据 tenacity 配置）
            assert call_count == 3  # 最大重试次数

    @pytest.mark.asyncio
    async def test_invalid_api_key_401(self, client: OpenRouterClient):
        """测试无效 API Key 返回 401"""
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
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
    async def test_rate_limit_429(self, client: OpenRouterClient):
        """测试限流处理 429"""
        request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
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
    async def test_malformed_response(self, client: OpenRouterClient):
        """测试响应格式错误"""
        malformed_response = self._create_mock_response(
            200,
            {"unexpected": "format"},
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = malformed_response

            with pytest.raises(KeyError):
                await client.complete(messages=[{"role": "user", "content": "test"}])


class TestOpenRouterClientStreamComplete:
    """流式补全测试"""

    @pytest_asyncio.fixture
    async def client(self) -> OpenRouterClient:
        """创建客户端实例"""
        with patch("agents.llm.client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                openrouter_api_key="sk-or-v1-test-key",
                openrouter_base_url="https://openrouter.ai/api/v1",
                openrouter_model="minimax/minimax-m2.5",
                llm_timeout_seconds=120,
                llm_max_retries=3,
            )
            return OpenRouterClient()

    @pytest.mark.asyncio
    async def test_stream_complete_yields_content(self, client: OpenRouterClient):
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
    async def test_stream_complete_request_format(self, client: OpenRouterClient):
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
