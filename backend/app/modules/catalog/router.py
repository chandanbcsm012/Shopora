"""Catalog HTTP routes. Mounted at /api/v1 by the Main Coordinator in
app/main.py (paths here carry no prefix of their own)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_role
from app.shared.pagination import Page, PageParams

from . import service
from .schemas import (
    BrandCreate,
    BrandOut,
    BrandUpdate,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from .service import ProductSort

router = APIRouter()

# Resolved once at import time so tests can override this exact dependency
# callable via app.dependency_overrides[require_admin] = ...
require_admin = require_role("admin", "super_admin", "manager")


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut])
async def get_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryOut]:
    categories = await service.list_categories(db)
    return [CategoryOut.model_validate(c) for c in categories]


@router.post("/categories", response_model=CategoryOut, status_code=201)
async def post_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> CategoryOut:
    category = await service.create_category(db, payload)
    return CategoryOut.model_validate(category)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def patch_category(
    category_id: str,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> CategoryOut:
    category = await service.update_category(db, category_id, payload)
    return CategoryOut.model_validate(category)


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> None:
    await service.delete_category(db, category_id)


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------


@router.get("/brands", response_model=list[BrandOut])
async def get_brands(db: AsyncSession = Depends(get_db)) -> list[BrandOut]:
    brands = await service.list_brands(db)
    return [BrandOut.model_validate(b) for b in brands]


@router.post("/brands", response_model=BrandOut, status_code=201)
async def post_brand(
    payload: BrandCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> BrandOut:
    brand = await service.create_brand(db, payload)
    return BrandOut.model_validate(brand)


@router.patch("/brands/{brand_id}", response_model=BrandOut)
async def patch_brand(
    brand_id: str,
    payload: BrandUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> BrandOut:
    brand = await service.update_brand(db, brand_id, payload)
    return BrandOut.model_validate(brand)


@router.delete("/brands/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> None:
    await service.delete_brand(db, brand_id)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get("/products", response_model=Page[ProductOut])
async def get_products(
    category_id: str | None = None,
    brand_id: str | None = None,
    q: str | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    in_stock_only: bool = False,
    sort: ProductSort = "newest",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> Page[ProductOut]:
    params = PageParams(page=page, page_size=page_size)
    items, total = await service.list_products(
        db,
        params,
        category_id=category_id,
        brand_id=brand_id,
        q=q,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        in_stock_only=in_stock_only,
        sort=sort,
    )
    return Page[ProductOut](
        items=[ProductOut.model_validate(p) for p in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)) -> ProductOut:
    # Public route: an inactive product 404s exactly like a missing one, so
    # it isn't still viewable/purchasable via a direct link once hidden.
    product = await service.get_active_product_or_404(db, product_id)
    return ProductOut.model_validate(product)


@router.post("/products", response_model=ProductOut, status_code=201)
async def post_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> ProductOut:
    product = await service.create_product(db, payload)
    return ProductOut.model_validate(product)


@router.patch("/products/{product_id}", response_model=ProductOut)
async def patch_product(
    product_id: str,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> ProductOut:
    product = await service.update_product(db, product_id, payload)
    return ProductOut.model_validate(product)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> None:
    await service.delete_product(db, product_id)


# ---------------------------------------------------------------------------
# Admin-only product views (mirrors the auth/orders `router`/`admin_router`
# split): the public routes above always exclude inactive products; the
# admin panel needs to see and manage them (e.g. to reactivate one), so it
# gets its own listing/detail routes rather than a client-controllable
# query param on the public endpoint that would just move the same leak.
# ---------------------------------------------------------------------------
admin_router = APIRouter()


@admin_router.get("/admin/products", response_model=Page[ProductOut])
async def admin_get_products(
    category_id: str | None = None,
    brand_id: str | None = None,
    q: str | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    in_stock_only: bool = False,
    sort: ProductSort = "newest",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> Page[ProductOut]:
    params = PageParams(page=page, page_size=page_size)
    items, total = await service.list_products(
        db,
        params,
        category_id=category_id,
        brand_id=brand_id,
        q=q,
        include_inactive=True,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
        in_stock_only=in_stock_only,
        sort=sort,
    )
    return Page[ProductOut](
        items=[ProductOut.model_validate(p) for p in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@admin_router.get("/admin/products/{product_id}", response_model=ProductOut)
async def admin_get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> ProductOut:
    product = await service.get_product_or_404(db, product_id)
    return ProductOut.model_validate(product)
