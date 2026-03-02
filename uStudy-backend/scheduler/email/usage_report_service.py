"""Usage report email service."""

import html
import logging
import os
from contextlib import contextmanager
from datetime import date
from email.message import EmailMessage
from typing import Any

from config import get_settings

logger = logging.getLogger(__name__)

# Admin email recipients for usage reports
REPORT_RECIPIENTS = ["tom_cat_gsk@163.com"]


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


def _format_cost(cents: int | None) -> str:
    """Format cost in cents to USD string."""
    return f"${(cents or 0) / 100:.4f}"


def _format_tokens(tokens: int | None) -> str:
    """Format token count with thousands separator."""
    return f"{tokens or 0:,}"


def _build_report_html(report_date: date, data: dict[str, Any]) -> str:
    """Build HTML email content for daily usage report."""
    date_str = report_date.strftime("%Y-%m-%d")

    # Usage type rows
    type_rows = ""
    for item in data.get("by_usage_type", []):
        type_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                {html.escape(item["usage_type"])}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                {_format_tokens(item["tokens"])}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                {item["calls"]:,}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                {_format_cost(item["cost_cents"])}
            </td>
        </tr>
        """

    # Model rows
    model_rows = ""
    for item in data.get("by_model", []):
        model_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                {html.escape(item["model"])}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                {_format_tokens(item["tokens"])}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                {item["calls"]:,}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                {_format_cost(item["cost_cents"])}
            </td>
        </tr>
        """

    # Top users rows
    user_rows = ""
    for i, user in enumerate(data.get("top_users", []), 1):
        user_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{i}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                {html.escape(user["nickname"])}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">
                {html.escape(user["email"])}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                {_format_tokens(user["tokens"])}
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">
                {user["calls"]:,}
            </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>uStudy Daily Usage Report - {date_str}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                 max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
        <div style="background: #fff; border-radius: 12px; padding: 24px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);">

            <!-- Header -->
            <div style="text-align: center; margin-bottom: 24px; padding-bottom: 16px;
                        border-bottom: 1px solid #eee;">
                <h1 style="color: #333; font-size: 24px; margin: 0;">
                    uStudy Daily Usage Report
                </h1>
                <p style="color: #666; margin: 8px 0 0; font-size: 16px;">{date_str}</p>
            </div>

            <!-- Summary Cards -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 24px;">
                <tr>
                    <td width="25%" style="padding: 8px;">
                        <div style="background: #e3f2fd; padding: 16px; border-radius: 8px;
                                    text-align: center;">
                            <div style="font-size: 28px; font-weight: bold; color: #1976d2;">
                                {data.get("active_users", 0):,}
                            </div>
                            <div style="color: #666; font-size: 14px;">Active Users</div>
                            <div style="color: #999; font-size: 12px;">
                                of {data.get("total_users", 0):,} total
                            </div>
                        </div>
                    </td>
                    <td width="25%" style="padding: 8px;">
                        <div style="background: #e8f5e9; padding: 16px; border-radius: 8px;
                                    text-align: center;">
                            <div style="font-size: 28px; font-weight: bold; color: #388e3c;">
                                {_format_tokens(data.get("total_tokens", 0))}
                            </div>
                            <div style="color: #666; font-size: 14px;">Total Tokens</div>
                        </div>
                    </td>
                    <td width="25%" style="padding: 8px;">
                        <div style="background: #fff3e0; padding: 16px; border-radius: 8px;
                                    text-align: center;">
                            <div style="font-size: 28px; font-weight: bold; color: #f57c00;">
                                {data.get("total_calls", 0):,}
                            </div>
                            <div style="color: #666; font-size: 14px;">API Calls</div>
                        </div>
                    </td>
                    <td width="25%" style="padding: 8px;">
                        <div style="background: #fce4ec; padding: 16px; border-radius: 8px;
                                    text-align: center;">
                            <div style="font-size: 28px; font-weight: bold; color: #c2185b;">
                                {_format_cost(data.get("estimated_cost_cents", 0))}
                            </div>
                            <div style="color: #666; font-size: 14px;">Est. Cost</div>
                        </div>
                    </td>
                </tr>
            </table>

            <!-- Usage by Type -->
            <div style="margin-bottom: 24px;">
                <h3 style="color: #333; margin-bottom: 12px;">Usage by Type</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f8f9fa;">
                            <th style="padding: 10px; text-align: left;">Type</th>
                            <th style="padding: 10px; text-align: right;">Tokens</th>
                            <th style="padding: 10px; text-align: right;">Calls</th>
                            <th style="padding: 10px; text-align: right;">Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        {type_rows if type_rows else '<tr><td colspan="4" style="padding: 16px; text-align: center; color: #999;">No usage data</td></tr>'}
                    </tbody>
                </table>
            </div>

            <!-- Usage by Model -->
            <div style="margin-bottom: 24px;">
                <h3 style="color: #333; margin-bottom: 12px;">Usage by Model</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f8f9fa;">
                            <th style="padding: 10px; text-align: left;">Model</th>
                            <th style="padding: 10px; text-align: right;">Tokens</th>
                            <th style="padding: 10px; text-align: right;">Calls</th>
                            <th style="padding: 10px; text-align: right;">Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        {model_rows if model_rows else '<tr><td colspan="4" style="padding: 16px; text-align: center; color: #999;">No usage data</td></tr>'}
                    </tbody>
                </table>
            </div>

            <!-- Top Users -->
            <div style="margin-bottom: 24px;">
                <h3 style="color: #333; margin-bottom: 12px;">Top 10 Users by Token Usage</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f8f9fa;">
                            <th style="padding: 10px; text-align: left; width: 40px;">#</th>
                            <th style="padding: 10px; text-align: left;">Nickname</th>
                            <th style="padding: 10px; text-align: left;">Email</th>
                            <th style="padding: 10px; text-align: right;">Tokens</th>
                            <th style="padding: 10px; text-align: right;">Calls</th>
                        </tr>
                    </thead>
                    <tbody>
                        {user_rows if user_rows else '<tr><td colspan="5" style="padding: 16px; text-align: center; color: #999;">No active users</td></tr>'}
                    </tbody>
                </table>
            </div>

            <!-- Footer -->
            <div style="text-align: center; padding-top: 16px; border-top: 1px solid #eee;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    This is an automated daily report from uStudy API.
                </p>
            </div>
        </div>
    </body>
    </html>
    """


class UsageReportEmailService:
    """Service for sending usage report emails."""

    def __init__(self):
        self.settings = get_settings()

    async def send_daily_report(
        self,
        report_date: date,
        report_data: dict[str, Any],
    ) -> bool:
        """
        Send daily usage report email.

        Returns True if sent successfully, False otherwise.
        """
        try:
            html_content = _build_report_html(report_date, report_data)
            subject = f"[uStudy] Daily Usage Report - {report_date.strftime('%Y-%m-%d')}"

            if self.settings.email_provider == "resend":
                return await self._send_via_resend(subject, html_content)
            else:
                return await self._send_via_smtp(subject, html_content)

        except Exception:
            logger.exception("Failed to send usage report email")
            return False

    async def _send_via_resend(self, subject: str, html_content: str) -> bool:
        """Send email using Resend API."""
        import asyncio

        if resend is None:
            logger.error("resend package not installed")
            return False

        # Set API key for this call
        resend.api_key = self.settings.resend_api_key
        params = {
            "from": f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>",
            "to": REPORT_RECIPIENTS,
            "subject": subject,
            "html": html_content,
        }

        def _sync_send():
            with no_proxy():
                return resend.Emails.send(params)

        # Use asyncio.to_thread (Python 3.9+) instead of deprecated get_event_loop()
        response = await asyncio.to_thread(_sync_send)
        return bool(response.get("id"))

    async def _send_via_smtp(self, subject: str, html_content: str) -> bool:
        """Send email using SMTP."""
        if aiosmtplib is None:
            logger.error("aiosmtplib package not installed")
            return False

        message = EmailMessage()
        message["From"] = (
            f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
        )
        message["To"] = ", ".join(REPORT_RECIPIENTS)
        message["Subject"] = subject
        message.set_content("Please view this email in an HTML-capable email client.")
        message.add_alternative(html_content, subtype="html")

        tls_kwargs = {"use_tls": True} if self.settings.smtp_use_ssl else {"start_tls": self.settings.smtp_use_tls}
        await aiosmtplib.send(
            message,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            username=self.settings.smtp_username,
            password=self.settings.smtp_password,
            **tls_kwargs,
        )
        return True
