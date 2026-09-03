"""DashScope LLM 异步客户端"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator

import httpx
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from config import get_settings
from db.database import get_scoped_session
from usage.metering import UsageContext, UsageResult, record_and_charge_usage
from usage.models import AiRequestLog

logger = logging.getLogger(__name__)


# 可重试的网络异常类型。HTTP 状态码需要单独判断，避免 400/401/403/422
# 这类确定性请求错误被重复发送，放大流式等待时间。
RETRYABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,  # 服务器意外断开连接
)
RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}


# Module-level shared httpx client pool (keyed by base_url:proxy_url)
_shared_clients: dict[str, httpx.AsyncClient] = {}


def _coerce_setting_number(settings: Any, name: str, default: float) -> float:
    value = getattr(settings, name, default)
    return float(value) if isinstance(value, (int, float)) else default


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code in RETRYABLE_HTTP_STATUS_CODES or status_code >= 500
    return False


def _retry_reason(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"http_{exc.response.status_code}"
    return type(exc).__name__


def _messages_chars(messages: list[dict[str, Any]]) -> int:
    return sum(len(str(message.get("content", ""))) for message in messages)


def _tool_result_chars(messages: list[dict[str, Any]]) -> int:
    return sum(
        len(str(message.get("content", "")))
        for message in messages
        if message.get("role") == "tool"
    )


class LLMClientError(Exception):
    """DashScope LLM 客户端配置错误"""

    pass


@dataclass
class ToolCall:
    """工具调用结果"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TokenUsage:
    """Token 用量信息"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class CompletionWithToolsResult:
    """带工具调用的补全结果"""

    content: str | None
    tool_calls: list[ToolCall]
    finish_reason: str
    usage: TokenUsage | None = None
    billing: UsageResult | None = None


@dataclass
class CompletionResult:
    """普通补全结果"""

    content: str
    usage: TokenUsage | None = None
    billing: UsageResult | None = None
    # Providers use ``length`` when max_tokens truncated the response.  Keep
    # this metadata so callers that require structured output can recover
    # without guessing from the returned text.
    finish_reason: str = "stop"


class LLMClient:
    """DashScope API 异步客户端"""

    def __init__(
        self,
        model_override: str | None = None,
        timeout_seconds: float | None = None,
        usage_context: UsageContext | None = None,
        base_url_override: str | None = None,
        api_key_override: str | None = None,
    ) -> None:
        self.settings = get_settings()

        self.model = model_override or self.settings.llm_default_model
        normalized_model = self.model.strip().lower()
        self.is_minimax = normalized_model.startswith("minimax-")
        openrouter_key = getattr(self.settings, "openrouter_api_key", "")
        use_openrouter = (
            "/" in self.model
            and isinstance(openrouter_key, str)
            and bool(openrouter_key)
        )
        if base_url_override or api_key_override:
            self.base_url = (base_url_override or self.settings.dashscope_base_url).rstrip("/")
            self.api_key = api_key_override or self.settings.dashscope_api_key
        elif self.is_minimax:
            self.base_url = getattr(
                self.settings, "minimax_base_url", "https://api.minimaxi.com/v1"
            ).rstrip("/")
            self.api_key = getattr(self.settings, "minimax_api_key", "")
        elif use_openrouter:
            self.base_url = (
                getattr(self.settings, "openrouter_bridge_url", "")
                or getattr(self.settings, "openrouter_base_url", "https://openrouter.ai/api/v1")
            ).rstrip("/")
            self.api_key = openrouter_key
        else:
            self.base_url = self.settings.dashscope_base_url.rstrip("/")
            self.api_key = self.settings.dashscope_api_key
        if not self.api_key:
            if self.is_minimax:
                missing = "MINIMAX_API_KEY"
            elif "/" in self.model:
                missing = "OPENROUTER_API_KEY"
            else:
                missing = "DASHSCOPE_API_KEY"
            raise LLMClientError(f"{missing} 未配置，请在 .env 文件中设置")
        self.is_openrouter = "openrouter.ai" in self.base_url or use_openrouter
        self.timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else _coerce_setting_number(self.settings, "llm_timeout_seconds", 60)
        )
        self.stream_timeout = httpx.Timeout(
            connect=_coerce_setting_number(
                self.settings, "llm_stream_connect_timeout_seconds", 10
            ),
            read=_coerce_setting_number(
                self.settings, "llm_stream_read_timeout_seconds", 600
            ),
            write=_coerce_setting_number(
                self.settings, "llm_stream_write_timeout_seconds", 30
            ),
            pool=_coerce_setting_number(
                self.settings, "llm_stream_pool_timeout_seconds", 30
            ),
        )
        self.max_retries = self.settings.llm_max_retries
        proxy_url = getattr(self.settings, "llm_proxy_url", "")
        self.proxy_url = proxy_url if isinstance(proxy_url, str) and proxy_url else None
        self.usage_context = usage_context

    def _get_client_kwargs(self) -> dict[str, Any]:
        """获取 httpx.AsyncClient 的配置参数"""
        kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        return kwargs

    def _get_stream_client_kwargs(self) -> dict[str, Any]:
        """获取流式 httpx.AsyncClient 的配置参数。"""
        kwargs: dict[str, Any] = {"timeout": self.stream_timeout}
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        return kwargs

    def _get_shared_client(self) -> httpx.AsyncClient:
        """Get or create a shared httpx client with connection pooling."""
        key = f"normal:{self.base_url}:{self.proxy_url}:{self.timeout}"
        client = _shared_clients.get(key)
        if client is None or client.is_closed:
            _shared_clients[key] = httpx.AsyncClient(
                **self._get_client_kwargs(),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30,
                ),
            )
        return _shared_clients[key]

    def _get_stream_shared_client(self) -> httpx.AsyncClient:
        """Get or create a shared client tuned for SSE streaming."""
        key = f"stream:{self.base_url}:{self.proxy_url}:{self.stream_timeout!r}"
        client = _shared_clients.get(key)
        if client is None or client.is_closed:
            _shared_clients[key] = httpx.AsyncClient(
                **self._get_stream_client_kwargs(),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30,
                ),
            )
        return _shared_clients[key]

    def _get_headers(self) -> dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _resolve_usage_context(
        self,
        usage_context: UsageContext | None,
    ) -> UsageContext | None:
        return usage_context or self.usage_context

    async def _preflight_usage_context(
        self,
        usage_context: UsageContext | None,
    ) -> None:
        context = self._resolve_usage_context(usage_context)
        if not context or not context.billable or not context.user_id:
            return

    async def _record_usage_if_needed(
        self,
        *,
        usage_context: UsageContext | None,
        usage: TokenUsage | dict[str, int] | None,
        idempotency_key: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> UsageResult | None:
        return await record_and_charge_usage(
            context=self._resolve_usage_context(usage_context),
            model=self.model,
            usage=usage,
            idempotency_key=idempotency_key,
            extra_metadata=extra_metadata,
        )

    @staticmethod
    def _usage_int(usage: TokenUsage | dict[str, int] | None, key: str) -> int | None:
        if not usage:
            return None
        if isinstance(usage, dict):
            value = usage.get(key)
        else:
            value = getattr(usage, key, None)
        return int(value) if value is not None else None

    @staticmethod
    def _http_status_from_error(error: BaseException | None) -> int | None:
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code
        return None

    async def _record_ai_request_log(
        self,
        *,
        request_kind: str,
        status: str,
        latency_ms: int | None,
        usage_context: UsageContext | None,
        usage: TokenUsage | dict[str, int] | None = None,
        error: BaseException | None = None,
        http_status_code: int | None = None,
        ttft_ms: int | None = None,
        last_chunk_gap_ms: int | None = None,
        retry_count: int = 0,
        retry_reason: str | None = None,
        message_count: int | None = None,
        context_chars: int | None = None,
        tool_result_chars: int | None = None,
    ) -> None:
        context = self._resolve_usage_context(usage_context)
        error_message = str(error) if error else None
        if error_message and len(error_message) > 2000:
            error_message = error_message[:2000]

        try:
            async with get_scoped_session() as db:
                db.add(
                    AiRequestLog(
                        user_id=getattr(context, "user_id", None),
                        space_id=getattr(context, "space_id", None),
                        conversation_id=getattr(context, "conversation_id", None),
                        model=self.model,
                        base_url=self.base_url,
                        request_kind=request_kind,
                        source_module=getattr(context, "source_module", None),
                        source_operation=getattr(context, "source_operation", None),
                        status=status,
                        http_status_code=http_status_code
                        or self._http_status_from_error(error),
                        error_type=type(error).__name__ if error else None,
                        error_message=error_message,
                        latency_ms=latency_ms,
                        ttft_ms=ttft_ms,
                        last_chunk_gap_ms=last_chunk_gap_ms,
                        retry_count=max(retry_count, 0),
                        retry_reason=retry_reason,
                        prompt_tokens=self._usage_int(usage, "prompt_tokens"),
                        completion_tokens=self._usage_int(usage, "completion_tokens"),
                        total_tokens=self._usage_int(usage, "total_tokens"),
                        message_count=message_count,
                        context_chars=context_chars,
                        tool_result_chars=tool_result_chars,
                    )
                )
                await db.commit()
        except Exception as log_error:
            logger.warning("AI request observability log write failed: %s", log_error)

    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        enable_thinking: bool | None = None,
        usage_context: UsageContext | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        """非流式补全请求，返回文本内容。"""
        result = await self.complete_result(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            usage_context=usage_context,
            idempotency_key=idempotency_key,
        )
        return result.content

    async def complete_result(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        enable_thinking: bool | None = None,
        usage_context: UsageContext | None = None,
        idempotency_key: str | None = None,
    ) -> CompletionResult:
        """
        非流式补全请求

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 温度参数 (0-1)
            max_tokens: 最大生成 token 数
            enable_thinking: 是否开启深度思考（None=使用模型默认行为）

        Returns:
            LLM 生成的文本内容

        Raises:
            httpx.HTTPStatusError: HTTP 请求失败
            httpx.TimeoutException: 请求超时
        """
        t_start = time.monotonic()
        response_status: int | None = None
        attempt_number = 0
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(_is_retryable_exception),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=30),
                reraise=True,
            ):
                with attempt:
                    attempt_number = attempt.retry_state.attempt_number
                    await self._preflight_usage_context(usage_context)
                    client = self._get_shared_client()
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._get_headers(),
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            # DashScope: enable_thinking=True 开启深度思考，False 关闭。
                            # 传 None 时不带此字段，沿用模型默认行为。
                            **(
                                {"enable_thinking": enable_thinking}
                                if enable_thinking is not None and not self.is_minimax
                                else {}
                            ),
                            **({"reasoning_split": True} if self.is_minimax else {}),
                        },
                    )
                    response_status = response.status_code
                    response.raise_for_status()
                    data = response.json()
                    if "error" in data:
                        error_msg = data.get("error", {})
                        error_text = (
                            error_msg.get("message", str(error_msg))
                            if isinstance(error_msg, dict)
                            else str(error_msg)
                        )
                        raise Exception(f"LLM API 错误: {error_text}")
                    if "choices" not in data or not data["choices"]:
                        raise Exception(
                            f"LLM 响应缺少 choices: {json.dumps(data)[:200]}"
                        )
                    content = data["choices"][0]["message"]["content"]
                    usage_data = data.get("usage") or {}
                    usage = (
                        TokenUsage(
                            prompt_tokens=usage_data.get("prompt_tokens", 0),
                            completion_tokens=usage_data.get("completion_tokens", 0),
                            total_tokens=usage_data.get("total_tokens", 0),
                        )
                        if usage_data
                        else None
                    )
                    billing = await self._record_usage_if_needed(
                        usage_context=usage_context,
                        usage=usage,
                        idempotency_key=idempotency_key,
                    )
                    await self._record_ai_request_log(
                        request_kind="complete",
                        status="success",
                        latency_ms=int((time.monotonic() - t_start) * 1000),
                        usage_context=usage_context,
                        usage=usage,
                        http_status_code=response_status,
                        retry_count=max(attempt_number - 1, 0),
                        message_count=len(messages),
                        context_chars=_messages_chars(messages),
                        tool_result_chars=_tool_result_chars(messages),
                    )
                    return CompletionResult(
                        content=content,
                        finish_reason=data["choices"][0].get("finish_reason", "stop"),
                        usage=usage,
                        billing=billing,
                    )
        except Exception as e:
            if isinstance(e, httpx.ConnectError):
                logger.error(
                    "无法连接到 LLM API (%s): %s。请检查网络连接或代理设置 (HTTP_PROXY/HTTPS_PROXY 或 LLM_PROXY_URL)",
                    self.base_url,
                    str(e),
                )
            await self._record_ai_request_log(
                request_kind="complete",
                status="failure",
                latency_ms=int((time.monotonic() - t_start) * 1000),
                usage_context=usage_context,
                error=e,
                http_status_code=response_status,
                retry_count=max(attempt_number - 1, 0),
                message_count=len(messages),
                context_chars=_messages_chars(messages),
                tool_result_chars=_tool_result_chars(messages),
            )
            raise

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 65536,
        usage_context: UsageContext | None = None,
        idempotency_key: str | None = None,
    ) -> CompletionWithToolsResult:
        """
        带工具调用的补全请求

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            tools: 工具定义列表 (OpenAI function calling format)
            temperature: 温度参数 (0-1)
            max_tokens: 最大生成 token 数

        Returns:
            CompletionWithToolsResult 包含内容和工具调用

        Raises:
            httpx.HTTPStatusError: HTTP 请求失败
            httpx.TimeoutException: 请求超时
        """
        t_start = time.monotonic()
        response_status: int | None = None
        attempt_number = 0
        logger.info(
            "开始 LLM 调用: model=%s, messages_count=%d", self.model, len(messages)
        )
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(_is_retryable_exception),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=30),
                reraise=True,
            ):
                with attempt:
                    attempt_number = attempt.retry_state.attempt_number
                    await self._preflight_usage_context(usage_context)
                    async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self._get_headers(),
                            json={
                                "model": self.model,
                                "messages": messages,
                                "tools": tools,
                                "tool_choice": "auto",
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                            },
                        )
                        response_status = response.status_code
                        response.raise_for_status()
                        data = response.json()
                        logger.info("LLM 调用成功: status=%d", response.status_code)

                    if "error" in data:
                        error_msg = data.get("error", {})
                        error_text = (
                            error_msg.get("message", str(error_msg))
                            if isinstance(error_msg, dict)
                            else str(error_msg)
                        )
                        logger.error(
                            "LLM API 错误: %s, 完整响应: %s",
                            error_text,
                            json.dumps(data, ensure_ascii=False)[:1000],
                        )
                        raise Exception(f"LLM API 错误: {error_text}")

                    if "choices" not in data or not data["choices"]:
                        logger.error("LLM 响应格式异常: %s", json.dumps(data)[:500])
                        raise Exception(
                            f"LLM 响应缺少 choices: {json.dumps(data)[:200]}"
                        )

                    choice = data["choices"][0]
                    message = choice["message"]
                    finish_reason = choice.get("finish_reason", "stop")

                    tool_calls: list[ToolCall] = []
                    if "tool_calls" in message and message["tool_calls"]:
                        for tc in message["tool_calls"]:
                            try:
                                arguments = json.loads(tc["function"]["arguments"])
                            except json.JSONDecodeError:
                                arguments = {}
                            tool_calls.append(
                                ToolCall(
                                    id=tc["id"],
                                    name=tc["function"]["name"],
                                    arguments=arguments,
                                )
                            )

                    usage_data = data.get("usage", {})
                    usage = (
                        TokenUsage(
                            prompt_tokens=usage_data.get("prompt_tokens", 0),
                            completion_tokens=usage_data.get("completion_tokens", 0),
                            total_tokens=usage_data.get("total_tokens", 0),
                        )
                        if usage_data
                        else None
                    )
                    billing = await self._record_usage_if_needed(
                        usage_context=usage_context,
                        usage=usage,
                        idempotency_key=idempotency_key,
                    )
                    await self._record_ai_request_log(
                        request_kind="complete_with_tools",
                        status="success",
                        latency_ms=int((time.monotonic() - t_start) * 1000),
                        usage_context=usage_context,
                        usage=usage,
                        http_status_code=response_status,
                        retry_count=max(attempt_number - 1, 0),
                        message_count=len(messages),
                        context_chars=_messages_chars(messages),
                        tool_result_chars=_tool_result_chars(messages),
                    )

                    return CompletionWithToolsResult(
                        content=message.get("content"),
                        tool_calls=tool_calls,
                        finish_reason=finish_reason,
                        usage=usage,
                        billing=billing,
                    )
        except Exception as e:
            if isinstance(e, httpx.HTTPStatusError):
                logger.error(
                    "LLM HTTP 错误: status=%d, response=%s",
                    e.response.status_code,
                    e.response.text[:500],
                )
            elif isinstance(e, httpx.TimeoutException):
                logger.error("LLM 调用超时: timeout=%d", self.timeout)
            elif isinstance(e, httpx.ConnectError):
                logger.error(
                    "无法连接到 LLM API (%s): %s。请检查网络连接或代理设置 (HTTP_PROXY/HTTPS_PROXY 或 LLM_PROXY_URL)",
                    self.base_url,
                    str(e),
                )
            else:
                logger.error("LLM 调用异常: %s: %s", type(e).__name__, str(e))
            await self._record_ai_request_log(
                request_kind="complete_with_tools",
                status="failure",
                latency_ms=int((time.monotonic() - t_start) * 1000),
                usage_context=usage_context,
                error=e,
                http_status_code=response_status,
                retry_count=max(attempt_number - 1, 0),
                message_count=len(messages),
                context_chars=_messages_chars(messages),
                tool_result_chars=_tool_result_chars(messages),
            )
            raise

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        usage_context: UsageContext | None = None,
        idempotency_key: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式补全请求（带重试机制）

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Yields:
            增量文本片段
        """
        last_error: Exception | None = None
        usage = self._resolve_usage_context(usage_context)
        conversation_id = getattr(usage, "conversation_id", None)
        context_chars = _messages_chars(messages)
        last_retry_reason: str | None = None

        for attempt in range(self.max_retries):
            retry_reason = None
            t_attempt_start = time.monotonic()
            first_token_ms: float | None = None
            last_chunk_gap_ms: float | None = None
            last_chunk_at: float | None = None
            response_status: int | None = None
            try:
                await self._preflight_usage_context(usage_context)
                accumulated_usage: dict[str, int] = {}
                async with httpx.AsyncClient(
                    **self._get_stream_client_kwargs()
                ) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers=self._get_headers(),
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "stream": True,
                            "stream_options": {"include_usage": True},
                            **({"reasoning_split": True} if self.is_minimax else {}),
                        },
                    ) as response:
                        response_status = response.status_code
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    data = json.loads(data_str)
                                except json.JSONDecodeError as e:
                                    logger.warning(
                                        "流式响应 JSON 解析失败: %s, line: %s",
                                        e,
                                        data_str[:100],
                                    )
                                    continue

                                if "error" in data:
                                    error_msg = data.get("error", {})
                                    error_text = (
                                        error_msg.get("message", str(error_msg))
                                        if isinstance(error_msg, dict)
                                        else str(error_msg)
                                    )
                                    logger.error("流式 LLM API 错误: %s", error_text)
                                    raise Exception(f"LLM API 错误: {error_text}")

                                choices = data.get("choices", [])
                                if "usage" in data and data["usage"]:
                                    accumulated_usage = data["usage"]

                                if not choices:
                                    # Final usage chunks contain usage but no choices when
                                    # stream_options.include_usage is enabled.
                                    continue

                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    now = time.monotonic()
                                    if first_token_ms is None:
                                        first_token_ms = (now - t_attempt_start) * 1000
                                    if last_chunk_at is not None:
                                        last_chunk_gap_ms = (now - last_chunk_at) * 1000
                                    last_chunk_at = now
                                    yield content

                if accumulated_usage:
                    await self._record_usage_if_needed(
                        usage_context=usage_context,
                        usage=accumulated_usage,
                        idempotency_key=idempotency_key,
                    )
                await self._record_ai_request_log(
                    request_kind="stream",
                    status="success",
                    latency_ms=int((time.monotonic() - t_attempt_start) * 1000),
                    usage_context=usage_context,
                    usage=accumulated_usage or None,
                    http_status_code=response_status,
                    ttft_ms=int(first_token_ms) if first_token_ms is not None else None,
                    last_chunk_gap_ms=(
                        int(last_chunk_gap_ms)
                        if last_chunk_gap_ms is not None
                        else None
                    ),
                    retry_count=attempt,
                    retry_reason=last_retry_reason,
                    message_count=len(messages),
                    context_chars=context_chars,
                    tool_result_chars=_tool_result_chars(messages),
                )

                logger.info(
                    "[LLMStreamMetrics] conversation_id=%s model=%s prompt_tokens=%s "
                    "first_token_ms=%s last_chunk_gap_ms=%s retry_reason=%s "
                    "context_chars=%d tool_result_chars=%d",
                    conversation_id,
                    self.model,
                    (
                        accumulated_usage.get("prompt_tokens")
                        if accumulated_usage
                        else None
                    ),
                    int(first_token_ms) if first_token_ms is not None else None,
                    int(last_chunk_gap_ms) if last_chunk_gap_ms is not None else None,
                    last_retry_reason,
                    context_chars,
                    _tool_result_chars(messages),
                )
                # 成功完成，退出重试循环
                return

            except Exception as e:
                if not _is_retryable_exception(e):
                    logger.error("流式 LLM 调用异常: %s: %s", type(e).__name__, str(e))
                    await self._record_ai_request_log(
                        request_kind="stream",
                        status="failure",
                        latency_ms=int((time.monotonic() - t_attempt_start) * 1000),
                        usage_context=usage_context,
                        error=e,
                        http_status_code=response_status,
                        ttft_ms=(
                            int(first_token_ms) if first_token_ms is not None else None
                        ),
                        last_chunk_gap_ms=(
                            int(last_chunk_gap_ms)
                            if last_chunk_gap_ms is not None
                            else None
                        ),
                        retry_count=attempt,
                        retry_reason=retry_reason,
                        message_count=len(messages),
                        context_chars=context_chars,
                        tool_result_chars=_tool_result_chars(messages),
                    )
                    raise
                last_error = e
                retry_reason = _retry_reason(e)
                last_retry_reason = retry_reason
                if attempt < self.max_retries - 1:
                    wait_time = min(2 * (2**attempt), 30)
                    logger.warning(
                        "流式 LLM 调用失败 (尝试 %d/%d): %s: %s, retry_reason=%s, 将在 %d 秒后重试",
                        attempt + 1,
                        self.max_retries,
                        type(e).__name__,
                        str(e),
                        retry_reason,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "流式 LLM 调用失败，已达最大重试次数: %s: %s, retry_reason=%s",
                        type(e).__name__,
                        str(e),
                        retry_reason,
                    )
                    await self._record_ai_request_log(
                        request_kind="stream",
                        status="failure",
                        latency_ms=int((time.monotonic() - t_attempt_start) * 1000),
                        usage_context=usage_context,
                        error=e,
                        http_status_code=response_status,
                        ttft_ms=(
                            int(first_token_ms) if first_token_ms is not None else None
                        ),
                        last_chunk_gap_ms=(
                            int(last_chunk_gap_ms)
                            if last_chunk_gap_ms is not None
                            else None
                        ),
                        retry_count=attempt,
                        retry_reason=retry_reason,
                        message_count=len(messages),
                        context_chars=context_chars,
                        tool_result_chars=_tool_result_chars(messages),
                    )
                    raise

        if last_error:
            raise last_error

    async def stream_complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 65536,
        enable_thinking: bool | None = None,
        usage_context: UsageContext | None = None,
        idempotency_key: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        流式带工具调用的补全请求（带重试机制）

        Args:
            messages: 消息列表
            tools: 工具定义列表 (OpenAI function calling format)
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Yields:
            字典事件:
            - {"type": "content", "content": "增量文本"}
            - {"type": "tool_call_start", "id": "...", "name": "..."}
            - {"type": "tool_call_end", "id": "...", "name": "...", "arguments": {...}}
            - {"type": "done", "finish_reason": "stop|tool_calls"}
        """
        logger.info(
            "开始流式 LLM 调用: model=%s, messages_count=%d", self.model, len(messages)
        )

        last_error: Exception | None = None
        usage = self._resolve_usage_context(usage_context)
        conversation_id = getattr(usage, "conversation_id", None)
        context_chars = _messages_chars(messages)
        tool_context_chars = _tool_result_chars(messages)
        last_retry_reason: str | None = None

        for attempt in range(self.max_retries):
            t_attempt_start = time.monotonic()
            first_token_ms: float | None = None
            last_chunk_gap_ms: float | None = None
            last_chunk_at: float | None = None
            retry_reason = None
            response_status: int | None = None
            logger.info(
                f"[Perf] LLM attempt {attempt+1}: model={self.model}, base_url={self.base_url}"
            )

            try:
                await self._preflight_usage_context(usage_context)
                client = self._get_stream_shared_client()
                t_conn = time.monotonic()
                logger.info(
                    f"[Perf] httpx client ready: {(t_conn-t_attempt_start)*1000:.0f}ms"
                )

                request_payload = {
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
                if self.is_openrouter:
                    if enable_thinking is not False:
                        request_payload["reasoning"] = {"effort": "medium"}
                elif not self.is_minimax:
                    # DashScope-specific switch.
                    request_payload["enable_thinking"] = enable_thinking is not False

                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=request_payload,
                ) as response:
                    t_response = time.monotonic()
                    response_status = response.status_code
                    logger.info(
                        f"[Perf] HTTP response received (status={response.status_code}): {(t_response-t_conn)*1000:.0f}ms"
                    )
                    response.raise_for_status()

                    # 用于累积工具调用参数
                    tool_calls_buffer: dict[int, dict[str, Any]] = {}
                    # 用于累积 token 用量（OpenRouter 在 finish_reason 之后的单独 chunk 返回）
                    accumulated_usage: dict[str, int] = {}
                    # 记录 finish_reason（可能在 usage 之前到达）
                    final_finish_reason: str | None = None
                    first_sse_line = True

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        if first_sse_line:
                            logger.info(
                                f"[Perf] First SSE line from LLM: {(time.monotonic()-t_response)*1000:.0f}ms"
                            )
                            first_sse_line = False

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError as e:
                            logger.warning(
                                "流式响应 JSON 解析失败: %s, line: %s",
                                e,
                                data_str[:100],
                            )
                            continue

                        if "error" in data:
                            error_msg = data.get("error", {})
                            error_text = (
                                error_msg.get("message", str(error_msg))
                                if isinstance(error_msg, dict)
                                else str(error_msg)
                            )
                            logger.error("流式 LLM API 错误: %s", error_text)
                            raise Exception(f"LLM API 错误: {error_text}")

                        choices = data.get("choices", [])

                        # 检查 usage 字段（OpenRouter 在 finish_reason 之后的单独 chunk 返回）
                        if "usage" in data and data["usage"]:
                            accumulated_usage = data["usage"]

                        if not choices:
                            continue

                        choice = choices[0]
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason")
                        has_stream_payload = bool(
                            delta.get("content")
                            or delta.get("reasoning")
                            or delta.get("reasoning_content")
                            or delta.get("reasoning_details")
                            or delta.get("tool_calls")
                        )
                        if has_stream_payload:
                            now = time.monotonic()
                            if first_token_ms is None:
                                first_token_ms = (now - t_attempt_start) * 1000
                            if last_chunk_at is not None:
                                last_chunk_gap_ms = (now - last_chunk_at) * 1000
                            last_chunk_at = now

                        # 处理 thinking 内容（reasoning 模型的推理过程）
                        # OpenRouter 返回 reasoning (字符串) 和 reasoning_details (数组)
                        reasoning = delta.get("reasoning") or delta.get(
                            "reasoning_content"
                        )
                        if not reasoning and delta.get("reasoning_details"):
                            for detail in delta["reasoning_details"]:
                                if isinstance(detail, dict) and detail.get("text"):
                                    reasoning = (reasoning or "") + detail["text"]
                        if reasoning:
                            yield {"type": "thinking", "content": reasoning}

                        # 处理文本内容 - 立即发送
                        if delta.get("content"):
                            yield {"type": "content", "content": delta["content"]}

                        # 处理工具调用
                        if delta.get("tool_calls"):
                            for tc in delta["tool_calls"]:
                                index = tc.get("index", 0)

                                # 新工具调用开始
                                if tc.get("id"):
                                    tool_calls_buffer[index] = {
                                        "id": tc["id"],
                                        "name": tc.get("function", {}).get("name", ""),
                                        "arguments": "",
                                    }
                                    yield {
                                        "type": "tool_call_start",
                                        "id": tc["id"],
                                        "name": tc.get("function", {}).get("name", ""),
                                    }

                                # 工具名称增量（某些模型可能分开发送）
                                if (
                                    tc.get("function", {}).get("name")
                                    and index in tool_calls_buffer
                                ):
                                    if not tool_calls_buffer[index]["name"]:
                                        tool_calls_buffer[index]["name"] = tc[
                                            "function"
                                        ]["name"]

                                # 参数增量
                                if tc.get("function", {}).get("arguments"):
                                    args_delta = tc["function"]["arguments"]
                                    if index in tool_calls_buffer:
                                        tool_calls_buffer[index][
                                            "arguments"
                                        ] += args_delta

                        # 记录 finish_reason（但不立即结束，等待 usage chunk）
                        # tool_call_end 统一在循环结束后发送，避免 Gemini/OpenRouter
                        # finish_reason 先于部分 tool_call delta 到达导致遗漏
                        if finish_reason:
                            final_finish_reason = finish_reason

                    # 循环结束（[DONE] 后），统一发送所有 tool_call_end
                    if tool_calls_buffer:
                        for tc_data in tool_calls_buffer.values():
                            try:
                                args = (
                                    json.loads(tc_data["arguments"])
                                    if tc_data["arguments"]
                                    else {}
                                )
                            except json.JSONDecodeError:
                                logger.warning(
                                    "工具参数 JSON 解析失败: %s",
                                    (
                                        tc_data["arguments"][:100]
                                        if tc_data["arguments"]
                                        else ""
                                    ),
                                )
                                args = {}
                            yield {
                                "type": "tool_call_end",
                                "id": tc_data["id"],
                                "name": tc_data["name"],
                                "arguments": args,
                            }

                    # 发送 done 事件
                    # 构建 usage 信息（如果可用）
                    usage_info = None
                    if accumulated_usage:
                        usage_info = {
                            "prompt_tokens": accumulated_usage.get("prompt_tokens", 0),
                            "completion_tokens": accumulated_usage.get(
                                "completion_tokens", 0
                            ),
                            "total_tokens": accumulated_usage.get("total_tokens", 0),
                        }
                    billing = await self._record_usage_if_needed(
                        usage_context=usage_context,
                        usage=usage_info,
                        idempotency_key=idempotency_key,
                    )

                    yield {
                        "type": "done",
                        "finish_reason": final_finish_reason or "stop",
                        "usage": usage_info,
                        "billing": billing.to_dict() if billing else None,
                    }
                    await self._record_ai_request_log(
                        request_kind="stream_with_tools",
                        status="success",
                        latency_ms=int((time.monotonic() - t_attempt_start) * 1000),
                        usage_context=usage_context,
                        usage=usage_info,
                        http_status_code=response_status,
                        ttft_ms=(
                            int(first_token_ms) if first_token_ms is not None else None
                        ),
                        last_chunk_gap_ms=(
                            int(last_chunk_gap_ms)
                            if last_chunk_gap_ms is not None
                            else None
                        ),
                        retry_count=attempt,
                        retry_reason=last_retry_reason,
                        message_count=len(messages),
                        context_chars=context_chars,
                        tool_result_chars=tool_context_chars,
                    )
                    logger.info(
                        "流式 LLM 调用完成: finish_reason=%s, usage=%s",
                        final_finish_reason,
                        usage_info,
                    )
                    logger.info(
                        "[LLMStreamMetrics] conversation_id=%s model=%s prompt_tokens=%s "
                        "first_token_ms=%s last_chunk_gap_ms=%s retry_reason=%s "
                        "context_chars=%d tool_result_chars=%d",
                        conversation_id,
                        self.model,
                        usage_info.get("prompt_tokens") if usage_info else None,
                        int(first_token_ms) if first_token_ms is not None else None,
                        (
                            int(last_chunk_gap_ms)
                            if last_chunk_gap_ms is not None
                            else None
                        ),
                        last_retry_reason,
                        context_chars,
                        tool_context_chars,
                    )

                # 成功完成，退出重试循环
                return

            except Exception as e:
                if not _is_retryable_exception(e):
                    # 非可重试异常，直接抛出
                    logger.error("流式 LLM 调用异常: %s: %s", type(e).__name__, str(e))
                    await self._record_ai_request_log(
                        request_kind="stream_with_tools",
                        status="failure",
                        latency_ms=int((time.monotonic() - t_attempt_start) * 1000),
                        usage_context=usage_context,
                        error=e,
                        http_status_code=response_status,
                        ttft_ms=(
                            int(first_token_ms) if first_token_ms is not None else None
                        ),
                        last_chunk_gap_ms=(
                            int(last_chunk_gap_ms)
                            if last_chunk_gap_ms is not None
                            else None
                        ),
                        retry_count=attempt,
                        retry_reason=retry_reason,
                        message_count=len(messages),
                        context_chars=context_chars,
                        tool_result_chars=tool_context_chars,
                    )
                    raise
                last_error = e
                retry_reason = _retry_reason(e)
                last_retry_reason = retry_reason
                if attempt < self.max_retries - 1:
                    wait_time = min(
                        2 * (2**attempt), 30
                    )  # 指数退避: 2, 4, 8... 最大 30 秒
                    logger.warning(
                        "流式 LLM 调用失败 (尝试 %d/%d): %s: %s, retry_reason=%s, 将在 %d 秒后重试",
                        attempt + 1,
                        self.max_retries,
                        type(e).__name__,
                        str(e),
                        retry_reason,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "流式 LLM 调用失败，已达最大重试次数: %s: %s, retry_reason=%s",
                        type(e).__name__,
                        str(e),
                        retry_reason,
                    )
                    await self._record_ai_request_log(
                        request_kind="stream_with_tools",
                        status="failure",
                        latency_ms=int((time.monotonic() - t_attempt_start) * 1000),
                        usage_context=usage_context,
                        error=e,
                        http_status_code=response_status,
                        ttft_ms=(
                            int(first_token_ms) if first_token_ms is not None else None
                        ),
                        last_chunk_gap_ms=(
                            int(last_chunk_gap_ms)
                            if last_chunk_gap_ms is not None
                            else None
                        ),
                        retry_count=attempt,
                        retry_reason=retry_reason,
                        message_count=len(messages),
                        context_chars=context_chars,
                        tool_result_chars=tool_context_chars,
                    )
                    raise

        # 如果循环正常结束但没有成功（理论上不应该到这里）
        if last_error:
            raise last_error
