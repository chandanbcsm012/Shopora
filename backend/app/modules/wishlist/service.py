"""Business logic for the wishlist module: list/add/remove a user's own
wishlist items, per docs/CONTRACTS.md."""
from __future__ import annotations

from fastapi import status
from sqlalchemy import column, delete, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.shared.error_codes import ErrorCode

from .models import WishlistItem

# Raw core Table (not an ORM model import) used solely to check whether a
# product exists before wishlisting it — wishlist may not import catalog's
# SQLAlchemy models per docs/ARCHITECTURE.md's rule that a module may only
# reach another module's *tables* via raw FK columns / ad hoc reads by table
# name, never its SQLAlchemy model class. Mirrors the identical technique
# `catalog.service`'s `_order_items_table`/`_cart_items_table` and
# `orders.service`'s `_products_table` already use.
_products_table = table("products", column("id"))


async def list_wishlist(db: AsyncSession, user_id: str) -> list[WishlistItem]:
    result = await db.execute(
        select(WishlistItem)
        .where(WishlistItem.user_id == user_id)
        .order_by(WishlistItem.created_at.desc())
    )
    return list(result.scalars().all())


async def add_to_wishlist(db: AsyncSession, user_id: str, product_id: str) -> WishlistItem:
    """Validates the product exists (via a raw Core table reference to
    `products`) but does NOT require it to be active — a customer can
    wishlist something that later goes out of stock or inactive and still
    see it listed, mirroring how cart/orders already handle "product no
    longer available" gracefully. If (user_id, product_id) already exists,
    returns the existing row instead of trying to insert a duplicate
    (query-then-insert-if-absent, not insert-and-catch-IntegrityError)."""
    existing = (
        await db.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == user_id, WishlistItem.product_id == product_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    product_exists = (
        await db.execute(select(_products_table.c.id).where(_products_table.c.id == product_id))
    ).scalar_one_or_none()
    if product_exists is None:
        raise AppError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Product not found",
            status.HTTP_404_NOT_FOUND,
            {"product_id": product_id},
        )

    item = WishlistItem(user_id=user_id, product_id=product_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def remove_from_wishlist(db: AsyncSession, user_id: str, product_id: str) -> None:
    """Idempotent — 204 whether or not it was actually wishlisted, and
    never touches another user's row for the same product_id."""
    await db.execute(
        delete(WishlistItem).where(
            WishlistItem.user_id == user_id, WishlistItem.product_id == product_id
        )
    )
    await db.commit()
