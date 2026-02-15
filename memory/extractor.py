"""自动记忆提取器 - 从对话中自动提取重要信息存入记忆"""

import json
import logging
import re
from typing import Any
from uuid import UUID

from agents.llm.client import OpenRouterClient
from db.models import MemoryType
from memory.schemas import ExtractionResult
from memory.service import MemoryService

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """分析以下对话，提取需要长期记住的信息。

## 提取规则

**长期记忆**（关于用户本人，跨所有学习空间有效）：
1. 用户明确表达的偏好（学习风格、时间安排、学习习惯等）
2. 用户分享的个人信息（专业背景、学习目标、职业规划等）
3. 用户纠正的信息（之前的误解需要更新）
4. 重要的个人特点和需求

**空间记忆**（仅与当前学习空间相关）：
1. 该学习主题的学习进度和成就
2. 该学习主题的特定偏好
3. 该学习主题的重点关注内容
4. 该学习主题的难点和问题

**不要提取**：
- 临时性的对话内容（如"好的"、"谢谢"等）
- 已经是常识的信息
- 敏感的个人隐私（密码、证件号、详细地址等）
- 本次对话的具体问答内容（只提取"关于用户"的信息）

## 当前学习空间
{space_info}

## 对话内容
{conversation}

## 输出格式
请以严格的 JSON 格式返回：
```json
{{
  "long_term": ["关于用户的持久信息1", "关于用户的持久信息2"],
  "space": ["关于当前学习空间的信息1"]
}}
```

如果没有值得记住的信息，返回空数组：
```json
{{"long_term": [], "space": []}}
```

只输出 JSON，不要包含其他文字。"""


class MemoryExtractor:
    """自动从对话中提取记忆"""

    def __init__(self) -> None:
        self.llm_client = OpenRouterClient()
        self.memory_service = MemoryService()

    async def extract_and_save(
        self,
        user_id: UUID,
        space_id: UUID | None,
        space_name: str | None,
        conversation: list[dict[str, Any]],
    ) -> ExtractionResult:
        """
        从对话中提取记忆并保存

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID（可选）
            space_name: 学习空间名称（可选）
            conversation: 对话消息列表

        Returns:
            ExtractionResult 包含提取数量和内容
        """
        # 1. 格式化对话内容
        conv_text = self._format_conversation(conversation)
        if not conv_text.strip():
            logger.debug("Empty conversation, skipping memory extraction")
            return ExtractionResult(
                long_term_count=0,
                space_count=0,
                long_term_contents=[],
                space_contents=[],
            )

        # 2. 构建提取 prompt
        space_info = f"{space_name} (ID: {space_id})" if space_name else "无（快速对话）"
        prompt = EXTRACTION_PROMPT.format(
            conversation=conv_text,
            space_info=space_info,
        )

        # 3. 调用 LLM 提取记忆
        try:
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # 低温度，更确定性
                max_tokens=1024,
            )
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return ExtractionResult(
                long_term_count=0,
                space_count=0,
                long_term_contents=[],
                space_contents=[],
            )

        # 4. 解析 JSON 响应
        extracted = self._parse_extraction_response(response)
        if not extracted:
            return ExtractionResult(
                long_term_count=0,
                space_count=0,
                long_term_contents=[],
                space_contents=[],
            )

        # 5. 保存提取的记忆
        long_term_contents = extracted.get("long_term", [])
        space_contents = extracted.get("space", [])

        saved_long_term = 0
        saved_space = 0

        for content in long_term_contents:
            if not content or not content.strip():
                continue
            try:
                await self.memory_service.add_memory(
                    user_id=user_id,
                    content=content.strip(),
                    memory_type=MemoryType.LONG_TERM,
                    extra_data={"source": "auto_extraction"},
                )
                saved_long_term += 1
            except Exception as e:
                logger.error(f"Failed to save long-term memory: {e}")

        if space_id:
            for content in space_contents:
                if not content or not content.strip():
                    continue
                try:
                    await self.memory_service.add_memory(
                        user_id=user_id,
                        content=content.strip(),
                        memory_type=MemoryType.SPACE,
                        space_id=space_id,
                        extra_data={"source": "auto_extraction"},
                    )
                    saved_space += 1
                except Exception as e:
                    logger.error(f"Failed to save space memory: {e}")

        logger.info(
            f"Extracted memories for user {user_id}: "
            f"{saved_long_term} long-term, {saved_space} space"
        )

        return ExtractionResult(
            long_term_count=saved_long_term,
            space_count=saved_space,
            long_term_contents=long_term_contents,
            space_contents=space_contents,
        )

    def _format_conversation(self, messages: list[dict[str, Any]]) -> str:
        """格式化对话为文本"""
        lines = []
        # 只取最近 10 轮对话
        for msg in messages[-20:]:  # 20 条消息约等于 10 轮
            role = msg.get("role", "")
            if role == "system":
                continue  # 跳过系统消息

            role_name = "用户" if role == "user" else "AI"
            content = msg.get("content", "")

            # 处理多模态消息
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = " ".join(text_parts)

            # 截断过长内容
            if len(content) > 500:
                content = content[:500] + "..."

            if content.strip():
                lines.append(f"{role_name}: {content}")

        return "\n".join(lines)

    def _parse_extraction_response(self, response: str) -> dict[str, list[str]] | None:
        """解析 LLM 返回的 JSON 响应"""
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # 尝试从 markdown 代码块中提取
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试查找 JSON 对象
        json_match = re.search(r"\{[^{}]*\"long_term\"[^{}]*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse extraction response: {response[:200]}")
        return None
