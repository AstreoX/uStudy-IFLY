"""知识图谱生成 Agent"""

import json
import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.exceptions import (
    LLMClientError,
    LLMParsingError,
    LLMParsingErrorWithOutput,
    SpaceNotFoundError,
)
from agents.llm.client import LLMClient
from agents.llm.prompts import build_knowledge_graph_prompt
from agents.graph_persistence import persist_graph
from agents.parsers.knowledge_graph import (
    KnowledgeGraphParser,
    ParsedKnowledgeGraph,
)
from agents.schemas import KnowledgeGraphGenerateRequest
from config import get_settings
from db.models import Space
from usage.metering import UsageContext
from usage.models import UsageType

logger = logging.getLogger(__name__)

# 日志和调试输出的截断限制
LOG_PREVIEW_LENGTH = 200
DEBUG_OUTPUT_MAX_LENGTH = 2000


class KnowledgeGraphAgent:
    """知识图谱生成 Agent"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.llm_client = LLMClient(model_override=self.settings.knowledge_graph_model or None)
        # 图谱生成是非流式长输出，单独放宽 read timeout，避免 20s 默认值过早失败。
        self.llm_client.timeout = max(
            self.settings.llm_timeout_seconds,
            self.settings.knowledge_graph_timeout_seconds,
        )
        self.parser = KnowledgeGraphParser()

    async def generate(
        self,
        user_id: UUID,
        space_id: UUID,
        request: KnowledgeGraphGenerateRequest,
    ) -> tuple[UUID, int, int]:
        """
        生成知识图谱并持久化到数据库

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID（必须已存在）
            request: 生成请求

        Returns:
            Tuple of (space_id, node_count, edge_count)

        Raises:
            SpaceNotFoundError: 学习空间不存在
            LLMClientError: LLM 调用失败
            LLMParsingError: LLM 输出解析失败
        """
        # 1. 验证 space 存在
        space = await self._verify_space(space_id, user_id)
        self.llm_client.usage_context = UsageContext(
            user_id=user_id,
            usage_type=UsageType.AGENT_LLM,
            source_module="agents",
            source_operation="knowledge_graph",
            billable=True,
            space_id=space_id,
            metadata={"topic": request.topic},
        )

        # 2. 调用 LLM 生成知识图谱（带重试）
        llm_output = await self._call_llm_with_retry(request)

        # 3. 解析输出（传入 topic 作为根节点名称）
        parsed_graph = self._parse_output(llm_output, request.topic)

        # 4. 持久化到数据库
        node_count, edge_count = await persist_graph(self.db, space.id, parsed_graph)

        logger.info(
            "知识图谱生成完成: space_id=%s, nodes=%d, edges=%d",
            space_id,
            node_count,
            edge_count,
        )

        return space.id, node_count, edge_count

    async def _verify_space(self, space_id: UUID, user_id: UUID) -> Space:
        """验证学习空间存在且用户有权访问"""
        from spaces.authorization import verify_space_access as _verify
        from spaces.authorization import (
            SpaceAccessDeniedError as _AccessDenied,
            SpaceNotFoundError as _NotFound,
        )

        try:
            return await _verify(self.db, space_id, user_id)
        except _NotFound:
            raise SpaceNotFoundError(f"学习空间不存在或无权访问: {space_id}")
        except _AccessDenied:
            raise SpaceNotFoundError(f"学习空间不存在或无权访问: {space_id}")

    async def _call_llm_with_retry(
        self,
        request: KnowledgeGraphGenerateRequest,
    ) -> str:
        """
        调用 LLM 生成知识图谱（带重试）

        最多重试 max_retries 次（解析失败也会重试）
        """
        messages = build_knowledge_graph_prompt(
            topic=request.topic,
            user_preference=request.user_preference,
        )

        max_retries = self.settings.llm_max_retries
        last_error: Exception | None = None
        last_llm_output: str | None = None  # 保存最后一次 LLM 输出用于调试

        for attempt in range(max_retries):
            try:
                logger.info("LLM 调用尝试 %d/%d", attempt + 1, max_retries)

                llm_output = await self.llm_client.complete(
                    messages,
                    max_tokens=self.settings.knowledge_graph_max_tokens,
                    enable_thinking=False,
                )
                last_llm_output = llm_output  # 保存输出

                # 调试日志：记录 LLM 输出摘要
                logger.debug(
                    "LLM 输出摘要: 长度=%d, 前%d字符=%s",
                    len(llm_output),
                    LOG_PREVIEW_LENGTH,
                    llm_output[:LOG_PREVIEW_LENGTH].replace("\n", "\\n"),
                )

                # 尝试解析验证（传入 topic 作为根节点名称）
                try:
                    self.parser.parse(llm_output, root_label=request.topic)
                    return llm_output
                except LLMParsingError as e:
                    # WARNING 级别只记录摘要信息
                    logger.warning(
                        "LLM 输出解析失败 (尝试 %d/%d): %s, output_length=%d",
                        attempt + 1,
                        max_retries,
                        e,
                        len(llm_output),
                    )
                    # DEBUG 级别记录完整输出（带截断）
                    truncated_output = (
                        llm_output[:DEBUG_OUTPUT_MAX_LENGTH]
                        if len(llm_output) > DEBUG_OUTPUT_MAX_LENGTH
                        else llm_output
                    )
                    logger.debug(
                        "LLM 原始输出 (截断至 %d 字符):\n%s",
                        DEBUG_OUTPUT_MAX_LENGTH,
                        truncated_output,
                    )
                    last_error = e
                    continue

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if e.response is not None else "unknown"
                response_text = e.response.text if e.response is not None else ""
                provider_error = self._extract_provider_error(response_text)
                logger.warning(
                    "LLM API 调用失败 (尝试 %d/%d): status=%s, error=%s",
                    attempt + 1,
                    max_retries,
                    status_code,
                    provider_error,
                )
                last_error = LLMClientError(
                    f"LLM API 错误 ({status_code}): {provider_error}"
                )
                continue

            except httpx.TimeoutException as e:
                error_text = str(e) or "<empty>"
                logger.warning(
                    "LLM API 调用超时 (尝试 %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    error_text,
                )
                last_error = LLMClientError(f"LLM 请求超时: {error_text}")
                continue

        # 所有重试都失败 - 只在解析错误时携带调试信息
        if last_llm_output and isinstance(last_error, LLMParsingError):
            raise LLMParsingErrorWithOutput(
                str(last_error),
                llm_output=last_llm_output,
            )
        raise last_error or LLMClientError("LLM 调用失败")

    def _parse_output(self, llm_output: str, topic: str) -> ParsedKnowledgeGraph:
        """解析 LLM 输出"""
        return self.parser.parse(llm_output, root_label=topic)

    @staticmethod
    def _extract_provider_error(response_text: str) -> str:
        """从上游 LLM 错误响应中提取可读错误信息。"""
        if not response_text:
            return "未知错误（空响应）"
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            return response_text[:300]

        error_obj = data.get("error")
        if isinstance(error_obj, dict):
            msg = error_obj.get("message")
            code = error_obj.get("code")
            if msg and code:
                return f"{code}: {msg}"
            if msg:
                return str(msg)
            return str(error_obj)
        return str(data)[:300]
