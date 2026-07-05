# Owned by the `payments` module. Defines the Payment SQLAlchemy model per
# docs/CONTRACTS.md's "Checkout, Addresses, Payments & Invoices" section.
#
# NOTE on module boundaries (docs/ARCHITECTURE.md): the `order_id` FK below
# references "orders.id" by table name only (no import of orders' Order
# model, no relationship() crossing into it) — same discipline as every
# other cross-module FK in this app.
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin, UUIDPKMixin


class Payment(UUIDPKMixin, TimestampMixin, Base):
    """payments.Payment — one payment per order in this scope (unique
    order_id), per docs/CONTRACTS.md. `method`/`status` are plain validated
    strings (Pydantic Literal at the schema/provider layer), not DB enums —
    simple and sufficient for this foundation scope."""

    __tablename__ = "payments"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), nullable=False, unique=True, index=True
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    refunded_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
