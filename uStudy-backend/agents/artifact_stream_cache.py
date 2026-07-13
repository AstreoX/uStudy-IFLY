"""Artifact 流式生成缓存。

在交互式演示后台生成期间，将当前代码快照写入 Redis，
用于通知流断连后的恢复和任务状态查询。
"""

import json
import logging
import time
from dataclasses import asdict, dataclass

from config import get_settings
from db.redis import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()

ARTIFACT_STREAM_KEY_PREFIX = "artifact_stream:"
TTL_SECONDS = settings.streaming_cache_ttl_seconds


@dataclass
class ArtifactStreamState:
    """Artifact 流式状态快照。"""

    task_id: str
    note_id: str
    title: str
    status: str
    code_snapshot: str
    chars_total: int
    updated_at: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ArtifactStreamState":
        return cls(
            task_id=data.get("task_id", ""),
            note_id=data.get("note_id", ""),
            title=data.get("title", ""),
            status=data.get("status", "streaming"),
            code_snapshot=data.get("code_snapshot", ""),
            chars_total=int(data.get("chars_total", 0) or 0),
            updated_at=float(data.get("updated_at", 0.0) or 0.0),
        )


async def set_artifact_stream_state(
    task_id: str,
    note_id: str,
    title: str,
    status: str,
    code_snapshot: str,
) -> None:
    """覆盖写入当前 Artifact 快照。"""
    try:
        redis_client = await get_redis()
        key = f"{ARTIFACT_STREAM_KEY_PREFIX}{task_id}"
        state = ArtifactStreamState(
            task_id=task_id,
            note_id=note_id,
            title=title,
            status=status,
            code_snapshot=code_snapshot,
            chars_total=len(code_snapshot),
            updated_at=time.time(),
        )
        await redis_client.setex(key, TTL_SECONDS, json.dumps(state.to_dict(), ensure_ascii=False))
    except Exception as exc:
        logger.warning("Failed to set artifact stream state: %s", exc)


async def get_artifact_stream_state(task_id: str) -> ArtifactStreamState | None:
    """读取 Artifact 快照。"""
    try:
        redis_client = await get_redis()
        key = f"{ARTIFACT_STREAM_KEY_PREFIX}{task_id}"
        data = await redis_client.get(key)
        if not data:
            return None
        return ArtifactStreamState.from_dict(json.loads(data))
    except Exception as exc:
        logger.warning("Failed to get artifact stream state: %s", exc)
        return None
