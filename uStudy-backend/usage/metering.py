"""Central LLM usage metering for the experiment fork."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
from typing import Any
from uuid import UUID

from sqlalchemy import select

from db.database import get_scoped_session
from usage.models import ApiUsageLog, UsageType
from usage.recorder import DEFAULT_PRICING, MODEL_PRICING, _estimate_cost_cents

# Kept only for historical cost-estimation fields in usage logs. No billing is performed.
USD_TO_CNY = "7.30"
LLM_CHARGE_MULTIPLIER = "2.0"

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UsageContext:
    """Business context for one or more LLM calls."""

    user_id: UUID | None
    usage_type: UsageType
    source_module: str
    source_operation: str
    billable: bool = True
    space_id: UUID | None = None
    conversation_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UsageResult:
    """Persisted usage and billing result."""

    usage_log_id: UUID
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_cents: int
    charge_cents: int
    billing_status: str
    wallet_transaction_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "usage_log_id": str(self.usage_log_id),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_cents": self.estimated_cost_cents,
            "charge_cents": self.charge_cents,
            "billing_status": self.billing_status,
            "wallet_transaction_id": (
                str(self.wallet_transaction_id) if self.wallet_transaction_id else None
            ),
        }


def _usage_value(usage: Any, key: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(key, 0) or 0)
    return int(getattr(usage, key, 0) or 0)


def estimate_llm_charge_cents(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> int:
    """Estimate RMB wallet charge in cents from provider USD token rates."""
    total_tokens = prompt_tokens + completion_tokens
    if total_tokens <= 0:
        return 0

    input_rate, output_rate = MODEL_PRICING.get(model, DEFAULT_PRICING)
    usd_cost = (
        Decimal(prompt_tokens) * Decimal(str(input_rate))
        + Decimal(completion_tokens) * Decimal(str(output_rate))
    ) / Decimal(1_000_000)
    charge_yuan = (
        usd_cost
        * Decimal(USD_TO_CNY)
        * Decimal(LLM_CHARGE_MULTIPLIER)
    )
    charge_cents = int((charge_yuan * Decimal(100)).to_integral_value(rounding=ROUND_CEILING))
    return max(1, charge_cents)


def make_usage_idempotency_key(
    context: UsageContext | None,
    *,
    model: str,
    operation_salt: str | None = None,
) -> str:
    if operation_salt:
        return operation_salt
    prefix = "llm"
    if context:
        prefix = f"{context.source_module}:{context.source_operation}"
    return f"{prefix}:{model}:{uuid.uuid4().hex}"


async def record_and_charge_usage(
    *,
    context: UsageContext | None,
    model: str,
    usage: Any,
    idempotency_key: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> UsageResult | None:
    """Record LLM usage and charge wallet when context is billable."""
    if context is None:
        return None

    prompt_tokens = _usage_value(usage, "prompt_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens")
    total_tokens = _usage_value(usage, "total_tokens") or (
        prompt_tokens + completion_tokens
    )
    if total_tokens <= 0 and prompt_tokens <= 0 and completion_tokens <= 0:
        return None

    key = idempotency_key or make_usage_idempotency_key(context, model=model)
    metadata = dict(context.metadata or {})
    metadata.update(extra_metadata or {})
    estimated_cost_cents = _estimate_cost_cents(
        model, prompt_tokens, completion_tokens
    )
    # The experiment records usage for observability; paid wallet charging is removed.
    wallet_billing_enabled = False
    charge_cents = 0

    async with get_scoped_session() as db:
        existing = await db.execute(
            select(ApiUsageLog).where(ApiUsageLog.idempotency_key == key)
        )
        existing_log = existing.scalar_one_or_none()
        if existing_log:
            return UsageResult(
                usage_log_id=existing_log.id,
                prompt_tokens=existing_log.prompt_tokens,
                completion_tokens=existing_log.completion_tokens,
                total_tokens=existing_log.total_tokens,
                estimated_cost_cents=existing_log.estimated_cost_cents,
                charge_cents=existing_log.charge_cents,
                billing_status=existing_log.billing_status,
                wallet_transaction_id=existing_log.wallet_transaction_id,
            )

        wallet_tx = None
        billing_status = (
            "disabled"
            if context.billable and not wallet_billing_enabled
            else "not_billable"
        )
        log = ApiUsageLog(
            user_id=context.user_id,
            space_id=context.space_id,
            conversation_id=context.conversation_id,
            usage_type=context.usage_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_cents=estimated_cost_cents,
            source_module=context.source_module,
            source_operation=context.source_operation,
            billable=context.billable,
            charge_cents=charge_cents if billing_status == "charged" else 0,
            billing_status=billing_status,
            wallet_transaction_id=wallet_tx.id if wallet_tx else None,
            idempotency_key=key,
            request_metadata=metadata or None,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

    return UsageResult(
        usage_log_id=log.id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_cents=estimated_cost_cents,
        charge_cents=log.charge_cents,
        billing_status=log.billing_status,
        wallet_transaction_id=log.wallet_transaction_id,
    )
