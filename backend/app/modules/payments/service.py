"""Thin service-layer helpers `orders` uses to drive a Payment row's
lifecycle (create -> apply provider outcome -> optionally refund), per
docs/CONTRACTS.md. No standalone payment endpoints exist in this module —
`orders` drives everything through these functions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Payment
from .providers import PaymentOutcome, get_provider


async def create_payment(
    db: AsyncSession, order_id: str, method: str, amount_cents: int, currency: str
) -> Payment:
    payment = Payment(
        order_id=order_id,
        method=method,
        status="pending",
        amount_cents=amount_cents,
        currency=currency,
    )
    db.add(payment)
    await db.flush()
    return payment


async def apply_outcome(db: AsyncSession, payment: Payment, outcome: PaymentOutcome) -> Payment:
    payment.status = outcome.status
    if outcome.provider_reference is not None:
        payment.provider_reference = outcome.provider_reference
    if outcome.failure_reason is not None:
        payment.failure_reason = outcome.failure_reason
    db.add(payment)
    await db.flush()
    return payment


async def refund_payment(db: AsyncSession, payment: Payment, amount_cents: int) -> Payment:
    """Delegates to the payment method's provider, which raises
    `PAYMENT_NOT_REFUNDABLE` / `REFUND_EXCEEDS_PAYMENT_AMOUNT` as
    appropriate (see providers.py). Commits on success."""
    provider = get_provider(payment.method)
    outcome = await provider.refund(payment, amount_cents)

    payment.status = outcome.status
    payment.refunded_amount_cents += amount_cents
    if outcome.provider_reference is not None:
        payment.provider_reference = outcome.provider_reference
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def get_payment_for_order(db: AsyncSession, order_id: str) -> Payment | None:
    result = await db.execute(select(Payment).where(Payment.order_id == order_id))
    return result.scalar_one_or_none()
