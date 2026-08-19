"""Collaborative space join notification - sends email to space owner when a user joins."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.message import EmailMessage

from auth.email_service import no_proxy

logger = logging.getLogger(__name__)

try:
    import aiosmtplib
except ImportError:
    aiosmtplib = None

try:
    import resend
except ImportError:
    resend = None


def _build_join_notification_html(
    joiner_email: str,
    joiner_nickname: str,
    space_name: str,
) -> str:
    """Build HTML content for space join notification email."""
    import html

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                 max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5;">
        <div style="background: #fff; border-radius: 12px; padding: 24px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <div style="text-align: center; margin-bottom: 24px; padding-bottom: 16px;
                        border-bottom: 1px solid #eee;">
                <h1 style="color: #1677ff; font-size: 24px; margin: 0;">New Member Joined</h1>
                <p style="color: #666; margin: 8px 0 0;">uStudy</p>
            </div>
            <div style="padding: 16px; background: #f0f7ff; border-radius: 8px;
                        border-left: 4px solid #1677ff;">
                <table style="width: 100%; font-size: 14px;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 120px;">Space:</td>
                        <td style="padding: 8px 0; color: #333; font-weight: 600;">
                            {html.escape(space_name)}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">Member:</td>
                        <td style="padding: 8px 0; color: #333;">
                            {html.escape(joiner_nickname)}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">Email:</td>
                        <td style="padding: 8px 0; color: #333;">
                            {html.escape(joiner_email)}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">Joined At:</td>
                        <td style="padding: 8px 0; color: #333;">{now_str}</td>
                    </tr>
                </table>
            </div>
            <div style="text-align: center; padding-top: 16px; margin-top: 16px;
                        border-top: 1px solid #eee;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    Automated notification from uStudy.
                </p>
            </div>
        </div>
    </body>
    </html>
    """


async def _send_via_resend(
    settings, subject: str, html_content: str, to_email: str
) -> bool:
    if resend is None:
        logger.error("resend package not installed, cannot send join notification")
        return False

    resend.api_key = settings.resend_api_key
    params = {
        "from": f"{settings.smtp_from_name} <{settings.smtp_from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }

    def _sync_send():
        with no_proxy():
            return resend.Emails.send(params)

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, _sync_send)
    return bool(response.get("id"))


async def _send_via_smtp(
    settings, subject: str, html_content: str, to_email: str
) -> bool:
    if aiosmtplib is None:
        logger.error("aiosmtplib package not installed, cannot send join notification")
        return False

    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("Please view this email in an HTML-capable email client.")
    message.add_alternative(html_content, subtype="html")

    tls_kwargs = (
        {"use_tls": True}
        if settings.smtp_use_ssl
        else {"start_tls": settings.smtp_use_tls}
    )
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        **tls_kwargs,
    )
    return True


async def send_space_join_notification(
    settings,
    owner_email: str,
    joiner_email: str,
    joiner_nickname: str,
    space_name: str,
) -> bool:
    """Send notification email to space owner when a new member joins.

    Args:
        settings: App settings with email configuration.
        owner_email: The space owner's email address (recipient).
        joiner_email: The joining user's email address.
        joiner_nickname: The joining user's nickname.
        space_name: Name of the space being joined.

    Returns:
        True if sent successfully, False otherwise.
        Failures are logged but never raise.
    """
    try:
        html_content = _build_join_notification_html(
            joiner_email=joiner_email,
            joiner_nickname=joiner_nickname,
            space_name=space_name,
        )
        subject = f"[uStudy] {joiner_nickname} joined your space: {space_name}"

        if settings.email_provider == "resend":
            ok = await _send_via_resend(
                settings, subject, html_content, to_email=owner_email
            )
        else:
            ok = await _send_via_smtp(
                settings, subject, html_content, to_email=owner_email
            )

        if ok:
            logger.info(
                "Space join notification sent to %s (joiner: %s, space: %s)",
                owner_email,
                joiner_email,
                space_name,
            )
        else:
            logger.warning(
                "Space join notification failed for owner %s (joiner: %s)",
                owner_email,
                joiner_email,
            )
        return ok

    except Exception:
        logger.exception("Error sending space join notification to %s", owner_email)
        return False
