"""知识图谱掌握分更新 Agent"""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from agents.llm import OpenRouterClient
from agents.llm.mastery_update_prompts import build_mastery_update_prompt
from config import get_settings
from db.database import AsyncSessionLocal
from db.models import Node
from graph.service import GraphService
from quiz.full_evaluation_service import _extract_json_from_response

logger = logging.getLogger(__name__)

# AI 参数常量
MASTERY_UPDATE_TEMPERATURE = 0.3  # 低温度保证更新一致性
MASTERY_UPDATE_MAX_TOKENS = 1024  # 足够生成更新计划


@dataclass
class MasteryUpdateItem:
    """单个节点的掌握分更新"""

    node_name: str
    current_mastery: int | None
    new_mastery: int
    reason: str


@dataclass
class MasteryUpdateResult:
    """掌握分更新结果"""

    updates: list[MasteryUpdateItem]
    success_count: int
    failure_count: int
    error_message: str | None = None


class MasteryUpdateAgent:
    """知识图谱掌握分更新 Agent

    注意：该 Agent 使用独立的数据库会话，以支持与其他任务并行执行。
    """

    def __init__(self, space_id: UUID) -> None:
        self.space_id = space_id

    async def update_mastery(
        self,
        quiz_topic: str,
        question_results: list[dict],
    ) -> MasteryUpdateResult:
        """
        根据答题结果更新知识图谱节点的掌握分

        使用独立的数据库会话，确保与其他并行任务隔离。

        Args:
            quiz_topic: 测试主题
            question_results: 答题结果列表，每项包含:
                - order: 题目序号
                - question_stem: 题干
                - score: 得分
                - max_score: 满分
                - status: correct/wrong/partial

        Returns:
            MasteryUpdateResult
        """
        # 使用独立的数据库会话，避免与并行任务共享 session
        async with AsyncSessionLocal() as db:
            try:
                graph_service = GraphService(db)

                # 1. 获取当前知识图谱
                graph_data = await graph_service.get_graph(self.space_id)
                nodes = graph_data.get("nodes", [])

                if not nodes:
                    logger.info(
                        "Space %s has no knowledge graph nodes, skipping mastery update",
                        self.space_id,
                    )
                    return MasteryUpdateResult(
                        updates=[],
                        success_count=0,
                        failure_count=0,
                    )

                # 2. 构建 prompt 并调用 LLM
                messages = build_mastery_update_prompt(
                    quiz_topic=quiz_topic,
                    nodes=nodes,
                    question_results=question_results,
                )

                client = OpenRouterClient(model_override=get_settings().mastery_evaluation_model or None)
                response = await client.complete(
                    messages=messages,
                    temperature=MASTERY_UPDATE_TEMPERATURE,
                    max_tokens=MASTERY_UPDATE_MAX_TOKENS,
                )

                # 3. 解析 LLM 返回的更新计划
                parsed = _extract_json_from_response(response)
                update_plan = parsed.get("updates", [])

                if not update_plan:
                    logger.info(
                        "LLM returned no mastery updates for quiz topic: %s",
                        quiz_topic,
                    )
                    return MasteryUpdateResult(
                        updates=[],
                        success_count=0,
                        failure_count=0,
                    )

                # 4. 批量执行更新（单个事务）
                return await self._execute_updates(db, nodes, update_plan)

            except Exception as e:
                logger.error(
                    "Mastery update failed for space %s: %s",
                    self.space_id,
                    str(e),
                )
                return MasteryUpdateResult(
                    updates=[],
                    success_count=0,
                    failure_count=0,
                    error_message=str(e),
                )

    async def _execute_updates(
        self,
        db,
        nodes: list[dict],
        update_plan: list[dict],
    ) -> MasteryUpdateResult:
        """
        批量执行掌握分更新（单个事务）

        Args:
            db: 数据库会话
            nodes: 当前知识图谱节点列表
            update_plan: LLM 返回的更新计划

        Returns:
            MasteryUpdateResult
        """
        # 建立名称到节点的映射
        name_to_node = {n["label"]: n for n in nodes}

        # 第一遍：验证并收集有效更新
        valid_updates: list[tuple[UUID, int, str, int | None, str]] = []
        failure_count = 0

        for item in update_plan:
            node_name = item.get("node_name", "")
            new_mastery = item.get("new_mastery")
            reason = item.get("reason", "")

            # 验证节点存在
            node = name_to_node.get(node_name)
            if not node:
                logger.warning(
                    "Node '%s' not found in knowledge graph, skipping",
                    node_name,
                )
                failure_count += 1
                continue

            # 验证掌握分有效（支持 float 转 int）
            if new_mastery is None:
                logger.warning(
                    "Missing mastery value for node '%s'",
                    node_name,
                )
                failure_count += 1
                continue

            try:
                new_mastery = int(new_mastery)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid mastery value for node '%s': %s",
                    node_name,
                    new_mastery,
                )
                failure_count += 1
                continue

            # 限制掌握分范围
            new_mastery = max(0, min(100, new_mastery))

            # 验证 UUID 格式
            try:
                node_id = UUID(node["id"])
            except (ValueError, TypeError):
                logger.error(
                    "Invalid node ID format for '%s': %s",
                    node_name,
                    node.get("id"),
                )
                failure_count += 1
                continue

            current_mastery = node.get("mastery")
            valid_updates.append((node_id, new_mastery, node_name, current_mastery, reason))

        if not valid_updates:
            return MasteryUpdateResult(
                updates=[],
                success_count=0,
                failure_count=failure_count,
            )

        # 第二遍：批量执行更新（单个事务）
        updates: list[MasteryUpdateItem] = []
        success_count = 0

        try:
            for node_id, new_mastery, node_name, current_mastery, reason in valid_updates:
                # 直接更新节点，不单独提交
                result = await db.execute(
                    select(Node).where(
                        Node.id == node_id,
                        Node.space_id == self.space_id,
                    )
                )
                node_obj = result.scalar_one_or_none()

                if node_obj:
                    node_obj.mastery = new_mastery
                    updates.append(
                        MasteryUpdateItem(
                            node_name=node_name,
                            current_mastery=current_mastery,
                            new_mastery=new_mastery,
                            reason=reason,
                        )
                    )
                    success_count += 1
                    logger.info(
                        "Updated mastery for node '%s': %s -> %s (%s)",
                        node_name,
                        current_mastery,
                        new_mastery,
                        reason,
                    )
                else:
                    logger.warning(
                        "Node '%s' not found during update",
                        node_name,
                    )
                    failure_count += 1

            # 单次提交所有更新
            await db.commit()

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to commit mastery updates: %s",
                str(e),
            )
            return MasteryUpdateResult(
                updates=[],
                success_count=0,
                failure_count=failure_count + len(valid_updates),
                error_message=f"Transaction failed: {str(e)}",
            )

        return MasteryUpdateResult(
            updates=updates,
            success_count=success_count,
            failure_count=failure_count,
        )
