"""Pydantic schemas for the catalog module, per docs/CONTRACTS.md field
contracts for Category, Brand, Product, and ProductImage."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: str | None = None
    image_url: str | None = None


class CategoryUpdate(BaseModel):
    """All fields optional; only provided fields are updated."""

    name: str | None = None
    slug: str | None = None
    parent_id: str | None = None
    image_url: str | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    parent_id: str | None = None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
class BrandCreate(BaseModel):
    name: str
    slug: str


class BrandUpdate(BaseModel):
    """All fields optional; only provided fields are updated. No image
    field on Brand (per docs/CONTRACTS.md)."""

    name: str | None = None
    slug: str | None = None


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# ProductImage
# ---------------------------------------------------------------------------
class ProductImageCreate(BaseModel):
    url: str
    alt_text: str | None = None
    sort_order: int = 0


class ProductImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    url: str
    alt_text: str | None = None
    sort_order: int


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    brand_id: str | None = None
    category_id: str
    price_cents: int
    currency: str = "USD"
    sku: str
    stock_quantity: int = 0
    is_active: bool = True
    images: list[ProductImageCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """All fields optional; only provided fields are updated."""

    name: str | None = None
    slug: str | None = None
    description: str | None = None
    brand_id: str | None = None
    category_id: str | None = None
    price_cents: int | None = None
    currency: str | None = None
    sku: str | None = None
    stock_quantity: int | None = None
    is_active: bool | None = None
    images: list[ProductImageCreate] | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None = None
    brand_id: str | None = None
    category_id: str
    price_cents: int
    currency: str
    sku: str
    stock_quantity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    images: list[ProductImageOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cross-module contract: consumed by the `orders` module. Keep this minimal
# and stable — see service.get_available_product().
# ---------------------------------------------------------------------------
class ProductOrderView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    price_cents: int
    currency: str
    stock_quantity: int
