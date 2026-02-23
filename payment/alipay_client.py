"""支付宝客户端封装 — 基于 python-alipay-sdk"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path

from alipay import AliPay
from alipay.utils import AliPayConfig

from config import get_settings
from payment.exceptions import AlipayError

logger = logging.getLogger(__name__)


def _ensure_pem_format(key_string: str, key_type: str) -> str:
    """确保密钥是 PEM 格式，支付宝开放平台下载的可能是裸 Base64 字符串"""
    key_string = key_string.strip()
    if key_string.startswith("-----"):
        return key_string
    # 裸 Base64 字符串，补全 PEM 头尾
    if key_type == "private":
        return (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            + key_string
            + "\n-----END RSA PRIVATE KEY-----"
        )
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        + key_string
        + "\n-----END PUBLIC KEY-----"
    )


@lru_cache
def _get_alipay_client() -> AliPay:
    """获取支付宝客户端单例"""
    settings = get_settings()

    if not settings.alipay_app_id:
        raise AlipayError("ALIPAY_APP_ID not configured")

    private_key_path = Path(settings.alipay_app_private_key_path)
    public_key_path = Path(settings.alipay_public_key_path)

    if not private_key_path.exists():
        raise AlipayError(f"Alipay private key not found: {private_key_path}")
    if not public_key_path.exists():
        raise AlipayError(f"Alipay public key not found: {public_key_path}")

    app_private_key_string = _ensure_pem_format(
        private_key_path.read_text(encoding="utf-8"), "private"
    )
    alipay_public_key_string = _ensure_pem_format(
        public_key_path.read_text(encoding="utf-8"), "public"
    )

    return AliPay(
        appid=settings.alipay_app_id,
        app_notify_url=settings.alipay_notify_url or None,
        app_private_key_string=app_private_key_string,
        alipay_public_key_string=alipay_public_key_string,
        sign_type=settings.alipay_sign_type,
        debug=settings.alipay_debug,
        verbose=False,
        config=AliPayConfig(timeout=15),
    )


def get_alipay_client() -> AliPay:
    return _get_alipay_client()


async def create_alipay_page_url(
    out_trade_no: str,
    total_amount: str,
    subject: str,
    return_url: str | None = None,
) -> str:
    """生成支付宝电脑网站支付 URL（在线程池中执行同步 SDK 调用）"""
    settings = get_settings()
    client = get_alipay_client()

    def _build_url() -> str:
        order_string = client.api_alipay_trade_page_pay(
            out_trade_no=out_trade_no,
            total_amount=total_amount,
            subject=subject,
            return_url=return_url or settings.alipay_return_url or None,
            notify_url=settings.alipay_notify_url or None,
        )
        gateway = (
            "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
            if settings.alipay_debug
            else "https://openapi.alipay.com/gateway.do"
        )
        return f"{gateway}?{order_string}"

    return await asyncio.to_thread(_build_url)


async def verify_alipay_notification(data: dict) -> bool:
    """验证支付宝异步通知签名"""
    settings = get_settings()
    sign_type = data.get("sign_type")
    if sign_type != settings.alipay_sign_type:
        logger.warning(f"Unexpected sign_type: expected {settings.alipay_sign_type}, got {sign_type}")
        return False

    client = get_alipay_client()

    def _verify() -> bool:
        return client.verify(data, data.get("sign"))

    return await asyncio.to_thread(_verify)
