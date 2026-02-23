"""支付订单管理员通知邮件"""

from __future__ import annotations

import asyncio
import html
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


def _build_payment_notification_html(
    user_nickname: str,
    user_email: str,
    tier_name: str,
    cycle_name: str,
    amount_display: str,
    order_id: str,
    out_trade_no: str,
) -> str:
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
                <h1 style="color: #1677ff; font-size: 24px; margin: 0;">New Payment Order</h1>
                <p style="color: #666; margin: 8px 0 0;">uStudy</p>
            </div>
            <div style="padding: 16px; background: #f0f7ff; border-radius: 8px;
                        border-left: 4px solid #1677ff;">
                <table style="width: 100%; font-size: 14px;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 100px;">用户昵称:</td>
                        <td style="padding: 8px 0; color: #333; font-weight: 600;">
                            {html.escape(user_nickname)}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">用户邮箱:</td>
                        <td style="padding: 8px 0; color: #333;">{html.escape(user_email)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">订阅套餐:</td>
                        <td style="padding: 8px 0; color: #333; font-weight: 600;">
                            {html.escape(tier_name)} · {html.escape(cycle_name)}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">支付金额:</td>
                        <td style="padding: 8px 0; color: #e63946; font-size: 18px; font-weight: 700;">
                            {html.escape(amount_display)}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">订单号:</td>
                        <td style="padding: 8px 0; color: #333; font-family: monospace; font-size: 12px;">
                            {html.escape(out_trade_no)}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;">创建时间:</td>
                        <td style="padding: 8px 0; color: #333;">{now_str}</td>
                    </tr>
                </table>
            </div>
            <div style="text-align: center; margin-top: 20px;">
                <p style="color: #666; font-size: 13px; margin: 0;">
                    请核实收款后，在管理后台确认该订单。
                </p>
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
        logger.error("resend package not installed")
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
        logger.error("aiosmtplib package not installed")
        return False

    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = ADMIN_NOTIFICATION_EMAIL
    message["Subject"] = subject
    message.set_content("Please view this email in an HTML-capable email client.")
    message.add_alternative(html_content, subtype="html")

    tls_kwargs = (
        {"use_tls": True} if settings.smtp_use_ssl
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


async def send_payment_notification(
    settings,
    user_nickname: str,
    user_email: str,
    tier_name: str,
    cycle_name: str,
    amount_display: str,
    order_id: str,
    out_trade_no: str,
) -> bool:
    """发送支付订单通知邮件给管理员"""
    try:
        html_content = _build_payment_notification_html(
            user_nickname=user_nickname,
            user_email=user_email,
            tier_name=tier_name,
            cycle_name=cycle_name,
            amount_display=amount_display,
            order_id=order_id,
            out_trade_no=out_trade_no,
        )
        subject = f"[uStudy] 新订单: {user_nickname} - {tier_name} {cycle_name} {amount_display}"

        if settings.email_provider == "resend":
            ok = await _send_via_resend(settings, subject, html_content)
        else:
            ok = await _send_via_smtp(settings, subject, html_content)

        if ok:
            logger.info("Payment notification sent for order %s", out_trade_no)
        else:
            logger.warning("Payment notification failed for order %s", out_trade_no)
        return ok

    except Exception:
        logger.exception("Error sending payment notification for order %s", out_trade_no)
        return False
