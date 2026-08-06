"""OpenRouter Embedding 异步客户端"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import get_settings

logger = logging.getLogger(__name__)

# 可重试的网络异常类型
RETRYABLE_EXCEPTIONS = (
    httpx.HTTPStatusError,
    httpx.TimeoutException,
    httpx.ConnectError,
)


class EmbeddingClientError(Exception):
    """Embedding 客户端错误"""

    pass


@dataclass
class EmbeddingResult:
    """Embedding 结果"""

    embeddings: list[list[float]]
    token_count: int
    model: str


class EmbeddingClient:
    """OpenRouter Embedding API 异步客户端

    支持两种使用模式：
    - 单次调用 (embed/embed_query): 每次创建临时 HTTP 客户端
    - 批量处理 (embed_batch): 复用持久化客户端 + 并发控制
    """

    def __init__(self, model_override: str | None = None) -> None:
        self.settings = get_settings()

        # 验证 API Key 已配置
        if not self.settings.openrouter_api_key:
            raise EmbeddingClientError(
                "OPENROUTER_API_KEY 未配置，请在 .env 文件中设置"
            )

        self.base_url = self.settings.openrouter_base_url
        self.api_key = self.settings.openrouter_api_key
        self.model = model_override or self.settings.embedding_model
        self.dimension = self.settings.embedding_dimension
        self.batch_size = self.settings.embedding_batch_size
        self.max_concurrent = self.settings.embedding_max_concurrent
        self.timeout = 60  # embedding 请求超时时间（秒）
        self.max_retries = self.settings.llm_max_retries
        self.proxy_url = self.settings.llm_proxy_url or None

        # 延迟初始化: 持久化客户端和并发控制
        self._client: httpx.AsyncClient | None = None
        self._client_lock: asyncio.Lock | None = None
        self._semaphore: asyncio.Semaphore | None = None

    async def _get_semaphore(self) -> asyncio.Semaphore:
        """延迟创建 semaphore，确保在 async 上下文中初始化。"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建持久化 HTTP 客户端（并发安全）。"""
        if self._client is not None and not self._client.is_closed:
            return self._client
        # 延迟创建锁
        if self._client_lock is None:
            self._client_lock = asyncio.Lock()
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(**self._get_client_kwargs())
        return self._client

    async def aclose(self) -> None:
        """关闭持久化 HTTP 客户端连接。"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _get_client_kwargs(self) -> dict:
        """获取 httpx.AsyncClient 的配置参数"""
        kwargs = {"timeout": self.timeout}
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        else:
            # 显式关闭环境变量代理，避免意外走系统代理
            kwargs["trust_env"] = False
        return kwargs

    def _get_headers(self) -> dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://ustudy.app",
            "X-Title": "uStudy",
            "Content-Type": "application/json",
        }

    def _parse_embedding_response(self, data: dict) -> EmbeddingResult:
        """解析 embedding API 响应"""
        # 检查 API 响应是否包含错误
        if "error" in data:
            error_msg = data.get("error", {})
            if isinstance(error_msg, dict):
                error_text = error_msg.get("message", str(error_msg))
                error_code = error_msg.get("code")
                if error_code:
                    error_text = f"{error_text} (code={error_code})"
            else:
                error_text = str(error_msg)
            logger.error("Embedding API 错误: %s", error_text)
            raise EmbeddingClientError(f"Embedding API 错误: {error_text}")

        if "data" not in data:
            raise EmbeddingClientError(f"Embedding 响应缺少 data 字段: {data}")

        # 按 index 排序确保顺序正确
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        embeddings = [item["embedding"] for item in sorted_data]

        # 获取 token 使用量
        usage = data.get("usage", {})
        token_count = usage.get("total_tokens", 0)

        return EmbeddingResult(
            embeddings=embeddings,
            token_count=token_count,
            model=data.get("model", self.model),
        )

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """对一批文本进行 embedding（使用临时 HTTP 客户端）。

        适用于单次调用场景（embed / embed_query），
        每次调用创建并关闭 HTTP 客户端。
        """
        t0 = time.monotonic()
        async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
            payload = {
                "model": self.model,
                "input": texts,
                "dimensions": self.dimension,
                "provider": {"allow_fallbacks": True},
            }
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            elapsed = (time.monotonic() - t0) * 1000
            logger.info(
                "[Perf] Embedding API call (%d texts): %.0fms, model=%s",
                len(texts), elapsed, self.model,
            )
            return self._parse_embedding_response(response.json())

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _embed_batch_persistent(self, texts: list[str]) -> EmbeddingResult:
        """对一批文本进行 embedding（使用持久化 HTTP 客户端）。

        适用于批量处理场景（embed_batch），
        复用 TCP/TLS 连接以减少握手开销。
        """
        t0 = time.monotonic()
        client = await self._get_client()
        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimension,
            "provider": {"allow_fallbacks": True},
        }
        response = await client.post(
            f"{self.base_url}/embeddings",
            headers=self._get_headers(),
            json=payload,
        )
        response.raise_for_status()
        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "[Perf] Embedding API call (%d texts): %.0fms, model=%s",
            len(texts), elapsed, self.model,
        )
        return self._parse_embedding_response(response.json())

    async def _embed_batch_throttled(self, texts: list[str]) -> EmbeddingResult:
        """带并发控制的持久化 embedding 批次调用"""
        sem = await self._get_semaphore()
        async with sem:
            return await self._embed_batch_persistent(texts)

    async def embed(self, text: str) -> list[float]:
        """
        对单个文本进行 embedding（临时客户端，无连接泄漏）。

        Args:
            text: 输入文本

        Returns:
            embedding 向量
        """
        result = await self._embed_batch([text])
        return result.embeddings[0]

    async def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """
        对多个文本进行批量 embedding。

        使用持久化客户端复用连接，并发控制通过 semaphore 限流。
        调用方应在完成后调用 aclose() 释放连接。

        Args:
            texts: 文本列表

        Returns:
            EmbeddingResult 包含所有向量
        """
        if not texts:
            return EmbeddingResult(embeddings=[], token_count=0, model=self.model)

        # 单批次直接处理（仍使用持久化客户端）
        if len(texts) <= self.batch_size:
            return await self._embed_batch_throttled(texts)

        # 分批并发处理
        batches = [
            texts[i : i + self.batch_size]
            for i in range(0, len(texts), self.batch_size)
        ]

        logger.info(
            "Embedding 批量处理: %d 条文本 → %d 批 (并发=%d)",
            len(texts),
            len(batches),
            self.max_concurrent,
        )

        results = await asyncio.gather(
            *[self._embed_batch_throttled(batch) for batch in batches],
            return_exceptions=True,
        )

        # 检查是否有失败的批次
        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            raise errors[0]

        all_embeddings: list[list[float]] = []
        total_tokens = 0
        for result in results:
            all_embeddings.extend(result.embeddings)
            total_tokens += result.token_count

        return EmbeddingResult(
            embeddings=all_embeddings,
            token_count=total_tokens,
            model=self.model,
        )

    async def embed_query(self, query: str) -> list[float]:
        """
        对搜索查询进行 embedding（别名方法，语义更清晰）。

        支持 Redis 缓存：相同查询在 TTL 内直接返回缓存结果，避免重复 API 调用。
        使用临时 HTTP 客户端，适用于搜索服务等短生命周期场景。

        Args:
            query: 搜索查询文本

        Returns:
            embedding 向量
        """
        settings = get_settings()
        if not settings.embedding_cache_enabled:
            return await self.embed(query)

        # 计算缓存 key
        cache_key = f"emb:{hashlib.sha256(query.encode()).hexdigest()[:16]}"

        try:
            from db.redis import get_redis

            r = await get_redis()
            cached = await r.get(cache_key)
            if cached is not None:
                logger.debug("Embedding cache hit: %s", cache_key)
                return json.loads(cached)
        except Exception as e:
            logger.debug("Embedding cache read failed (will compute): %s", e)

        # 缓存未命中，调用 API
        embedding = await self.embed(query)

        # 异步写入缓存（不阻塞返回）
        try:
            from db.redis import get_redis

            r = await get_redis()
            await r.set(
                cache_key,
                json.dumps(embedding),
                ex=settings.embedding_cache_ttl_seconds,
            )
        except Exception as e:
            logger.debug("Embedding cache write failed: %s", e)

        return embedding
