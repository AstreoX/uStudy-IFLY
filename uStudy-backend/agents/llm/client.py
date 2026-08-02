"""OpenRouter LLM 异步客户端"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import get_settings

logger = logging.getLogger(__name__)


def _model_needs_bridge(openrouter_id: str) -> bool:
    """Check if a model requires routing through the JP bridge."""
    from chat.models_config import ALLOWED_MODELS

    return any(
        info.get("use_bridge") and info["openrouter_id"] == openrouter_id
        for info in ALLOWED_MODELS.values()
    )

# 可重试的网络异常类型
RETRYABLE_EXCEPTIONS = (
    httpx.HTTPStatusError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,  # 服务器意外断开连接
)


# Module-level shared httpx client pool (keyed by base_url:proxy_url)
_shared_clients: dict[str, httpx.AsyncClient] = {}


class OpenRouterClientError(Exception):
    """OpenRouter 客户端配置错误"""

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


class OpenRouterClient:
    """OpenRouter API 异步客户端"""

    def __init__(self, model_override: str | None = None) -> None:
        self.settings = get_settings()

        # 验证 API Key 已配置
        if not self.settings.openrouter_api_key:
            raise OpenRouterClientError(
                "OPENROUTER_API_KEY 未配置，请在 .env 文件中设置"
            )

        self.base_url = self.settings.openrouter_base_url
        self.api_key = self.settings.openrouter_api_key
        self.model = model_override or self.settings.openrouter_model

        # Route region-restricted models through JP bridge
        if self.settings.openrouter_bridge_url and _model_needs_bridge(self.model):
            self.base_url = self.settings.openrouter_bridge_url
        self.timeout = self.settings.llm_timeout_seconds
        self.max_retries = self.settings.llm_max_retries
        self.proxy_url = self.settings.llm_proxy_url or None

    def _get_client_kwargs(self) -> dict[str, Any]:
        """获取 httpx.AsyncClient 的配置参数"""
        kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        return kwargs

    def _get_shared_client(self) -> httpx.AsyncClient:
        """Get or create a shared httpx client with connection pooling."""
        key = f"{self.base_url}:{self.proxy_url}"
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

    def _get_headers(self) -> dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://ustudy.app",
            "X-Title": "uStudy",
            "Content-Type": "application/json",
        }

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        非流式补全请求

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 温度参数 (0-1)
            max_tokens: 最大生成 token 数

        Returns:
            LLM 生成的文本内容

        Raises:
            httpx.HTTPStatusError: HTTP 请求失败
            httpx.TimeoutException: 请求超时
        """
        try:
            async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.ConnectError as e:
            logger.error(
                "无法连接到 LLM API (%s): %s。请检查网络连接或代理设置 (HTTP_PROXY/HTTPS_PROXY 或 LLM_PROXY_URL)",
                self.base_url, str(e)
            )
            raise

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 8192,
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
        logger.info("开始 LLM 调用: model=%s, messages_count=%d", self.model, len(messages))
        async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
            try:
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
                response.raise_for_status()
                data = response.json()
                logger.info("LLM 调用成功: status=%d", response.status_code)
            except httpx.HTTPStatusError as e:
                logger.error("LLM HTTP 错误: status=%d, response=%s", e.response.status_code, e.response.text[:500])
                raise
            except httpx.TimeoutException as e:
                logger.error("LLM 调用超时: timeout=%d", self.timeout)
                raise
            except httpx.ConnectError as e:
                logger.error(
                    "无法连接到 LLM API (%s): %s。请检查网络连接或代理设置 (HTTP_PROXY/HTTPS_PROXY 或 LLM_PROXY_URL)",
                    self.base_url, str(e)
                )
                raise
            except Exception as e:
                logger.error("LLM 调用异常: %s: %s", type(e).__name__, str(e))
                raise

            # 检查 API 响应是否包含错误
            if "error" in data:
                error_msg = data.get("error", {})
                if isinstance(error_msg, dict):
                    error_text = error_msg.get("message", str(error_msg))
                else:
                    error_text = str(error_msg)
                # 打印完整响应以便调试
                logger.error("LLM API 错误: %s, 完整响应: %s", error_text, json.dumps(data, ensure_ascii=False)[:1000])
                raise Exception(f"LLM API 错误: {error_text}")

            if "choices" not in data or not data["choices"]:
                logger.error("LLM 响应格式异常: %s", json.dumps(data)[:500])
                raise Exception(f"LLM 响应缺少 choices: {json.dumps(data)[:200]}")

            choice = data["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason", "stop")

            # 解析工具调用
            tool_calls: list[ToolCall] = []
            if "tool_calls" in message and message["tool_calls"]:
                for tc in message["tool_calls"]:
                    try:
                        arguments = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        # LLM 返回了格式错误的 JSON，使用空字典
                        arguments = {}
                    tool_calls.append(
                        ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=arguments,
                        )
                    )

            # 提取 token 用量
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ) if usage_data else None

            return CompletionWithToolsResult(
                content=message.get("content"),
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )

    async def stream_complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
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

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
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
                        },
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content

                # 成功完成，退出重试循环
                return

            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = min(2 * (2 ** attempt), 30)
                    logger.warning(
                        "流式 LLM 调用失败 (尝试 %d/%d): %s: %s, 将在 %d 秒后重试",
                        attempt + 1, self.max_retries, type(e).__name__, str(e), wait_time
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("流式 LLM 调用失败，已达最大重试次数: %s: %s", type(e).__name__, str(e))
                    raise

            except Exception as e:
                logger.error("流式 LLM 调用异常: %s: %s", type(e).__name__, str(e))
                raise

        if last_error:
            raise last_error

    async def stream_complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 8192,
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
        logger.info("开始流式 LLM 调用: model=%s, messages_count=%d", self.model, len(messages))

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            t_attempt_start = time.monotonic()
            logger.info(f"[Perf] LLM attempt {attempt+1}: model={self.model}, base_url={self.base_url}")

            try:
                client = self._get_shared_client()
                t_conn = time.monotonic()
                logger.info(f"[Perf] httpx client ready: {(t_conn-t_attempt_start)*1000:.0f}ms")

                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json={
                        "model": self.model,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "auto",
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                        # Only request reasoning for thinking-capable models
                        **({"reasoning": {"effort": "high"}} if "thinking" in self.model.lower() else {}),
                    },
                ) as response:
                    t_response = time.monotonic()
                    logger.info(f"[Perf] HTTP response received (status={response.status_code}): {(t_response-t_conn)*1000:.0f}ms")
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
                            logger.info(f"[Perf] First SSE line from LLM: {(time.monotonic()-t_response)*1000:.0f}ms")
                            first_sse_line = False

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError as e:
                            logger.warning("流式响应 JSON 解析失败: %s, line: %s", e, data_str[:100])
                            continue

                        if "error" in data:
                            error_msg = data.get("error", {})
                            error_text = error_msg.get("message", str(error_msg)) if isinstance(error_msg, dict) else str(error_msg)
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

                        # 处理 thinking 内容（reasoning 模型的推理过程）
                        # OpenRouter 返回 reasoning (字符串) 和 reasoning_details (数组)
                        reasoning = delta.get("reasoning") or delta.get("reasoning_content")
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
                                        "arguments": ""
                                    }
                                    yield {
                                        "type": "tool_call_start",
                                        "id": tc["id"],
                                        "name": tc.get("function", {}).get("name", "")
                                    }

                                # 工具名称增量（某些模型可能分开发送）
                                if tc.get("function", {}).get("name") and index in tool_calls_buffer:
                                    if not tool_calls_buffer[index]["name"]:
                                        tool_calls_buffer[index]["name"] = tc["function"]["name"]

                                # 参数增量
                                if tc.get("function", {}).get("arguments"):
                                    args_delta = tc["function"]["arguments"]
                                    if index in tool_calls_buffer:
                                        tool_calls_buffer[index]["arguments"] += args_delta

                        # 记录 finish_reason（但不立即结束，等待 usage chunk）
                        # tool_call_end 统一在循环结束后发送，避免 Gemini/OpenRouter
                        # finish_reason 先于部分 tool_call delta 到达导致遗漏
                        if finish_reason:
                            final_finish_reason = finish_reason

                    # 循环结束（[DONE] 后），统一发送所有 tool_call_end
                    if tool_calls_buffer:
                        for tc_data in tool_calls_buffer.values():
                            try:
                                args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                            except json.JSONDecodeError:
                                logger.warning(
                                    "工具参数 JSON 解析失败: %s",
                                    tc_data["arguments"][:100] if tc_data["arguments"] else ""
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
                            "completion_tokens": accumulated_usage.get("completion_tokens", 0),
                            "total_tokens": accumulated_usage.get("total_tokens", 0),
                        }

                    yield {"type": "done", "finish_reason": final_finish_reason or "stop", "usage": usage_info}
                    logger.info("流式 LLM 调用完成: finish_reason=%s, usage=%s", final_finish_reason, usage_info)

                # 成功完成，退出重试循环
                return

            except RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = min(2 * (2 ** attempt), 30)  # 指数退避: 2, 4, 8... 最大 30 秒
                    logger.warning(
                        "流式 LLM 调用失败 (尝试 %d/%d): %s: %s, 将在 %d 秒后重试",
                        attempt + 1, self.max_retries, type(e).__name__, str(e), wait_time
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("流式 LLM 调用失败，已达最大重试次数: %s: %s", type(e).__name__, str(e))
                    raise

            except Exception as e:
                # 非可重试异常，直接抛出
                logger.error("流式 LLM 调用异常: %s: %s", type(e).__name__, str(e))
                raise

        # 如果循环正常结束但没有成功（理论上不应该到这里）
        if last_error:
            raise last_error
