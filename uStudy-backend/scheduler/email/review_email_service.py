"""复习提醒邮件服务

使用 LLM 生成个性化复习提醒邮件和不活跃关怀邮件。
LLM 失败时降级为静态模板。
"""

import asyncio
import html
import logging
import os
from contextlib import contextmanager
from email.message import EmailMessage
from typing import Any

from config import get_settings

logger = logging.getLogger(__name__)


@contextmanager
def no_proxy():
    """临时禁用代理环境变量。"""
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
    old_values = {var: os.environ.get(var) for var in proxy_vars}
    for var in proxy_vars:
        os.environ.pop(var, None)
    try:
        yield
    finally:
        for var, value in old_values.items():
            if value is not None:
                os.environ[var] = value


try:
    import aiosmtplib
except ImportError:
    aiosmtplib = None

try:
    import resend
except ImportError:
    resend = None


# ── LLM Prompt 模板 ──

REVIEW_EMAIL_SYSTEM_PROMPT = """你是 uStudy 学习助手，负责为用户写复习提醒邮件。

要求：
1. 温暖鼓励的语气，像一位关心学生的老师
2. 提及用户的具体学习主题，让邮件有针对性
3. 简短实用，不超过 200 字正文
4. 不使用 emoji
5. 用中文
6. 输出纯文本（邮件系统会自动包装为 HTML）
7. 不要写邮件标题，只写正文内容
8. 结尾署名"uStudy 学习助手"
"""

INACTIVITY_EMAIL_SYSTEM_PROMPT = """你是 uStudy 学习助手，负责为一段时间没有复习的用户写一封关怀邮件。

要求：
1. 关爱温暖的语气，绝对不施加压力或制造愧疚感
2. 提及用户之前学过的主题，表达对他们学习成果的认可
3. 轻轻地提醒有复习内容可以回顾
4. 简短实用，不超过 150 字正文
5. 不使用 emoji
6. 用中文
7. 输出纯文本
8. 不要写邮件标题，只写正文内容
9. 结尾署名"uStudy 学习助手"
"""


def _wrap_email_html(text_content: str, title: str) -> str:
    """将纯文本内容包装为 HTML 邮件。"""
    escaped = html.escape(text_content).replace("\n", "<br>")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{html.escape(title)}</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
             max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="text-align: center; margin-bottom: 24px;">
        <h1 style="color: #333; font-size: 22px;">uStudy</h1>
    </div>
    <div style="background: #f8f9fa; border-radius: 12px; padding: 24px;
                line-height: 1.8; color: #333; font-size: 15px;">
        {escaped}
    </div>
    <p style="color: #999; font-size: 12px; text-align: center; margin-top: 24px;">
        此邮件由 uStudy 自动发送，如不需要可在学习空间设置中关闭复习提醒
    </p>
</body>
</html>"""


def _build_review_fallback(
    nickname: str, review_summaries: list[dict[str, Any]],
) -> str:
    """降级模板：复习提醒邮件。"""
    lines = [f"{nickname}，你好！\n"]
    lines.append("以下学习空间有新的复习内容等你回顾：\n")
    for summary in review_summaries:
        space = summary.get("space_name", "未命名空间")
        count = summary.get("due_count", 0)
        topics = ", ".join(summary.get("topics", [])[:3])
        lines.append(f"  {space}：{count} 项待复习")
        if topics:
            lines.append(f"    主题: {topics}")
    lines.append("\n坚持复习，知识才能真正内化。加油！")
    lines.append("\nuStudy 学习助手")
    return "\n".join(lines)


def _build_inactivity_fallback(
    nickname: str, days_inactive: int, pending_topics: list[str],
) -> str:
    """降级模板：不活跃关怀邮件。"""
    topics_text = "、".join(pending_topics[:3])
    return (
        f"{nickname}，好久不见！\n\n"
        f"之前你学过的{topics_text}等知识还记得吗？"
        f"适当回顾一下，可以帮助巩固记忆。\n\n"
        f"没有压力，按自己的节奏来就好。\n\n"
        f"uStudy 学习助手"
    )


class ReviewEmailService:
    """复习邮件发送服务。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def send_review_email(
        self,
        user_email: str,
        nickname: str,
        review_summaries: list[dict[str, Any]],
    ) -> bool:
        """发送每日复习提醒邮件。

        Args:
            user_email: 用户邮箱
            nickname: 用户昵称
            review_summaries: [{space_name, topics, quiz_id, due_count}, ...]

        Returns:
            True if sent successfully
        """
        text_content = await self._generate_review_email_content(
            nickname, review_summaries,
        )
        subject = "【uStudy】你的今日复习计划已准备好"
        html_content = _wrap_email_html(text_content, subject)
        return await self._send_email(user_email, subject, html_content)

    async def send_inactivity_care_email(
        self,
        user_email: str,
        nickname: str,
        days_inactive: int,
        pending_topics: list[str],
    ) -> bool:
        """发送不活跃关怀邮件。

        Args:
            user_email: 用户邮箱
            nickname: 用户昵称
            days_inactive: 不活跃天数
            pending_topics: 待复习的主题列表

        Returns:
            True if sent successfully
        """
        text_content = await self._generate_inactivity_email_content(
            nickname, days_inactive, pending_topics,
        )
        subject = "【uStudy】想念你了"
        html_content = _wrap_email_html(text_content, subject)
        return await self._send_email(user_email, subject, html_content)

    async def _generate_review_email_content(
        self,
        nickname: str,
        review_summaries: list[dict[str, Any]],
    ) -> str:
        """用 LLM 生成复习提醒邮件内容，失败则降级为模板。"""
        try:
            from agents.llm.client import OpenRouterClient

            client = OpenRouterClient(model_override=self.settings.gemini_model)

            summaries_text = []
            for s in review_summaries:
                space = s.get("space_name", "未命名空间")
                count = s.get("due_count", 0)
                topics = ", ".join(s.get("topics", [])[:5])
                summaries_text.append(f"- {space}: {count}项待复习, 主题: {topics}")

            user_msg = (
                f"用户昵称: {nickname}\n\n"
                f"复习概览:\n" + "\n".join(summaries_text)
            )

            result = await client.complete_with_tools(
                messages=[
                    {"role": "system", "content": REVIEW_EMAIL_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                tools=[],
                temperature=0.8,
                max_tokens=1024,
            )
            if result.content and len(result.content.strip()) > 20:
                return result.content.strip()
        except Exception:
            logger.exception("LLM review email generation failed, using fallback")

        return _build_review_fallback(nickname, review_summaries)

    async def _generate_inactivity_email_content(
        self,
        nickname: str,
        days_inactive: int,
        pending_topics: list[str],
    ) -> str:
        """用 LLM 生成关怀邮件内容，失败则降级为模板。"""
        try:
            from agents.llm.client import OpenRouterClient

            client = OpenRouterClient(model_override=self.settings.gemini_model)

            topics_text = "、".join(pending_topics[:5])
            user_msg = (
                f"用户昵称: {nickname}\n"
                f"已有 {days_inactive} 天没有进行复习\n"
                f"之前学过的主题: {topics_text}"
            )

            result = await client.complete_with_tools(
                messages=[
                    {"role": "system", "content": INACTIVITY_EMAIL_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                tools=[],
                temperature=0.8,
                max_tokens=1024,
            )
            if result.content and len(result.content.strip()) > 20:
                return result.content.strip()
        except Exception:
            logger.exception("LLM inactivity email generation failed, using fallback")

        return _build_inactivity_fallback(nickname, days_inactive, pending_topics)

    async def _send_email(
        self, to_email: str, subject: str, html_content: str,
    ) -> bool:
        """发送邮件（Resend / SMTP 双通道）。"""
        try:
            if self.settings.email_provider == "resend":
                return await self._send_via_resend(to_email, subject, html_content)
            else:
                return await self._send_via_smtp(to_email, subject, html_content)
        except Exception:
            logger.exception(f"Failed to send review email to {to_email}")
            return False

    async def _send_via_resend(
        self, to_email: str, subject: str, html_content: str,
    ) -> bool:
        if resend is None:
            logger.error("resend package not installed")
            return False

        resend.api_key = self.settings.resend_api_key
        params = {
            "from": f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }

        def _sync_send():
            with no_proxy():
                return resend.Emails.send(params)

        response = await asyncio.to_thread(_sync_send)
        return bool(response.get("id"))

    async def _send_via_smtp(
        self, to_email: str, subject: str, html_content: str,
    ) -> bool:
        if aiosmtplib is None:
            logger.error("aiosmtplib package not installed")
            return False

        message = EmailMessage()
        message["From"] = (
            f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
        )
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content("请使用支持 HTML 的邮件客户端查看此邮件。")
        message.add_alternative(html_content, subtype="html")

        tls_kwargs = (
            {"use_tls": True}
            if self.settings.smtp_use_ssl
            else {"start_tls": self.settings.smtp_use_tls}
        )
        await aiosmtplib.send(
            message,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            username=self.settings.smtp_username,
            password=self.settings.smtp_password,
            **tls_kwargs,
        )
        return True
