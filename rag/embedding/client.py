"""OpenRouter Embedding 异步客户端"""

import asyncio
import logging
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
    """OpenRouter Embedding API 异步客户端"""

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
        self.timeout = 60  # embedding 请求超时时间（秒）
        self.max_retries = self.settings.llm_max_retries
        self.proxy_url = self.settings.llm_proxy_url or None

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

    @retry(
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """
        对一批文本进行 embedding

        Args:
            texts: 文本列表

        Returns:
            EmbeddingResult 包含向量和 token 数

        Raises:
            httpx.HTTPStatusError: HTTP 请求失败
            httpx.TimeoutException: 请求超时
            EmbeddingClientError: API 返回错误
        """
        async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
            payload = {
                "model": self.model,
                "input": texts,
                "dimensions": self.dimension,  # 指定输出向量维度
                # 显式开启 provider 自动回退，降低单一 provider 故障导致的失败率
                "provider": {"allow_fallbacks": True},
            }
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

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

    async def embed(self, text: str) -> list[float]:
        """
        对单个文本进行 embedding

        Args:
            text: 输入文本

        Returns:
            embedding 向量 (1536 维)
        """
        result = await self._embed_batch([text])
        return result.embeddings[0]

    async def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """
        对多个文本进行批量 embedding

        Args:
            texts: 文本列表

        Returns:
            EmbeddingResult 包含所有向量
        """
        if not texts:
            return EmbeddingResult(embeddings=[], token_count=0, model=self.model)

        # 如果文本数量不超过批次大小，直接处理
        if len(texts) <= self.batch_size:
            return await self._embed_batch(texts)

        # 分批处理
        all_embeddings: list[list[float]] = []
        total_tokens = 0

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            logger.info(
                "处理 embedding 批次 %d/%d (共 %d 条)",
                i // self.batch_size + 1,
                (len(texts) + self.batch_size - 1) // self.batch_size,
                len(batch),
            )

            result = await self._embed_batch(batch)
            all_embeddings.extend(result.embeddings)
            total_tokens += result.token_count

            # 批次之间添加短暂延迟，避免 rate limit
            if i + self.batch_size < len(texts):
                await asyncio.sleep(0.1)

        return EmbeddingResult(
            embeddings=all_embeddings,
            token_count=total_tokens,
            model=self.model,
        )

    async def embed_query(self, query: str) -> list[float]:
        """
        对搜索查询进行 embedding（别名方法，语义更清晰）

        Args:
            query: 搜索查询文本

        Returns:
            embedding 向量
        """
        return await self.embed(query)
