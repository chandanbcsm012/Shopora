# Owned by the `wishlist` module. Defines the WishlistItem SQLAlchemy model
# per docs/CONTRACTS.md's "Storefront: Homepage, Filtering, Wishlist &
# Static Pages (foundation scope)" section.
#
# NOTE on module boundaries (docs/ARCHITECTURE.md): wishlist may only be
# referenced by other modules through this module's service layer / Pydantic
# schemas, never its SQLAlchemy model directly. Both `user_id` and
# `product_id` below reference other modules' tables by table name only (no
# import of auth's User or catalog's Product model) — the same discipline
# every other module in this codebase follows for cross-module FKs.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, UUIDPKMixin, utcnow


class WishlistItem(UUIDPKMixin, Base):
    """wishlist.WishlistItem — id, user_id (FK users), product_id (FK
    products), created_at, per docs/CONTRACTS.md. Unique constraint on
    (user_id, product_id): wishlisting an already-wishlisted product is
    idempotent (service layer returns the existing row rather than trying
    to insert a duplicate), not a conflict error. No `updated_at` (unlike
    `TimestampMixin`-based models elsewhere) — a wishlist entry is either
    present or absent, nothing on it ever changes after creation."""

    __tablename__ = "wishlist_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_wishlist_items_user_product"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
