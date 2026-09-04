"""SMTP-only email delivery for authentication verification codes."""

from __future__ import annotations

from email.message import EmailMessage
from typing import Protocol

try:
    import aiosmtplib
except ImportError:  # pragma: no cover - optional dependency
    aiosmtplib = None

from tenacity import retry, stop_after_attempt, wait_exponential


class EmailProvider(Protocol):
    async def send_verification_email(self, to: str, code: str) -> bool: ...


class SMTPEmailProvider:
    """阿里云 SMTP 验证码邮件实现。"""

    def __init__(self, host: str, port: int, username: str, password: str,
                 from_email: str, from_name: str, use_tls: bool = True,
                 use_ssl: bool = False):
        if aiosmtplib is None:
            raise RuntimeError("aiosmtplib package not installed")
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.use_tls = use_tls
        self.use_ssl = use_ssl

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def send_verification_email(self, to: str, code: str) -> bool:
        message = EmailMessage()
        message["From"] = f"{self.from_name} <{self.from_email}>"
        message["To"] = to
        message["Subject"] = "【uStudy】您的验证码"
        message.set_content(f"您的验证码是: {code}，10分钟内有效。")
        message.add_alternative(self._get_verification_email_html(code), subtype="html")
        tls_kwargs = {"use_tls": True} if self.use_ssl else {"start_tls": self.use_tls}
        await aiosmtplib.send(message, hostname=self.host, port=self.port,
                              username=self.username, password=self.password, **tls_kwargs)
        return True

    @staticmethod
    def _get_verification_email_html(code: str) -> str:
        return f"""<!DOCTYPE html><html><head><meta charset=\"UTF-8\"></head>
<body style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;\">
<div style=\"text-align: center; margin-bottom: 30px;\"><h1>uStudy</h1></div>
<div style=\"background: #f8f9fa; border-radius: 12px; padding: 30px; text-align: center;\">
<p style=\"color: #666; font-size: 16px;\">您的验证码是：</p>
<div style=\"font-size: 36px; font-weight: bold; color: #333; background: #fff; padding: 20px 40px; border-radius: 8px; letter-spacing: 8px; display: inline-block;\">{code}</div>
<p style=\"color: #999; font-size: 14px; margin-top: 20px;\">验证码 10 分钟内有效，请勿泄露给他人</p></div>
<p style=\"color: #999; font-size: 12px; text-align: center; margin-top: 30px;\">如果您没有请求此验证码，请忽略此邮件</p></body></html>"""


def get_email_provider(settings) -> EmailProvider:
    return SMTPEmailProvider(host=settings.smtp_host, port=settings.smtp_port,
                             username=settings.smtp_username, password=settings.smtp_password,
                             from_email=settings.smtp_from_email, from_name=settings.smtp_from_name,
                             use_tls=settings.smtp_use_tls, use_ssl=settings.smtp_use_ssl)
