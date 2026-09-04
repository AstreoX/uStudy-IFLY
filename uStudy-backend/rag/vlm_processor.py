"""VLM 视觉语言模型处理器 — 通过 OpenRouter API 处理文档视觉内容（OCR + 图片描述）"""

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx

from config import get_settings
from usage.metering import UsageContext, record_and_charge_usage
from usage.observability import record_ai_request_log

# (completed, total) → awaitable
ProgressCallback = Callable[[int, int], Awaitable[None]]

logger = logging.getLogger(__name__)


@dataclass
class VLMTask:
    """VLM 处理任务"""

    image_bytes: bytes
    task_type: str  # "ocr" or "describe"
    context: str = ""  # 上下文文本，提升描述准确性
    page_num: int | None = None  # 页码（OCR 时使用）


class VLMProcessor:
    """通过 OpenRouter VLM API 处理文档视觉内容"""

    # OCR 系统提示
    OCR_SYSTEM_PROMPT = (
        "你是一个专业的 OCR 文字识别助手。请仔细提取图片中的所有文字内容，"
        "保持原始的格式和结构（包括段落分隔、列表、表格等）。"
        "只输出提取到的文字内容，不要添加任何解释或说明。"
        '如果图片中没有可识别的文字，回复"[无可识别文字]"。'
    )

    # 图片描述系统提示
    DESCRIBE_SYSTEM_PROMPT = (
        "你是一个专业的图片内容描述助手。请简洁描述图片内容，"
        "重点关注信息性内容（图表数据、公式、示意图、流程图等）。"
        "如果是图表，请提取关键数据点。如果是公式，请用文字或 LaTeX 表示。"
        "描述应该简洁有用，帮助读者理解文档中图片传递的信息。"
    )

    def __init__(self, usage_context: UsageContext | None = None) -> None:
        self.settings = get_settings()
        self.model = self.settings.vlm_model
        self.max_concurrent = self.settings.vlm_max_concurrent
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self.usage_context = usage_context

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }

    def _get_client_kwargs(self) -> dict:
        kwargs: dict = {"timeout": 60}
        if self.settings.llm_proxy_url:
            kwargs["proxy"] = self.settings.llm_proxy_url
        return kwargs

    def _image_to_data_uri(self, image_bytes: bytes) -> str:
        """将图片字节转为 base64 data URI"""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        # 简单检测图片格式
        if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif image_bytes[:2] == b"\xff\xd8":
            mime = "image/jpeg"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            mime = "image/webp"
        else:
            mime = "image/png"  # 默认
        return f"data:{mime};base64,{b64}"

    async def ocr_page_image(self, image_bytes: bytes, context: str = "") -> str:
        """
        OCR：将页面图片转为文字（用于扫描件 PDF）

        Args:
            image_bytes: 页面图片的字节数据
            context: 可选上下文信息

        Returns:
            提取的文字内容
        """
        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": self._image_to_data_uri(image_bytes)},
            },
            {
                "type": "text",
                "text": "请提取这张图片中的所有文字内容。"
                + (f"\n上下文：{context}" if context else ""),
            },
        ]

        messages = [
            {"role": "system", "content": self.OCR_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return await self._call_vlm(messages)

    async def describe_image(self, image_bytes: bytes, context: str = "") -> str:
        """
        图片描述：生成嵌入图片的文字描述

        Args:
            image_bytes: 图片的字节数据
            context: 图片前后的文档文本，提升描述准确性

        Returns:
            图片的文字描述
        """
        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": self._image_to_data_uri(image_bytes)},
            },
            {
                "type": "text",
                "text": "请描述这张图片的内容。"
                + (f"\n文档上下文：{context}" if context else ""),
            },
        ]

        messages = [
            {"role": "system", "content": self.DESCRIBE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return await self._call_vlm(messages)

    async def inspect_presentation_slide(
        self, image_bytes: bytes, context: str = ""
    ) -> dict:
        """Inspect one rendered slide for the Presentations skill QA loop."""

        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": self._image_to_data_uri(image_bytes)},
            },
            {
                "type": "text",
                "text": (
                    "请逐项检查这张课件页面：文字截断或换行、元素重叠、画布溢出、"
                    "图片模糊或裁切、对齐与留白、字号层级、视觉一致性、未替换占位符。"
                    "只返回 JSON object：{summary:string, issues:[{severity:'error'|'warning',"
                    "category:string,detail:string}], passed:boolean}。"
                    + (f"\n页面上下文：{context}" if context else "")
                ),
            },
        ]
        raw = await self._call_vlm(
            [
                {
                    "role": "system",
                    "content": "你是 PowerPoint 逐页视觉质检助手，必须基于实际图片报告问题。",
                },
                {"role": "user", "content": user_content},
            ]
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {"ok": True, "passed": False, "summary": raw, "issues": []}
        if not isinstance(parsed, dict):
            return {"ok": True, "passed": False, "summary": raw, "issues": []}
        return {"ok": True, **parsed}

    async def process_batch(
        self,
        tasks: list[VLMTask],
        on_progress: ProgressCallback | None = None,
    ) -> list[str]:
        """
        批量处理 VLM 任务，使用 Semaphore 控制并发

        Args:
            tasks: VLM 任务列表
            on_progress: 可选的进度回调 (completed, total)

        Returns:
            结果列表（与输入顺序对应）
        """
        total = len(tasks)
        completed = 0
        # Throttle progress updates: report every N tasks to avoid DB spam
        progress_interval = max(1, total // 50)  # ~50 updates max

        if on_progress:
            await on_progress(0, total)

        async def _process_one(task: VLMTask) -> str:
            nonlocal completed
            async with self._semaphore:
                try:
                    if task.task_type == "ocr":
                        result = await self.ocr_page_image(
                            task.image_bytes, task.context
                        )
                    elif task.task_type == "describe":
                        result = await self.describe_image(
                            task.image_bytes, task.context
                        )
                    else:
                        logger.warning("未知的 VLM 任务类型: %s", task.task_type)
                        result = ""
                except Exception as e:
                    logger.warning("VLM 任务处理失败: %s", e)
                    result = ""

                completed += 1
                if on_progress and (
                    completed % progress_interval == 0 or completed == total
                ):
                    await on_progress(completed, total)
                return result

        results = await asyncio.gather(*[_process_one(t) for t in tasks])
        return list(results)

    async def _call_vlm(self, messages: list[dict]) -> str:
        """调用 VLM API"""
        base_url = self.settings.dashscope_base_url
        t_start = time.monotonic()
        response_status: int | None = None

        try:
            async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=self._get_headers(),
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.1,
                        "max_tokens": 4096,
                    },
                )
                response_status = response.status_code
                response.raise_for_status()
                data = response.json()
                if data.get("usage"):
                    await record_and_charge_usage(
                        context=self.usage_context,
                        model=self.model,
                        usage=data.get("usage"),
                    )
                if "choices" not in data or not data["choices"]:
                    raise Exception(f"VLM 响应缺少 choices: {str(data)[:200]}")
                content = data["choices"][0]["message"]["content"]
                await record_ai_request_log(
                    model=self.model,
                    base_url=base_url,
                    request_kind="vlm",
                    status="success",
                    latency_ms=int((time.monotonic() - t_start) * 1000),
                    usage_context=self.usage_context,
                    usage=data.get("usage"),
                    http_status_code=response_status,
                    message_count=len(messages),
                    context_chars=sum(
                        len(str(message.get("content", ""))) for message in messages
                    ),
                    source_module="rag",
                    source_operation="vlm_processing",
                )
                return content
        except httpx.ConnectError as e:
            logger.error("VLM API 连接失败: %s", e)
            await record_ai_request_log(
                model=self.model,
                base_url=base_url,
                request_kind="vlm",
                status="failure",
                latency_ms=int((time.monotonic() - t_start) * 1000),
                usage_context=self.usage_context,
                error=e,
                http_status_code=response_status,
                message_count=len(messages),
                context_chars=sum(
                    len(str(message.get("content", ""))) for message in messages
                ),
                source_module="rag",
                source_operation="vlm_processing",
            )
            raise
        except httpx.HTTPStatusError as e:
            logger.error("VLM API 请求失败 (HTTP %d): %s", e.response.status_code, e)
            await record_ai_request_log(
                model=self.model,
                base_url=base_url,
                request_kind="vlm",
                status="failure",
                latency_ms=int((time.monotonic() - t_start) * 1000),
                usage_context=self.usage_context,
                error=e,
                http_status_code=response_status,
                message_count=len(messages),
                context_chars=sum(
                    len(str(message.get("content", ""))) for message in messages
                ),
                source_module="rag",
                source_operation="vlm_processing",
            )
            raise
        except Exception as e:
            logger.error("VLM API 调用异常: %s", e)
            await record_ai_request_log(
                model=self.model,
                base_url=base_url,
                request_kind="vlm",
                status="failure",
                latency_ms=int((time.monotonic() - t_start) * 1000),
                usage_context=self.usage_context,
                error=e,
                http_status_code=response_status,
                message_count=len(messages),
                context_chars=sum(
                    len(str(message.get("content", ""))) for message in messages
                ),
                source_module="rag",
                source_operation="vlm_processing",
            )
            raise
