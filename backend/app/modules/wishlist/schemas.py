"""Pydantic schemas for the wishlist module, per docs/CONTRACTS.md field
contract for WishlistItem. `WishlistItemOut` deliberately does NOT embed
product details — the frontend enriches by calling catalogApi.getProduct
per item, the same client-side enrichment pattern CartContext already
uses for cart line items."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WishlistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    created_at: datetime


class AddToWishlistRequest(BaseModel):
    product_id: str
