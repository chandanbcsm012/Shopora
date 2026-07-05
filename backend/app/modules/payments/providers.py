"""Payment provider adapter interface, per docs/CONTRACTS.md. Built so a
real gateway (Stripe/Razorpay/etc.) can implement `PaymentProvider` later
without touching `orders`' checkout/refund logic.

`TestCardProvider` is a simulated card-payment path for this foundation
scope only: it intentionally has NO card-number/expiry/CVV field or
parameter anywhere — it only ever takes an `outcome: Literal["succeed",
"decline"]` chosen by the caller (there is nothing to "process" for real).
"""
from __future__ import annotations

from typing import ClassVar, Literal, Protocol
from uuid import uuid4

from fastapi import status
from pydantic import BaseModel

from app.core.errors import AppError
from app.shared.error_codes import ErrorCode

from .models import Payment


class PaymentOutcome(BaseModel):
    status: str  # one of the Payment.status values
    provider_reference: str | None = None
    failure_reason: str | None = None


class PaymentProvider(Protocol):
    method: ClassVar[str]

    async def process(self, payment: Payment, **kwargs) -> PaymentOutcome: ...

    async def refund(self, payment: Payment, amount_cents: int) -> PaymentOutcome: ...


class CODProvider:
    """Cash on delivery: nothing is captured until the courier collects
    cash, so `process()` always leaves the payment `pending`."""

    method: ClassVar[str] = "cod"

    async def process(self, payment: Payment, **kwargs) -> PaymentOutcome:
        return PaymentOutcome(status="pending")

    async def refund(self, payment: Payment, amount_cents: int) -> PaymentOutcome:
        # Nothing was ever captured for a COD payment, so there is nothing
        # to refund regardless of amount/current status.
        raise AppError(
            ErrorCode.PAYMENT_NOT_REFUNDABLE,
            "Cash-on-delivery payments have nothing captured to refund.",
            status.HTTP_409_CONFLICT,
        )


class TestCardProvider:
    """Simulated card payment for demo/testing only. Does not collect or
    accept any real card number/expiry/CVV — there is no card-data field
    anywhere in this method."""

    method: ClassVar[str] = "test_card"

    async def process(
        self, payment: Payment, outcome: Literal["succeed", "decline"] = "succeed", **kwargs
    ) -> PaymentOutcome:
        if outcome == "succeed":
            return PaymentOutcome(
                status="captured", provider_reference=f"TEST-{uuid4().hex[:12]}"
            )
        return PaymentOutcome(
            status="failed", failure_reason="Test card declined (simulated)"
        )

    async def refund(self, payment: Payment, amount_cents: int) -> PaymentOutcome:
        if payment.status not in ("captured", "partially_refunded"):
            raise AppError(
                ErrorCode.PAYMENT_NOT_REFUNDABLE,
                f"Payment in status '{payment.status}' cannot be refunded.",
                status.HTTP_409_CONFLICT,
            )

        remaining = payment.amount_cents - payment.refunded_amount_cents
        if amount_cents > remaining:
            raise AppError(
                ErrorCode.REFUND_EXCEEDS_PAYMENT_AMOUNT,
                f"Refund amount {amount_cents} exceeds the remaining refundable amount {remaining}.",
                status.HTTP_409_CONFLICT,
            )

        new_status = "refunded" if amount_cents == remaining else "partially_refunded"
        return PaymentOutcome(
            status=new_status, provider_reference=f"TEST-REFUND-{uuid4().hex[:12]}"
        )


_PROVIDERS: dict[str, PaymentProvider] = {
    CODProvider.method: CODProvider(),
    TestCardProvider.method: TestCardProvider(),
}


def get_provider(method: str) -> PaymentProvider:
    provider = _PROVIDERS.get(method)
    if provider is None:
        raise AppError(
            ErrorCode.INVALID_PAYMENT_METHOD,
            f"Unsupported payment method '{method}'.",
            status.HTTP_400_BAD_REQUEST,
        )
    return provider
