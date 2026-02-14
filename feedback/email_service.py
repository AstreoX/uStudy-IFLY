"""Feedback email service for sending notifications."""

from __future__ import annotations

import html
import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)

# Target emails for feedback notifications
FEEDBACK_TARGET_EMAILS = [
    "tom_cat_gsk@163.com",
    "gnobodyzx@outlook.com",
    "gnobodyzx@gmail.com",
    "q2119807469@qq.com",
]


@contextmanager
def no_proxy():
    """Temporarily disable proxy environment variables."""
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


def _format_conversation_history(history: list[dict[str, Any]]) -> str:
    """Format conversation history into readable HTML."""
    html_parts = []

    for msg in history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        created_at = msg.get("created_at", "")
        tool_calls = msg.get("tool_calls") or msg.get("toolCalls")
        segments = msg.get("segments")

        # Format timestamp
        timestamp_str = ""
        if created_at:
            try:
                if isinstance(created_at, str):
                    timestamp_str = created_at
                else:
                    timestamp_str = datetime.fromisoformat(
                        str(created_at)
                    ).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                timestamp_str = str(created_at)

        # Role styling
        role_color = "#4a90d9" if role == "user" else "#2ecc71"
        role_label = "User" if role == "user" else "AI"

        html_parts.append(
            f"""
            <div style="margin-bottom: 16px; padding: 12px; background: #f8f9fa;
                        border-radius: 8px; border-left: 4px solid {role_color};">
                <div style="font-size: 12px; color: #666; margin-bottom: 8px;">
                    <strong style="color: {role_color};">{role_label}</strong>
                    {f' - {timestamp_str}' if timestamp_str else ''}
                </div>
                <div style="font-size: 14px; color: #333; white-space: pre-wrap;">
                    {html.escape(content) if content else '<em>No content</em>'}
                </div>
            """
        )

        # Add tool calls if present
        if tool_calls:
            html_parts.append(
                """
                <div style="margin-top: 8px; padding: 8px; background: #fff3cd;
                            border-radius: 4px; font-size: 12px;">
                    <strong>Tool Calls:</strong>
                    <pre style="margin: 4px 0; white-space: pre-wrap; word-break: break-all;">
                """
            )
            html_parts.append(html.escape(json.dumps(tool_calls, indent=2, ensure_ascii=False)))
            html_parts.append("</pre></div>")

        # Add segments if present
        if segments:
            html_parts.append(
                """
                <div style="margin-top: 8px; padding: 8px; background: #d1ecf1;
                            border-radius: 4px; font-size: 12px;">
                    <strong>Segments:</strong>
                    <pre style="margin: 4px 0; white-space: pre-wrap; word-break: break-all;">
                """
            )
            html_parts.append(html.escape(json.dumps(segments, indent=2, ensure_ascii=False)))
            html_parts.append("</pre></div>")

        html_parts.append("</div>")

    return "".join(html_parts)


def _format_llm_context(llm_context: dict[str, Any] | None) -> str:
    """Format LLM API context into readable HTML with collapsible sections."""
    if not llm_context:
        return "<p><em>No LLM context available (message may predate this feature)</em></p>"

    html_parts = []
    request = llm_context.get("request", {})
    response = llm_context.get("response", {})

    # Model and parameters info
    html_parts.append(f"""
    <div style="margin-bottom: 16px; padding: 12px; background: #e3f2fd; border-radius: 8px;">
        <strong>Model:</strong> {html.escape(str(request.get('model', 'unknown')))}
        <span style="margin-left: 16px;"><strong>Temperature:</strong> {request.get('temperature', 'N/A')}</span>
        <span style="margin-left: 16px;"><strong>Max Tokens:</strong> {request.get('max_tokens', 'N/A')}</span>
    </div>
    """)

    # Tools definitions (collapsible)
    tools = request.get("tools", [])
    if tools:
        tools_json = json.dumps(tools, indent=2, ensure_ascii=False)
        html_parts.append(f"""
        <details style="margin-bottom: 16px;">
            <summary style="cursor: pointer; padding: 8px; background: #fff3e0; border-radius: 4px;">
                <strong>Tools Definitions ({len(tools)} tools)</strong>
            </summary>
            <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto;
                        font-size: 11px; max-height: 400px; overflow-y: auto;">
{html.escape(tools_json)}
            </pre>
        </details>
        """)

    # Initial messages sent to LLM (collapsible)
    messages = request.get("messages", [])
    if messages:
        messages_json = json.dumps(messages, indent=2, ensure_ascii=False)
        html_parts.append(f"""
        <details style="margin-bottom: 16px;">
            <summary style="cursor: pointer; padding: 8px; background: #e8f5e9; border-radius: 4px;">
                <strong>Initial Messages to LLM ({len(messages)} messages)</strong>
            </summary>
            <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto;
                        font-size: 11px; max-height: 500px; overflow-y: auto;">
{html.escape(messages_json)}
            </pre>
        </details>
        """)

    # Response iterations
    iterations = response.get("iterations", [])
    total_iterations = response.get("total_iterations", len(iterations))
    finish_reason = response.get("finish_reason", "unknown")

    html_parts.append(f"""
    <div style="margin-bottom: 12px; padding: 8px; background: #fce4ec; border-radius: 4px;">
        <strong>Response Summary:</strong>
        {total_iterations} iteration(s), finish_reason: {html.escape(str(finish_reason))}
    </div>
    """)

    for i, iteration in enumerate(iterations, 1):
        iteration_json = json.dumps(iteration, indent=2, ensure_ascii=False)
        has_tools = bool(iteration.get("tool_calls"))
        iter_label = f"Iteration {i}" + (" (with tool calls)" if has_tools else " (final response)")

        html_parts.append(f"""
        <details style="margin-bottom: 12px;" {"open" if i == len(iterations) else ""}>
            <summary style="cursor: pointer; padding: 8px; background: #f3e5f5; border-radius: 4px;">
                <strong>{iter_label}</strong>
            </summary>
            <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto;
                        font-size: 11px; max-height: 400px; overflow-y: auto;">
{html.escape(iteration_json)}
            </pre>
        </details>
        """)

    return "".join(html_parts)


def _build_feedback_email_html(
    user_email: str,
    user_nickname: str,
    chat_mode: str,
    space_name: str | None,
    feedback_content: str,
    conversation_history: list[dict[str, Any]],
    system_prompt: str | None = None,
    llm_context: dict[str, Any] | None = None,
) -> str:
    """Build HTML email content for feedback notification."""
    mode_display = "Learning Space" if chat_mode == "space_chat" else "Quick Chat"
    space_info = f" ({html.escape(space_name)})" if space_name else ""

    # LLM Context section (priority over legacy system_prompt)
    llm_context_section = ""
    if llm_context:
        llm_context_section = f"""
        <div style="margin-bottom: 24px;">
            <h3 style="color: #333; margin-bottom: 12px;">
                Complete LLM API Context
            </h3>
            {_format_llm_context(llm_context)}
        </div>
        """
    elif system_prompt:
        # Fallback to legacy system_prompt display
        llm_context_section = f"""
        <div style="margin-bottom: 24px;">
            <h3 style="color: #333; margin-bottom: 12px;">System Prompt (Legacy)</h3>
            <div style="background: #e8f4fd; padding: 12px; border-radius: 8px;
                        max-height: 300px; overflow-y: auto;">
                <pre style="margin: 0; white-space: pre-wrap; word-break: break-all;
                            font-size: 12px; color: #333;">
{html.escape(system_prompt)}
                </pre>
            </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>User Feedback - uStudy</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                 max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
        <div style="background: #fff; border-radius: 12px; padding: 24px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 24px; padding-bottom: 16px;
                        border-bottom: 1px solid #eee;">
                <h1 style="color: #333; font-size: 24px; margin: 0;">
                    User Feedback Report
                </h1>
                <p style="color: #666; margin: 8px 0 0;">uStudy AI Assistant</p>
            </div>

            <!-- User Info -->
            <div style="margin-bottom: 24px; padding: 16px; background: #f8f9fa;
                        border-radius: 8px;">
                <h3 style="color: #333; margin: 0 0 12px;">User Information</h3>
                <table style="width: 100%; font-size: 14px;">
                    <tr>
                        <td style="padding: 4px 0; color: #666; width: 120px;">Email:</td>
                        <td style="padding: 4px 0; color: #333;">{html.escape(user_email)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #666;">Nickname:</td>
                        <td style="padding: 4px 0; color: #333;">{html.escape(user_nickname)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #666;">Chat Mode:</td>
                        <td style="padding: 4px 0; color: #333;">{mode_display}{space_info}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #666;">Submitted:</td>
                        <td style="padding: 4px 0; color: #333;">
                            {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                        </td>
                    </tr>
                </table>
            </div>

            <!-- Feedback Content -->
            <div style="margin-bottom: 24px;">
                <h3 style="color: #333; margin-bottom: 12px;">Feedback Content</h3>
                <div style="background: #fff3cd; padding: 16px; border-radius: 8px;
                            border-left: 4px solid #ffc107;">
                    <p style="margin: 0; font-size: 14px; color: #333; white-space: pre-wrap;">
{html.escape(feedback_content)}
                    </p>
                </div>
            </div>

            {llm_context_section}

            <!-- Conversation History -->
            <div style="margin-bottom: 24px;">
                <h3 style="color: #333; margin-bottom: 12px;">
                    Conversation History ({len(conversation_history)} messages)
                </h3>
                {_format_conversation_history(conversation_history)}
            </div>

            <!-- Footer -->
            <div style="text-align: center; padding-top: 16px; border-top: 1px solid #eee;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    This is an automated feedback notification from uStudy.
                </p>
            </div>
        </div>
    </body>
    </html>
    """


class FeedbackEmailService:
    """Service for sending feedback notification emails."""

    def __init__(self, settings):
        """Initialize with app settings."""
        self.settings = settings
        self._provider = None

    async def send_feedback_email(
        self,
        user_email: str,
        user_nickname: str,
        chat_mode: str,
        space_name: str | None,
        feedback_content: str,
        conversation_history: list[dict[str, Any]],
        system_prompt: str | None = None,
        llm_context: dict[str, Any] | None = None,
    ) -> bool:
        """Send feedback notification email.

        Returns True if email was sent successfully, False otherwise.
        Email failures are logged but don't raise exceptions.
        """
        try:
            html_content = _build_feedback_email_html(
                user_email=user_email,
                user_nickname=user_nickname,
                chat_mode=chat_mode,
                space_name=space_name,
                feedback_content=feedback_content,
                conversation_history=conversation_history,
                system_prompt=system_prompt,
                llm_context=llm_context,
            )

            subject = f"[uStudy Feedback] {user_nickname} - {chat_mode}"

            if self.settings.email_provider == "resend":
                return await self._send_via_resend(subject, html_content)
            else:
                return await self._send_via_smtp(subject, html_content)

        except Exception as e:
            logger.exception(f"Failed to send feedback email: {e}")
            return False

    async def _send_via_resend(self, subject: str, html_content: str) -> bool:
        """Send email using Resend API."""
        import asyncio

        if resend is None:
            logger.error("resend package not installed")
            return False

        resend.api_key = self.settings.resend_api_key
        params = {
            "from": f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>",
            "to": FEEDBACK_TARGET_EMAILS,
            "subject": subject,
            "html": html_content,
        }

        def _sync_send():
            with no_proxy():
                return resend.Emails.send(params)

        # Run synchronous resend call in thread executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _sync_send)

        return bool(response.get("id"))

    async def _send_via_smtp(self, subject: str, html_content: str) -> bool:
        """Send email using SMTP."""
        if aiosmtplib is None:
            logger.error("aiosmtplib package not installed")
            return False

        message = EmailMessage()
        message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
        message["To"] = ", ".join(FEEDBACK_TARGET_EMAILS)
        message["Subject"] = subject
        message.set_content("Please view this email in an HTML-capable email client.")
        message.add_alternative(html_content, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            username=self.settings.smtp_username,
            password=self.settings.smtp_password,
            start_tls=self.settings.smtp_use_tls,
        )
        return True
