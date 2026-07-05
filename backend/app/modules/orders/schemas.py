"""Pydantic schemas for the orders module (cart + checkout + order history)
per docs/CONTRACTS.md field contract."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.modules.addresses.schemas import AddressOut
from app.modules.orders.models import OrderStatus


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    quantity: int
    unit_price_cents: int

    @computed_field  # type: ignore[misc]
    @property
    def line_total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


class CartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    items: list[CartItemOut]

    @computed_field  # type: ignore[misc]
    @property
    def subtotal_cents(self) -> int:
        return sum(item.line_total_cents for item in self.items)


class AddCartItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(gt=0)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    product_name_snapshot: str
    sku_snapshot: str
    quantity: int
    unit_price_cents: int

    @computed_field  # type: ignore[misc]
    @property
    def line_total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: OrderStatus
    total_cents: int
    currency: str
    items: list[OrderItemOut]
    created_at: datetime
    shipping_address: AddressOut | None = None
    billing_address: AddressOut | None = None
    payment_status: str | None = None
    invoice_number: str | None = None
    # INR Currency & GST (foundation scope): all null unless
    # `order.currency == "INR"` and GST was applicable at checkout time.
    taxable_amount_cents: int | None = None
    cgst_cents: int | None = None
    sgst_cents: int | None = None
    igst_cents: int | None = None
    tax_total_cents: int | None = None
    grand_total_cents: int | None = None


class OrderStatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    from_status: str | None = None
    to_status: str
    note: str | None = None
    created_at: datetime


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    sequence_number: int
    created_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def invoice_number(self) -> str:
        return f"INV-{self.sequence_number:06d}"


# ---------------------------------------------------------------------------
# Checkout, Addresses, Payments & Invoices (foundation scope) additions.
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    shipping_address_id: str
    billing_address_id: str
    payment_method: Literal["cod", "test_card"]
    test_card_outcome: Literal["succeed", "decline"] = "succeed"


class AdminOrderStatusUpdate(BaseModel):
    status: Literal["pending", "paid", "shipped", "delivered", "cancelled"]
    note: str | None = None


class RefundRequest(BaseModel):
    amount_cents: int | None = None
