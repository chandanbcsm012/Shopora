# Owned by the Database Team. Define Cart, CartItem, Order, OrderItem,
# OrderStatusHistory, and Invoice SQLAlchemy models here per
# docs/CONTRACTS.md.
#
# NOTE on module boundaries (docs/ARCHITECTURE.md): orders may only call
# catalog/auth/addresses/payments through their service layers, never import
# their SQLAlchemy models directly. FKs below reference "users.id" /
# "products.id" / "addresses.id" by table name (resolved at DB level via
# Alembic/metadata), not by importing the User/Product/Address classes, and
# there are intentionally no relationship() declarations crossing into those
# other modules' models.
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, event, func, select
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin, UUIDPKMixin, utcnow


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Cart(UUIDPKMixin, TimestampMixin, Base):
    """orders.Cart — id, user_id (FK users, unique), created_at, updated_at
    (per docs/CONTRACTS.md). Unique on user_id: one cart per user."""

    __tablename__ = "carts"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(UUIDPKMixin, Base):
    """orders.CartItem — id, cart_id (FK carts), product_id (FK products),
    quantity, unit_price_cents (per docs/CONTRACTS.md)."""

    __tablename__ = "cart_items"

    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")


class Order(UUIDPKMixin, TimestampMixin, Base):
    """orders.Order — id, user_id (FK users), status, total_cents,
    currency, created_at, updated_at (per docs/CONTRACTS.md). status enum:
    pending, paid, shipped, delivered, cancelled.

    `shipping_address_id`/`billing_address_id` (Checkout/Addresses/Payments
    addition): nullable raw FKs to `addresses.id` — nullable because
    existing rows predate this column; the API layer requires both for new
    checkouts, the DB does not enforce it. No cross-module model import/
    relationship, same discipline as `user_id` above."""

    __tablename__ = "orders"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(
            OrderStatus,
            name="order_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=OrderStatus.PENDING,
    )
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    shipping_address_id: Mapped[str | None] = mapped_column(
        ForeignKey("addresses.id"), nullable=True, index=True
    )
    billing_address_id: Mapped[str | None] = mapped_column(
        ForeignKey("addresses.id"), nullable=True, index=True
    )
    # INR Currency & GST (foundation scope) additions -- all nullable for
    # backward compatibility. `total_cents` above keeps its existing meaning
    # (sum of line items, pre-tax) unchanged; when GST applies,
    # `grand_total_cents` is the actual tax-inclusive amount
    # charged/displayed as the order's bottom line. Populated only when
    # `order.currency == "INR"` and `calculate_gst` (orders/tax.py) returns a
    # breakdown; left null otherwise (GST disabled, non-INR currency, or no
    # buyer state to compute against).
    taxable_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cgst_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sgst_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    igst_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grand_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(UUIDPKMixin, Base):
    """orders.OrderItem — id, order_id (FK orders), product_id (FK
    products), product_name_snapshot, sku_snapshot, quantity,
    unit_price_cents (per docs/CONTRACTS.md). `sku_snapshot` (Checkout/
    Addresses/Payments addition) is populated at checkout time alongside
    `product_name_snapshot`, from the same source, so invoices can show a
    real SKU."""

    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderStatusHistory(UUIDPKMixin, Base):
    """orders.OrderStatusHistory — id, order_id (FK orders), from_status
    (nullable — null for the initial creation), to_status, note (nullable),
    created_at (per docs/CONTRACTS.md). Append-only, no `updated_at`. Every
    `Order.status` write, anywhere, inserts one of these in the same
    transaction — never update `Order.status` without a matching history
    row."""

    __tablename__ = "order_status_history"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Invoice(UUIDPKMixin, Base):
    """orders.Invoice — id, order_id (FK orders, unique), sequence_number
    (Integer, Identity(start=1), unique, not null — safe concurrent
    auto-increment, NOT tied to the UUID primary key), created_at (per
    docs/CONTRACTS.md). The human-readable `invoice_number` (e.g.
    `INV-000123`) is a `@computed_field` in the Pydantic schema, not a
    stored column — see schemas.py. Created only when an order's payment
    succeeds."""

    __tablename__ = "invoices"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id"), nullable=False, unique=True, index=True
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer, Identity(start=1), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


@event.listens_for(Invoice, "before_insert")
def _assign_sequence_number_for_non_identity_backends(mapper, connection, target) -> None:
    """`Identity()` (the safe, concurrent, server-generated auto-increment
    per docs/CONTRACTS.md) is a PostgreSQL/Oracle/MSSQL feature -- SQLite
    (used only for this app's fast in-memory unit/router tests, never
    production) silently drops it at DDL time, leaving `sequence_number`
    with no default and no way to populate itself, which raises a NOT NULL
    violation on insert. On any non-PostgreSQL connection only, compute a
    fallback value here instead; real PostgreSQL connections are untouched
    and keep relying on the server-side IDENTITY column exactly as
    intended (verified against real Postgres via `alembic upgrade head`)."""
    if target.sequence_number is not None or connection.dialect.name == "postgresql":
        return
    current_max = connection.execute(
        select(func.coalesce(func.max(Invoice.__table__.c.sequence_number), 0))
    ).scalar_one()
    target.sequence_number = current_max + 1
