"""
一次性种子脚本：将现有前端 QR 码图片注册到 payment_qr_codes 表。

用法（在 Docker 容器内执行）：
    python scripts/seed_qr_codes.py

前提：QR 码图片已复制到 static/payment/ 目录中。
"""

import asyncio
import sys
from pathlib import Path

# 让脚本在项目根目录下可以正确导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from db.database import get_scoped_session
from db.models import BillingCycle, PaymentQrCode, SubscriptionTier

# (tier, billing_cycle, pay_method, display_filename, save_filename)
SEED_DATA = [
    # BASIC (Plus) — alipay
    (SubscriptionTier.BASIC, BillingCycle.MONTHLY, "alipay",
     "alipay-qr-month-plus(12-9).png", "save-alipay-qr-month-plus(12-9).jpg"),
    (SubscriptionTier.BASIC, BillingCycle.SEMESTER, "alipay",
     "alipay-qr-4-month-plus(38).png", "save-alipay-qr-4-month-plus(38).jpg"),
    (SubscriptionTier.BASIC, BillingCycle.YEARLY, "alipay",
     "alipay-qr-year-plus(92).png", "save-alipay-qr-year-plus(92).jpg"),
    # BASIC (Plus) — wechat
    (SubscriptionTier.BASIC, BillingCycle.MONTHLY, "wechat",
     "wechat-qr-month-plus(12-9).png", "save-wechat-qr-month-plus(12-9).png"),
    (SubscriptionTier.BASIC, BillingCycle.SEMESTER, "wechat",
     "wechat-qr-4-month-plus(38).png", "save-wechat-qr-4-month-plus(38).png"),
    (SubscriptionTier.BASIC, BillingCycle.YEARLY, "wechat",
     "wechat-qr-year-plus(92).png", "save-wechat-qr-year-plus(92).png"),
    # PREMIUM (Ultra) — alipay
    (SubscriptionTier.PREMIUM, BillingCycle.MONTHLY, "alipay",
     "alipay-qr-month-ultra(36-9).png", "save-alipay-qr-month-ultra(36-9).jpg"),
    (SubscriptionTier.PREMIUM, BillingCycle.SEMESTER, "alipay",
     "alipay-qr-4-month-ultra(108).png", "save-alipay-qr-4-month-ultra(108).jpg"),
    (SubscriptionTier.PREMIUM, BillingCycle.YEARLY, "alipay",
     "alipay-qr-year-ultra(268).png", "save-alipay-qr-year-ultra(268).jpg"),
    # PREMIUM (Ultra) — wechat
    (SubscriptionTier.PREMIUM, BillingCycle.MONTHLY, "wechat",
     "wechat-qr-month-ultra(36-9).png", "save-wechat-qr-month-ultra(36-9).png"),
    (SubscriptionTier.PREMIUM, BillingCycle.SEMESTER, "wechat",
     "wechat-qr-4-month-ultra(108).png", "save-wechat-qr-4-month-ultra(108).png"),
    (SubscriptionTier.PREMIUM, BillingCycle.YEARLY, "wechat",
     "wechat-qr-year-ultra(268).png", "save-wechat-qr-year-ultra(268).png"),
]

STATIC_DIR = Path("static/payment")


async def seed():
    missing_files = []
    for _, _, _, display, save in SEED_DATA:
        if not (STATIC_DIR / display).exists():
            missing_files.append(display)
        if not (STATIC_DIR / save).exists():
            missing_files.append(save)

    if missing_files:
        print(f"[ERROR] 缺少 {len(missing_files)} 个文件:")
        for f in missing_files:
            print(f"  - static/payment/{f}")
        print("\n请先将 QR 码图片复制到 static/payment/ 目录。")
        sys.exit(1)

    inserted = 0
    skipped = 0

    async with get_scoped_session() as session:
        for tier, cycle, method, display, save in SEED_DATA:
            result = await session.execute(
                select(PaymentQrCode).where(
                    PaymentQrCode.tier == tier,
                    PaymentQrCode.billing_cycle == cycle,
                    PaymentQrCode.pay_method == method,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  [SKIP] {tier.value}/{cycle.value}/{method} — 已存在")
                skipped += 1
                continue

            row = PaymentQrCode(
                tier=tier,
                billing_cycle=cycle,
                pay_method=method,
                display_filename=display,
                save_filename=save,
            )
            session.add(row)
            print(f"  [ADD]  {tier.value}/{cycle.value}/{method} → {display}")
            inserted += 1

        await session.commit()

    print(f"\n完成: 插入 {inserted} 条, 跳过 {skipped} 条")


if __name__ == "__main__":
    print("=== Seed payment_qr_codes ===\n")
    asyncio.run(seed())
