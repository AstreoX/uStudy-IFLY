"""流式响应缓存服务

在 AI 流式生成过程中，实时缓存已生成内容到 Redis，支持客户端断连后断点续传。
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from config import get_settings
from db.redis import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()

STREAMING_KEY_PREFIX = "streaming:"
TTL_SECONDS = settings.streaming_cache_ttl_seconds


@dataclass
class StreamingState:
    """流式传输状态"""

    conversation_id: str
    content: str = ""  # 已生成的文本内容
    thinking: str = ""  # 思考过程内容
    tool_calls: list = field(default_factory=list)  # 工具调用记录
    is_complete: bool = False  # 是否已完成
    updated_at: float = 0.0  # 最后更新时间戳

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StreamingState":
        return cls(
            conversation_id=data.get("conversation_id", ""),
            content=data.get("content", ""),
            thinking=data.get("thinking", ""),
            tool_calls=data.get("tool_calls", []),
            is_complete=data.get("is_complete", False),
            updated_at=data.get("updated_at", 0.0),
        )


async def init_streaming_cache(conversation_id: str) -> None:
    """初始化流式缓存（开始新的流式传输时调用）"""
    try:
        r = await get_redis()
        key = f"{STREAMING_KEY_PREFIX}{conversation_id}"
        state = StreamingState(
            conversation_id=conversation_id,
            updated_at=time.time(),
        )
        await r.setex(key, TTL_SECONDS, json.dumps(state.to_dict()))
        logger.debug(f"Initialized streaming cache for conversation {conversation_id}")
    except Exception as e:
        # Redis 故障不应阻塞主流程
        logger.warning(f"Failed to init streaming cache: {e}")


async def update_streaming_cache(
    conversation_id: str,
    content_delta: str = "",
    thinking_delta: str = "",
    tool_call: Optional[dict] = None,
    is_complete: bool = False,
) -> None:
    """
    增量更新流式缓存

    Args:
        conversation_id: 对话 ID
        content_delta: 增量文本内容
        thinking_delta: 增量思考内容
        tool_call: 工具调用记录（完整对象）
        is_complete: 是否已完成
    """
    try:
        r = await get_redis()
        key = f"{STREAMING_KEY_PREFIX}{conversation_id}"

        # 使用 Lua 脚本原子更新，避免竞态条件
        lua_script = """
        local key = KEYS[1]
        local content_delta = ARGV[1]
        local thinking_delta = ARGV[2]
        local tool_call_json = ARGV[3]
        local is_complete = ARGV[4] == "true"
        local updated_at = tonumber(ARGV[5])
        local ttl = tonumber(ARGV[6])

        local state_json = redis.call('GET', key)
        local state
        if state_json then
            state = cjson.decode(state_json)
        else
            state = {
                conversation_id = ARGV[7],
                content = "",
                thinking = "",
                tool_calls = {},
                is_complete = false,
                updated_at = 0
            }
        end

        -- 追加增量内容
        if content_delta ~= "" then
            state.content = state.content .. content_delta
        end
        if thinking_delta ~= "" then
            state.thinking = state.thinking .. thinking_delta
        end
        if tool_call_json ~= "" then
            local tool_call = cjson.decode(tool_call_json)
            table.insert(state.tool_calls, tool_call)
        end
        if is_complete then
            state.is_complete = true
        end
        state.updated_at = updated_at

        redis.call('SETEX', key, ttl, cjson.encode(state))
        return "OK"
        """

        await r.eval(
            lua_script,
            1,  # number of keys
            key,  # KEYS[1]
            content_delta,  # ARGV[1]
            thinking_delta,  # ARGV[2]
            json.dumps(tool_call) if tool_call else "",  # ARGV[3]
            "true" if is_complete else "false",  # ARGV[4]
            str(time.time()),  # ARGV[5]
            str(TTL_SECONDS),  # ARGV[6]
            conversation_id,  # ARGV[7]
        )
    except Exception as e:
        # Redis 故障不应阻塞主流程
        logger.warning(f"Failed to update streaming cache: {e}")


async def get_streaming_state(conversation_id: str) -> Optional[StreamingState]:
    """
    获取当前流式状态

    Args:
        conversation_id: 对话 ID

    Returns:
        StreamingState 或 None（如果缓存不存在/已过期）
    """
    try:
        r = await get_redis()
        key = f"{STREAMING_KEY_PREFIX}{conversation_id}"
        data = await r.get(key)
        if data:
            return StreamingState.from_dict(json.loads(data))
        return None
    except Exception as e:
        logger.warning(f"Failed to get streaming state: {e}")
        return None


async def clear_streaming_cache(conversation_id: str) -> None:
    """清除流式缓存"""
    try:
        r = await get_redis()
        key = f"{STREAMING_KEY_PREFIX}{conversation_id}"
        await r.delete(key)
        logger.debug(f"Cleared streaming cache for conversation {conversation_id}")
    except Exception as e:
        logger.warning(f"Failed to clear streaming cache: {e}")
