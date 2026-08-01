"""Registration notification service - sends email when new user registers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.message import EmailMessage

from auth.email_service import no_proxy

logger = logging.getLogger(__name__)

ADMIN_NOTIFICATION_EMAIL = "tom_cat_gsk@163.com"

try:
    import aiosmtplib
except ImportError:
    aiosmtplib = None

try:
    import resend
except ImportError:
    resend = None


def _build_notification_html(
    user_email: str,
    user_nickname: str,
    registration_method: str,
) -> str:
    """Build HTML content for registration notification email."""
    import html

    method_labels = {
        "email": "Email / Password",
        "code": "Verification Code",
        "apple": "Apple Sign-In",
    }
    method_display = method_labels.get(registration_method, registration_method)
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
                <h1 style="color: #333; font-size: 24px; margin: 0;">New User Registered</h1>
                <p style="color: #666; margin: 8px 0 0;">uStudy</p>
            </div>
            <div style="padding: 16px; background: #f8f9fa; border-radius: 8px;">
                <table style="width: 100%; font-size: 14px;">
                    <tr>
                        <td style="padding: 6px 0; color: #666; width: 120px;">Email:</td>
                        <td style="padding: 6px 0; color: #333;">{html.escape(user_email)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;">Nickname:</td>
                        <td style="padding: 6px 0; color: #333;">{html.escape(user_nickname)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;">Method:</td>
                        <td style="padding: 6px 0; color: #333;">{method_display}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;">Time:</td>
                        <td style="padding: 6px 0; color: #333;">{now_str}</td>
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


async def _send_via_resend(settings, subject: str, html_content: str) -> bool:
    if resend is None:
        logger.error("resend package not installed, cannot send registration notification")
        return False

    resend.api_key = settings.resend_api_key
    params = {
        "from": f"{settings.smtp_from_name} <{settings.smtp_from_email}>",
        "to": [ADMIN_NOTIFICATION_EMAIL],
        "subject": subject,
        "html": html_content,
    }

    def _sync_send():
        with no_proxy():
            return resend.Emails.send(params)

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, _sync_send)
    return bool(response.get("id"))


async def _send_via_smtp(settings, subject: str, html_content: str) -> bool:
    if aiosmtplib is None:
        logger.error("aiosmtplib package not installed, cannot send registration notification")
        return False

    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = ADMIN_NOTIFICATION_EMAIL
    message["Subject"] = subject
    message.set_content("Please view this email in an HTML-capable email client.")
    message.add_alternative(html_content, subtype="html")

    tls_kwargs = {"use_tls": True} if settings.smtp_use_ssl else {"start_tls": settings.smtp_use_tls}
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        **tls_kwargs,
    )
    return True


def _build_activation_html(
    user_email: str,
    user_nickname: str,
    activation_code: str,
    expires_at: datetime,
    tier_name: str = "Alpha",
) -> str:
    """Build HTML content for activation notification email."""
    import html

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S UTC") if expires_at else "N/A"

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
                <h1 style="color: #2e7d32; font-size: 24px; margin: 0;">{html.escape(tier_name)} Activated</h1>
                <p style="color: #666; margin: 8px 0 0;">uStudy</p>
            </div>
            <div style="padding: 16px; background: #f8f9fa; border-radius: 8px;">
                <table style="width: 100%; font-size: 14px;">
                    <tr>
                        <td style="padding: 6px 0; color: #666; width: 140px;">Email:</td>
                        <td style="padding: 6px 0; color: #333;">{html.escape(user_email)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;">Nickname:</td>
                        <td style="padding: 6px 0; color: #333;">{html.escape(user_nickname)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;">Tier:</td>
                        <td style="padding: 6px 0; color: #333;">{html.escape(tier_name)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;">Activation Code:</td>
                        <td style="padding: 6px 0; color: #333; font-family: monospace;">{html.escape(activation_code)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;">Expires At:</td>
                        <td style="padding: 6px 0; color: #333;">{expires_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #666;">Activated At:</td>
                        <td style="padding: 6px 0; color: #333;">{now_str}</td>
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


async def send_activation_notification(
    settings,
    user_email: str,
    user_nickname: str,
    activation_code: str,
    expires_at: datetime,
    tier_name: str = "Alpha",
) -> bool:
    """Send a notification email when a user activates a subscription via activation code.

    Args:
        settings: App settings with email configuration.
        user_email: The activated user's email address.
        user_nickname: The activated user's nickname.
        activation_code: The code that was used.
        expires_at: When the subscription expires.
        tier_name: Display name of the activated tier.

    Returns:
        True if sent successfully, False otherwise.
        Failures are logged but never raise.
    """
    try:
        html_content = _build_activation_html(
            user_email=user_email,
            user_nickname=user_nickname,
            activation_code=activation_code,
            expires_at=expires_at,
            tier_name=tier_name,
        )
        subject = f"[uStudy] {tier_name} Activated: {user_nickname}"

        if settings.email_provider == "resend":
            ok = await _send_via_resend(settings, subject, html_content)
        else:
            ok = await _send_via_smtp(settings, subject, html_content)

        if ok:
            logger.info("Activation notification sent for %s", user_email)
        else:
            logger.warning("Activation notification failed for %s", user_email)
        return ok

    except Exception:
        logger.exception("Error sending activation notification for %s", user_email)
        return False


async def send_registration_notification(
    settings,
    user_email: str,
    user_nickname: str,
    registration_method: str,
) -> bool:
    """Send a notification email when a new user registers.

    Args:
        settings: App settings with email configuration.
        user_email: The new user's email address.
        user_nickname: The new user's nickname.
        registration_method: One of "email", "code", "apple".

    Returns:
        True if sent successfully, False otherwise.
        Failures are logged but never raise.
    """
    try:
        html_content = _build_notification_html(
            user_email=user_email,
            user_nickname=user_nickname,
            registration_method=registration_method,
        )
        subject = f"[uStudy] New Registration: {user_nickname} ({registration_method})"

        if settings.email_provider == "resend":
            ok = await _send_via_resend(settings, subject, html_content)
        else:
            ok = await _send_via_smtp(settings, subject, html_content)

        if ok:
            logger.info(
                "Registration notification sent for %s (%s)", user_email, registration_method
            )
        else:
            logger.warning(
                "Registration notification failed for %s (%s)", user_email, registration_method
            )
        return ok

    except Exception:
        logger.exception(
            "Error sending registration notification for %s (%s)",
            user_email,
            registration_method,
        )
        return False
