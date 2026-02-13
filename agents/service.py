"""Agent 任务调度服务"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agents.exceptions import (
    LLMParsingErrorWithOutput,
    SpaceAccessDeniedError,
    SpaceNotFoundError,
    TaskNotFoundError,
)
from agents.knowledge_graph_agent import KnowledgeGraphAgent
from agents.schemas import (
    AgentTaskResponse,
    AgentTaskResultResponse,
    AgentTaskStatusEnum,
    KnowledgeGraphGenerateRequest,
    QuizGenerateRequest,
)
from agents.test_generation_agent import TestGenerationAgent
from db.database import AsyncSessionLocal
from db.models import AgentTask, AgentTaskStatus, AgentTaskType, DifficultyLevel, Quiz, Space

logger = logging.getLogger(__name__)

# 调试数据存储的大小限制
MAX_DEBUG_OUTPUT_SIZE = 50000  # 50KB（支持更多 LLM 输出）


def _truncate_debug_logs(debug_logs: list[dict[str, Any]], max_size: int = MAX_DEBUG_OUTPUT_SIZE) -> list[dict[str, Any]]:
    """
    截断调试日志以确保不超过大小限制

    保留最新的日志条目，删除较早的日志。
    """
    if not debug_logs:
        return debug_logs

    # 检查总大小
    logs_json = json.dumps(debug_logs, ensure_ascii=False)
    if len(logs_json) <= max_size:
        return debug_logs

    # 需要截断：保留最新的日志
    result = list(debug_logs)
    while result and len(json.dumps(result, ensure_ascii=False)) > max_size:
        result.pop(0)

    if result:
        result.insert(0, {"note": "Earlier logs truncated due to size limit"})

    return result


class AgentService:
    """Agent 任务调度服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_knowledge_graph_task(
        self,
        user_id: UUID,
        space_id: UUID,
        request: KnowledgeGraphGenerateRequest,
        conversation_id: UUID | None = None,
    ) -> AgentTaskResponse:
        """
        创建知识图谱生成任务

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID（必须已存在）
            request: 生成请求
            conversation_id: 关联的对话 ID（可选，用于 SSE 通知）

        Returns:
            任务创建响应

        Raises:
            SpaceNotFoundError: 学习空间不存在
            SpaceAccessDeniedError: 无权访问该学习空间
        """
        # 1. 验证 space 存在且属于当前用户
        await self._verify_space_ownership(space_id, user_id)

        # 2. 创建任务记录
        task = AgentTask(
            user_id=user_id,
            space_id=space_id,
            conversation_id=conversation_id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            status=AgentTaskStatus.PENDING,
            input_data={
                "topic": request.topic,
                "user_preference": request.user_preference,
            },
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info("创建知识图谱生成任务: task_id=%s, space_id=%s", task.id, space_id)

        # 3. 启动后台任务
        background_task = asyncio.create_task(
            self._run_knowledge_graph_task(
                task_id=task.id,
                user_id=user_id,
                space_id=space_id,
                request=request,
            ),
            name=f"kg_task_{task.id}",
        )
        # 添加异常回调以防止静默失败
        background_task.add_done_callback(self._handle_task_exception)

        return AgentTaskResponse(
            task_id=task.id,
            status=AgentTaskStatusEnum(task.status.value),
            task_type=task.task_type.value,
            created_at=task.created_at,
        )

    async def create_quiz_task(
        self,
        user_id: UUID,
        space_id: UUID,
        request: QuizGenerateRequest,
        conversation_id: UUID | None = None,
    ) -> AgentTaskResponse:
        """
        创建测试生成任务

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID
            request: 生成请求
            conversation_id: 关联的对话 ID（可选）

        Returns:
            任务创建响应

        Raises:
            SpaceNotFoundError: 学习空间不存在
            SpaceAccessDeniedError: 无权访问该学习空间
        """
        # 1. 验证 space 存在且属于当前用户
        await self._verify_space_ownership(space_id, user_id)

        # 2. 创建任务记录
        task = AgentTask(
            user_id=user_id,
            space_id=space_id,
            conversation_id=conversation_id,
            task_type=AgentTaskType.GENERATE_QUIZ,
            status=AgentTaskStatus.PENDING,
            input_data={
                "topic": request.topic,
                "difficulty_level": request.difficulty_level.value,
                "test_struct": [
                    {"question_type": item.question_type.value, "question_num": item.question_num}
                    for item in request.test_struct
                ],
            },
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info("创建测试生成任务: task_id=%s, space_id=%s", task.id, space_id)

        # 3. 启动后台任务
        background_task = asyncio.create_task(
            self._run_quiz_task(
                task_id=task.id,
                user_id=user_id,
                space_id=space_id,
                request=request,
            ),
            name=f"quiz_task_{task.id}",
        )
        background_task.add_done_callback(self._handle_task_exception)

        return AgentTaskResponse(
            task_id=task.id,
            status=AgentTaskStatusEnum(task.status.value),
            task_type=task.task_type.value,
            created_at=task.created_at,
        )

    def _handle_task_exception(self, task: asyncio.Task) -> None:
        """处理后台任务的未捕获异常"""
        if task.cancelled():
            logger.warning("后台任务被取消: %s", task.get_name())
            return

        exception = task.exception()
        if exception:
            logger.error(
                "后台任务未捕获异常: %s, error=%s",
                task.get_name(),
                exception,
                exc_info=exception,
            )

    async def _verify_space_ownership(self, space_id: UUID, user_id: UUID) -> None:
        """验证学习空间存在且属于当前用户"""
        result = await self.db.execute(select(Space).where(Space.id == space_id))
        space = result.scalar_one_or_none()

        if not space:
            raise SpaceNotFoundError(f"学习空间不存在: {space_id}")

        if space.user_id != user_id:
            raise SpaceAccessDeniedError(f"无权访问该学习空间: {space_id}")

    async def _run_knowledge_graph_task(
        self,
        task_id: UUID,
        user_id: UUID,
        space_id: UUID,
        request: KnowledgeGraphGenerateRequest,
    ) -> None:
        """
        后台执行知识图谱生成任务

        注意：此方法在独立的 AsyncSession 中运行
        """
        async with AsyncSessionLocal() as session:
            try:
                # 更新状态为 running
                await session.execute(
                    update(AgentTask)
                    .where(AgentTask.id == task_id)
                    .values(
                        status=AgentTaskStatus.RUNNING,
                        started_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

                logger.info("开始执行任务: task_id=%s", task_id)

                # 执行 Agent
                agent = KnowledgeGraphAgent(session)
                result_space_id, node_count, edge_count = await agent.generate(
                    user_id=user_id,
                    space_id=space_id,
                    request=request,
                )

                # 更新状态为 done
                await session.execute(
                    update(AgentTask)
                    .where(AgentTask.id == task_id)
                    .values(
                        status=AgentTaskStatus.DONE,
                        completed_at=datetime.now(timezone.utc),
                        output_data={
                            "space_id": str(result_space_id),
                            "node_count": node_count,
                            "edge_count": edge_count,
                        },
                    )
                )
                await session.commit()

                logger.info(
                    "任务完成: task_id=%s, nodes=%d, edges=%d",
                    task_id,
                    node_count,
                    edge_count,
                )

                # TODO: 发送 SSE 通知
                # await self._emit_task_done_event(task_id, result_space_id, node_count, edge_count)

            except Exception as e:
                logger.error("任务执行失败: task_id=%s, error=%s", task_id, e)

                # 构建调试数据
                debug_data: dict = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }

                # 如果是带输出的解析错误，保存 LLM 原始输出（带截断）
                if isinstance(e, LLMParsingErrorWithOutput):
                    raw_output = e.llm_output
                    debug_data["llm_output_length"] = len(raw_output)
                    debug_data["llm_raw_output"] = (
                        raw_output[:MAX_DEBUG_OUTPUT_SIZE]
                        if len(raw_output) > MAX_DEBUG_OUTPUT_SIZE
                        else raw_output
                    )
                    debug_data["llm_output_truncated"] = (
                        len(raw_output) > MAX_DEBUG_OUTPUT_SIZE
                    )

                # 更新状态为 failed
                await session.execute(
                    update(AgentTask)
                    .where(AgentTask.id == task_id)
                    .values(
                        status=AgentTaskStatus.FAILED,
                        completed_at=datetime.now(timezone.utc),
                        error_message=str(e),
                        output_data=debug_data,  # 保存调试数据
                    )
                )
                await session.commit()

                # TODO: 发送 SSE 错误通知
                # await self._emit_task_error_event(task_id, str(e))

    async def _run_quiz_task(
        self,
        task_id: UUID,
        user_id: UUID,
        space_id: UUID,
        request: QuizGenerateRequest,
    ) -> None:
        """
        后台执行测试生成任务

        注意：此方法在独立的 AsyncSession 中运行
        """
        async with AsyncSessionLocal() as session:
            try:
                # 更新状态为 running，并初始化 output_data（让前端能立即看到状态）
                initial_debug_log = {
                    "iteration": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "llm_content": "任务已启动，正在初始化...",
                    "tool_calls_count": 0,
                    "progress": "0/?",
                    "finish_reason": None,
                    "status": "initializing",
                }
                await session.execute(
                    update(AgentTask)
                    .where(AgentTask.id == task_id)
                    .values(
                        status=AgentTaskStatus.RUNNING,
                        started_at=datetime.now(timezone.utc),
                        output_data={
                            "debug_logs": [initial_debug_log],
                            "status_note": "initializing",
                        },
                    )
                )
                await session.commit()

                logger.info("开始执行测试生成任务: task_id=%s", task_id)

                # 创建 Quiz 记录
                quiz = Quiz(
                    space_id=space_id,
                    agent_task_id=task_id,
                    title=f"{request.topic} 测试",
                    topic=request.topic,
                    difficulty=DifficultyLevel(request.difficulty_level.value),
                    total_questions=0,
                )
                session.add(quiz)
                await session.commit()
                await session.refresh(quiz)

                # 创建进度回调函数，用于实时更新调试日志到数据库
                async def on_progress(logs: list[dict[str, Any]]) -> None:
                    """进度回调：更新数据库中的调试日志"""
                    logger.debug("on_progress 回调: logs 数量=%d", len(logs))
                    truncated = _truncate_debug_logs(logs)
                    await session.execute(
                        update(AgentTask)
                        .where(AgentTask.id == task_id)
                        .values(
                            output_data={
                                "quiz_id": str(quiz.id),
                                "debug_logs": truncated,
                                "status_note": "running",
                            }
                        )
                    )
                    await session.commit()
                    logger.debug("on_progress 回调完成: task_id=%s", task_id)

                # 执行 Agent
                agent = TestGenerationAgent(session)
                expected_count, actual_count, debug_logs = await agent.generate(
                    quiz_id=quiz.id,
                    topic=request.topic,
                    difficulty=request.difficulty_level.value,
                    test_struct=[
                        {"question_type": item.question_type.value, "question_num": item.question_num}
                        for item in request.test_struct
                    ],
                    on_progress=on_progress,
                )

                # 更新状态为 done（包含调试日志，带大小限制）
                truncated_logs = _truncate_debug_logs(debug_logs)
                await session.execute(
                    update(AgentTask)
                    .where(AgentTask.id == task_id)
                    .values(
                        status=AgentTaskStatus.DONE,
                        completed_at=datetime.now(timezone.utc),
                        output_data={
                            "quiz_id": str(quiz.id),
                            "expected_count": expected_count,
                            "question_count": actual_count,
                            "debug_logs": truncated_logs,
                        },
                    )
                )
                await session.commit()

                logger.info(
                    "测试生成任务完成: task_id=%s, quiz_id=%s, questions=%d",
                    task_id,
                    quiz.id,
                    actual_count,
                )

            except Exception as e:
                logger.error("测试生成任务失败: task_id=%s, error=%s", task_id, e)

                # 回滚之前的事务（防止 PendingRollbackError）
                await session.rollback()

                # 获取已收集的调试日志（如果有）
                debug_logs: list = []
                if "agent" in locals() and agent is not None:
                    try:
                        debug_logs = agent.debug_logs
                    except Exception as debug_err:
                        logger.warning("获取调试日志失败: %s", debug_err)

                # 更新状态为 failed（包含调试日志，带大小限制）
                truncated_logs = _truncate_debug_logs(debug_logs)
                await session.execute(
                    update(AgentTask)
                    .where(AgentTask.id == task_id)
                    .values(
                        status=AgentTaskStatus.FAILED,
                        completed_at=datetime.now(timezone.utc),
                        error_message=str(e),
                        output_data={
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "debug_logs": truncated_logs,
                        },
                    )
                )
                await session.commit()

    async def get_task_status(
        self,
        user_id: UUID,
        task_id: UUID,
    ) -> AgentTaskResultResponse:
        """
        获取任务状态和结果

        Args:
            user_id: 用户 ID
            task_id: 任务 ID

        Returns:
            任务结果响应

        Raises:
            TaskNotFoundError: 任务不存在
        """
        result = await self.db.execute(
            select(AgentTask).where(
                AgentTask.id == task_id,
                AgentTask.user_id == user_id,
            )
        )
        task = result.scalar_one_or_none()

        if not task:
            raise TaskNotFoundError(f"任务不存在: {task_id}")

        # 解析 output_data
        space_id = None
        node_count = None
        edge_count = None
        quiz_id = None
        question_count = None
        debug_logs = None

        if task.output_data:
            space_id_str = task.output_data.get("space_id")
            if space_id_str:
                space_id = UUID(space_id_str)
            node_count = task.output_data.get("node_count")
            edge_count = task.output_data.get("edge_count")
            quiz_id_str = task.output_data.get("quiz_id")
            if quiz_id_str:
                quiz_id = UUID(quiz_id_str)
            question_count = task.output_data.get("question_count")
            debug_logs = task.output_data.get("debug_logs")

        return AgentTaskResultResponse(
            task_id=task.id,
            status=AgentTaskStatusEnum(task.status.value),
            task_type=task.task_type.value,
            space_id=space_id,
            error_message=task.error_message,
            node_count=node_count,
            edge_count=edge_count,
            quiz_id=quiz_id,
            question_count=question_count,
            debug_logs=debug_logs,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )
