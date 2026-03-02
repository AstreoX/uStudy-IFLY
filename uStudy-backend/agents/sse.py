"""Agent SSE 事件管理（预留）

此模块为 SSE (Server-Sent Events) 提供基础设施。
当前为预留实现，待 chat 模块完成后集成。

SSE 事件类型:
- sub_agent_start: 任务开始
- sub_agent_done: 任务完成
- sub_agent_error: 任务失败
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    """Agent 事件"""

    event_type: str  # sub_agent_start, sub_agent_done, sub_agent_error
    task_id: UUID
    data: dict[str, Any]


class AgentEventManager:
    """
    Agent 事件管理器

    管理任务状态变更事件，支持 SSE 推送。

    TODO: 集成到 chat 模块的 SSE 端点
    """

    def __init__(self) -> None:
        # 事件队列，按 conversation_id 分组
        self._queues: dict[UUID, asyncio.Queue[AgentEvent]] = {}

    def subscribe(self, conversation_id: UUID) -> asyncio.Queue[AgentEvent]:
        """
        订阅指定对话的事件

        Args:
            conversation_id: 对话 ID

        Returns:
            事件队列
        """
        if conversation_id not in self._queues:
            self._queues[conversation_id] = asyncio.Queue()
        return self._queues[conversation_id]

    def unsubscribe(self, conversation_id: UUID) -> None:
        """
        取消订阅

        Args:
            conversation_id: 对话 ID
        """
        self._queues.pop(conversation_id, None)

    async def emit_task_start(
        self,
        conversation_id: UUID,
        task_id: UUID,
        task_type: str,
    ) -> None:
        """
        发送任务开始事件

        Args:
            conversation_id: 对话 ID
            task_id: 任务 ID
            task_type: 任务类型
        """
        event = AgentEvent(
            event_type="sub_agent_start",
            task_id=task_id,
            data={"task_type": task_type},
        )
        await self._emit(conversation_id, event)

    async def emit_task_done(
        self,
        conversation_id: UUID,
        task_id: UUID,
        result: dict[str, Any],
    ) -> None:
        """
        发送任务完成事件

        Args:
            conversation_id: 对话 ID
            task_id: 任务 ID
            result: 任务结果
        """
        event = AgentEvent(
            event_type="sub_agent_done",
            task_id=task_id,
            data={"result": result},
        )
        await self._emit(conversation_id, event)

    async def emit_task_error(
        self,
        conversation_id: UUID,
        task_id: UUID,
        error: str,
    ) -> None:
        """
        发送任务失败事件

        Args:
            conversation_id: 对话 ID
            task_id: 任务 ID
            error: 错误信息
        """
        event = AgentEvent(
            event_type="sub_agent_error",
            task_id=task_id,
            data={"error": error},
        )
        await self._emit(conversation_id, event)

    async def _emit(self, conversation_id: UUID, event: AgentEvent) -> None:
        """
        发送事件到队列

        Args:
            conversation_id: 对话 ID
            event: 事件
        """
        queue = self._queues.get(conversation_id)
        if queue:
            await queue.put(event)
            logger.debug(
                f"事件已发送: conversation_id={conversation_id}, "
                f"event_type={event.event_type}, task_id={event.task_id}"
            )
        else:
            logger.debug(
                f"无订阅者，事件丢弃: conversation_id={conversation_id}, "
                f"event_type={event.event_type}"
            )


# 全局事件管理器实例
event_manager = AgentEventManager()
