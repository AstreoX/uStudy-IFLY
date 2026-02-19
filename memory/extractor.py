"""自动记忆提取器 - 从对话中自动提取重要信息存入记忆 + 学习活动记录"""

import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from agents.llm.client import OpenRouterClient
from db.database import get_scoped_session
from db.models import MemoryType, Node, StudyActivityLog
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

## 学习活动记录

除了记忆提取，还请分析本轮对话并生成一条学习活动记录。

{activity_context}

请在 JSON 输出中增加 "study_activity" 字段：

## 输出格式
请以严格的 JSON 格式返回：
```json
{{
  "long_term": ["关于用户的持久信息1", "关于用户的持久信息2"],
  "space": ["关于当前学习空间的信息1"],
  "study_activity": {{
    "action": "create",
    "update_id": null,
    "title": "简洁的学习内容标题（如：矩阵乘法与行列式计算）",
    "summary": "一句话描述本次学习内容和收获",
    "activity_type": "学习新知识|复习|解题|探讨",
    "study_depth": "浅层浏览|中等理解|深入掌握",
    "related_nodes": ["知识点1", "知识点2"],
    "should_skip": false
  }}
}}
```

学习活动记录规则：
- 如果对话内容太短或无实质学习内容，设 "should_skip": true
- related_nodes 从以下知识节点列表中选择匹配的：{node_labels}
- **判断 create 还是 update**：
  - 查看今日已有活动记录列表，如果当前对话内容是某条已有记录主题的延续/深入，则 action="update"，并填写 update_id 为该记录的序号
  - 如果当前对话内容是新的学习主题（与已有记录主题不同），则 action="create"
  - 同一个对话中讨论了不同主题，如果是不同主题可以分别创建

如果没有值得记住的信息，long_term 和 space 返回空数组。
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
        conversation_id: UUID | None = None,
    ) -> ExtractionResult:
        """
        从对话中提取记忆并保存

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID（可选）
            space_name: 学习空间名称（可选）
            conversation: 对话消息列表
            conversation_id: 对话 ID，用于关联活动记录（可选）

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

        # 2. 获取今日活动上下文 + 知识节点列表
        activity_context, today_activities = await self._build_activity_context(
            user_id, conversation_id
        )
        node_labels = await self._get_space_node_labels(space_id)
        node_labels_str = ", ".join(node_labels) if node_labels else "（无可用知识节点）"

        # 3. 构建提取 prompt
        space_info = f"{space_name} (ID: {space_id})" if space_name else "无（快速对话）"
        prompt = EXTRACTION_PROMPT.format(
            conversation=conv_text,
            space_info=space_info,
            activity_context=activity_context,
            node_labels=node_labels_str,
        )

        # 4. 调用 LLM 提取记忆
        try:
            response = await self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
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

        # 5. 解析 JSON 响应
        extracted = self._parse_extraction_response(response)
        if not extracted:
            return ExtractionResult(
                long_term_count=0,
                space_count=0,
                long_term_contents=[],
                space_contents=[],
            )

        # 6. 保存提取的记忆
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

        # 7. 保存学习活动记录
        activity_saved = False
        activity_title = None

        activity_data = extracted.get("study_activity", {})
        if activity_data and not activity_data.get("should_skip", False):
            try:
                activity_title = await self._save_study_activity(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    space_id=space_id,
                    space_name=space_name,
                    activity_data=activity_data,
                    message_count=len(conversation),
                    today_activities=today_activities,
                )
                activity_saved = True
            except Exception as e:
                logger.error(f"Failed to save study activity: {e}", exc_info=True)

        logger.info(
            f"Extracted memories for user {user_id}: "
            f"{saved_long_term} long-term, {saved_space} space, "
            f"activity={'saved' if activity_saved else 'skipped'}"
        )

        return ExtractionResult(
            long_term_count=saved_long_term,
            space_count=saved_space,
            long_term_contents=long_term_contents,
            space_contents=space_contents,
            activity_saved=activity_saved,
            activity_title=activity_title,
        )

    async def _build_activity_context(
        self,
        user_id: UUID,
        conversation_id: UUID | None,
    ) -> tuple[str, list[StudyActivityLog]]:
        """
        构建今日活动上下文，供 LLM 判断 create/update。

        Returns:
            (context_string, today_activities_list)
        """
        today = datetime.now(timezone.utc).date()
        today_activities: list[StudyActivityLog] = []

        try:
            async with get_scoped_session() as session:
                result = await session.execute(
                    select(StudyActivityLog)
                    .where(
                        StudyActivityLog.user_id == user_id,
                        StudyActivityLog.activity_date == today,
                    )
                    .order_by(StudyActivityLog.activity_time.asc())
                )
                today_activities = list(result.scalars().all())
                # Eagerly access all attributes before session closes
                for a in today_activities:
                    _ = a.id, a.title, a.activity_type, a.study_depth, a.conversation_id
        except Exception as e:
            logger.error(f"Failed to load today's activities: {e}")

        if not today_activities:
            return "今日尚无学习活动记录，请创建新记录。", []

        lines = ["今日已有学习活动记录："]
        for idx, act in enumerate(today_activities, start=1):
            depth_str = f"，{act.study_depth}" if act.study_depth else ""
            conv_marker = " (当前对话)" if (
                conversation_id and act.conversation_id == conversation_id
            ) else ""
            lines.append(
                f"[{idx}] {act.title}（{act.activity_type}{depth_str}）{conv_marker}"
            )
        lines.append("")
        lines.append(
            "如果本轮对话内容是上述某条记录的延续，请设 action=\"update\"，update_id 为对应序号。"
        )
        lines.append("如果是新主题，请设 action=\"create\"。")

        return "\n".join(lines), today_activities

    async def _get_space_node_labels(self, space_id: UUID | None) -> list[str]:
        """获取空间所有知识节点的 label 列表"""
        if not space_id:
            return []

        try:
            async with get_scoped_session() as session:
                result = await session.execute(
                    select(Node.label).where(Node.space_id == space_id)
                )
                return [row[0] for row in result.all()]
        except Exception as e:
            logger.error(f"Failed to load node labels for space {space_id}: {e}")
            return []

    async def _save_study_activity(
        self,
        user_id: UUID,
        conversation_id: UUID | None,
        space_id: UUID | None,
        space_name: str | None,
        activity_data: dict[str, Any],
        message_count: int,
        today_activities: list[StudyActivityLog],
    ) -> str:
        """
        保存学习活动记录。

        Returns:
            活动标题
        """
        action = activity_data.get("action", "create")
        title = activity_data.get("title", "学习活动")[:300]
        summary = activity_data.get("summary", "")[:1000]
        activity_type = activity_data.get("activity_type", "学习新知识")[:50]
        study_depth = activity_data.get("study_depth")
        if study_depth:
            study_depth = study_depth[:50]
        related_nodes = activity_data.get("related_nodes") or []
        now = datetime.now(timezone.utc)

        async with get_scoped_session() as session:
            if action == "update" and activity_data.get("update_id") is not None:
                # 尝试更新已有记录
                update_idx = activity_data["update_id"]
                # LLM 可能返回字符串 "2" 而非 int 2
                if isinstance(update_idx, str) and update_idx.isdigit():
                    update_idx = int(update_idx)
                if isinstance(update_idx, int) and 1 <= update_idx <= len(today_activities):
                    target = today_activities[update_idx - 1]
                    result = await session.execute(
                        select(StudyActivityLog).where(
                            StudyActivityLog.id == target.id
                        )
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        existing.title = title
                        existing.summary = summary
                        existing.study_depth = study_depth
                        existing.related_node_labels = related_nodes or existing.related_node_labels
                        existing.message_count = message_count
                        existing.activity_type = activity_type
                        await session.commit()
                        logger.info(f"Updated activity log {existing.id} for user {user_id}")
                        return title

            # 默认 create
            new_activity = StudyActivityLog(
                user_id=user_id,
                conversation_id=conversation_id,
                space_id=space_id,
                title=title,
                summary=summary,
                activity_type=activity_type,
                subject_name=space_name[:200] if space_name else None,
                related_node_labels=related_nodes if related_nodes else None,
                message_count=message_count,
                study_depth=study_depth,
                source="conversation",
                activity_date=now.date(),
                activity_time=now,
            )
            session.add(new_activity)
            await session.commit()
            logger.info(f"Created activity log for user {user_id}: {title}")
            return title

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

    def _parse_extraction_response(self, response: str) -> dict[str, Any] | None:
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

        # 尝试查找 JSON 对象（更宽松匹配，支持嵌套）
        json_match = re.search(r"\{.*\"long_term\".*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse extraction response: {response[:200]}")
        return None
