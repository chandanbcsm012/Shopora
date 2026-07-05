# Owned by the `addresses` module. Defines the Address SQLAlchemy model per
# docs/CONTRACTS.md's "Checkout, Addresses, Payments & Invoices" section.
#
# NOTE on module boundaries (docs/ARCHITECTURE.md): addresses may only be
# referenced by other modules through this module's service layer / Pydantic
# schemas, never its SQLAlchemy model directly. The `user_id` FK below
# references "users.id" by table name only (no import of auth's User model).
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin, UUIDPKMixin


class Address(UUIDPKMixin, TimestampMixin, Base):
    """addresses.Address — self-service address book entry, per
    docs/CONTRACTS.md. `address_type` is a plain validated string (Pydantic
    Literal in the schema layer), not a DB enum — kept simple since this is
    an unconstrained, low-cardinality free-form field with no other table
    referencing it. Hard delete only, no soft-delete anywhere in this app."""

    __tablename__ = "addresses"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    alternate_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    landmark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_instructions: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    address_type: Mapped[str] = mapped_column(String(20), nullable=False, default="home")
    is_default_shipping: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default_billing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # INR Currency & GST (foundation scope) addition: buyer's GSTIN, for B2B
    # orders. Nullable/optional -- format-validated (not checksum/government
    # lookup) in the Pydantic schema layer, see schemas.py.
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
