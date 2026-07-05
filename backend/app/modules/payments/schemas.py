"""Pydantic schemas for the payments module, per docs/CONTRACTS.md field
contract for Payment. `PaymentOutcome` (the provider adapter's return type)
lives in `providers.py` alongside the provider protocol/implementations, not
here — see that file."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PaymentMethod = Literal["cod", "test_card"]

PaymentStatus = Literal[
    "pending",
    "authorized",
    "captured",
    "failed",
    "cancelled",
    "refunded",
    "partially_refunded",
    "expired",
]


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    method: str
    status: str
    amount_cents: int
    currency: str
    refunded_amount_cents: int
    provider_reference: str | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime
