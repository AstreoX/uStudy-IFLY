"""订阅定价表 — 单一数据源"""

from db.models import BillingCycle, SubscriptionTier

# (tier, cycle) → (amount_cents, subscription_days)
PRICING: dict[tuple[SubscriptionTier, BillingCycle], tuple[int, int]] = {
    (SubscriptionTier.BASIC, BillingCycle.MONTHLY): (1290, 30),
    (SubscriptionTier.BASIC, BillingCycle.SEMESTER): (3800, 120),
    (SubscriptionTier.BASIC, BillingCycle.YEARLY): (9200, 365),
    (SubscriptionTier.PREMIUM, BillingCycle.MONTHLY): (3690, 30),
    (SubscriptionTier.PREMIUM, BillingCycle.SEMESTER): (10800, 120),
    (SubscriptionTier.PREMIUM, BillingCycle.YEARLY): (26800, 365),
}
