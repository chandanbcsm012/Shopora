"""Business logic for the catalog module: CRUD for categories/brands/
products, uniqueness enforcement, filtered+paginated product listing, and
the cross-module read used by `orders` (see get_available_product)."""
from __future__ import annotations

from typing import Literal

from fastapi import status
from sqlalchemy import column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.shared.error_codes import ErrorCode
from app.shared.pagination import PageParams

from .models import Brand, Category, Product, ProductImage
from .schemas import (
    BrandCreate,
    BrandUpdate,
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductOrderView,
    ProductUpdate,
)

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


async def list_categories(db: AsyncSession) -> list[Category]:
    result = await db.execute(select(Category).order_by(Category.name))
    return list(result.scalars().all())


async def create_category(db: AsyncSession, data: CategoryCreate) -> Category:
    await _ensure_unique_slug(db, Category, data.slug)

    category = Category(
        name=data.name, slug=data.slug, parent_id=data.parent_id, image_url=data.image_url
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def get_category_or_404(db: AsyncSession, category_id: str) -> Category:
    category = await db.get(Category, category_id)
    if category is None:
        raise AppError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Category not found",
            status.HTTP_404_NOT_FOUND,
            {"category_id": category_id},
        )
    return category


async def update_category(db: AsyncSession, category_id: str, data: CategoryUpdate) -> Category:
    category = await get_category_or_404(db, category_id)

    updates = data.model_dump(exclude_unset=True)

    if "slug" in updates and updates["slug"] != category.slug:
        await _ensure_unique_slug(db, Category, updates["slug"], exclude_id=category.id)

    for field, value in updates.items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category_id: str) -> None:
    category = await get_category_or_404(db, category_id)

    has_products = (
        await db.execute(select(Product.id).where(Product.category_id == category_id).limit(1))
    ).scalar_one_or_none()
    if has_products is not None:
        raise AppError(
            ErrorCode.CATEGORY_IN_USE,
            "Category cannot be deleted because it has products assigned to it.",
            status.HTTP_409_CONFLICT,
            {"category_id": category_id},
        )

    has_children = (
        await db.execute(select(Category.id).where(Category.parent_id == category_id).limit(1))
    ).scalar_one_or_none()
    if has_children is not None:
        raise AppError(
            ErrorCode.CATEGORY_IN_USE,
            "Category cannot be deleted because it has child categories.",
            status.HTTP_409_CONFLICT,
            {"category_id": category_id},
        )

    await db.delete(category)
    await db.commit()


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------


async def list_brands(db: AsyncSession) -> list[Brand]:
    result = await db.execute(select(Brand).order_by(Brand.name))
    return list(result.scalars().all())


async def create_brand(db: AsyncSession, data: BrandCreate) -> Brand:
    await _ensure_unique_slug(db, Brand, data.slug)

    brand = Brand(name=data.name, slug=data.slug)
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand


async def get_brand_or_404(db: AsyncSession, brand_id: str) -> Brand:
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise AppError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Brand not found",
            status.HTTP_404_NOT_FOUND,
            {"brand_id": brand_id},
        )
    return brand


async def update_brand(db: AsyncSession, brand_id: str, data: BrandUpdate) -> Brand:
    brand = await get_brand_or_404(db, brand_id)

    updates = data.model_dump(exclude_unset=True)

    if "slug" in updates and updates["slug"] != brand.slug:
        await _ensure_unique_slug(db, Brand, updates["slug"], exclude_id=brand.id)

    for field, value in updates.items():
        setattr(brand, field, value)

    await db.commit()
    await db.refresh(brand)
    return brand


async def delete_brand(db: AsyncSession, brand_id: str) -> None:
    brand = await get_brand_or_404(db, brand_id)

    has_products = (
        await db.execute(select(Product.id).where(Product.brand_id == brand_id).limit(1))
    ).scalar_one_or_none()
    if has_products is not None:
        raise AppError(
            ErrorCode.BRAND_IN_USE,
            "Brand cannot be deleted because it has products assigned to it.",
            status.HTTP_409_CONFLICT,
            {"brand_id": brand_id},
        )

    await db.delete(brand)
    await db.commit()


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


def _product_query():
    return select(Product).options(selectinload(Product.images))


async def get_product(db: AsyncSession, product_id: str) -> Product | None:
    result = await db.execute(_product_query().where(Product.id == product_id))
    return result.scalars().first()


async def get_product_or_404(db: AsyncSession, product_id: str) -> Product:
    """Unfiltered lookup — used for admin mutations (update/delete/admin
    detail view), which must be able to find an inactive product to manage
    it. Public-facing reads must use `get_active_product_or_404` instead so
    a discontinued/hidden product's detail page isn't still reachable by
    anyone who has (or guesses) its id."""
    product = await get_product(db, product_id)
    if product is None:
        raise AppError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Product not found",
            status.HTTP_404_NOT_FOUND,
            {"product_id": product_id},
        )
    return product


async def get_active_product_or_404(db: AsyncSession, product_id: str) -> Product:
    """Public storefront lookup: an inactive product 404s exactly like a
    missing one, rather than remaining viewable/purchasable via a direct
    link once it's been hidden from listings."""
    product = await get_product_or_404(db, product_id)
    if not product.is_active:
        raise AppError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Product not found",
            status.HTTP_404_NOT_FOUND,
            {"product_id": product_id},
        )
    return product


ProductSort = Literal["newest", "price_asc", "price_desc", "name_asc", "name_desc"]

# Maps each supported `sort` value to its `.order_by(...)` clause. "newest"
# is byte-identical to the previously-hardcoded default so existing callers
# that don't pass `sort` see zero behavior change.
_SORT_CLAUSES = {
    "newest": Product.created_at.desc(),
    "price_asc": Product.price_cents.asc(),
    "price_desc": Product.price_cents.desc(),
    "name_asc": Product.name.asc(),
    "name_desc": Product.name.desc(),
}


async def list_products(
    db: AsyncSession,
    params: PageParams,
    category_id: str | None = None,
    brand_id: str | None = None,
    q: str | None = None,
    include_inactive: bool = False,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
    in_stock_only: bool = False,
    sort: ProductSort = "newest",
) -> tuple[list[Product], int]:
    """`include_inactive` must only ever be set `True` by the admin-only
    listing route — the public storefront listing always leaves it `False`
    so discontinued/hidden products don't appear in browsing/search.

    `min_price_cents`/`max_price_cents`/`in_stock_only` filter both `query`
    and `count_query` (they affect the total count); `sort` only affects
    `query`'s ordering, never the count."""
    query = _product_query()
    count_query = select(func.count()).select_from(Product)

    if not include_inactive:
        query = query.where(Product.is_active.is_(True))
        count_query = count_query.where(Product.is_active.is_(True))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
        count_query = count_query.where(Product.category_id == category_id)
    if brand_id is not None:
        query = query.where(Product.brand_id == brand_id)
        count_query = count_query.where(Product.brand_id == brand_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(func.lower(Product.name).like(pattern))
        count_query = count_query.where(func.lower(Product.name).like(pattern))
    if min_price_cents is not None:
        query = query.where(Product.price_cents >= min_price_cents)
        count_query = count_query.where(Product.price_cents >= min_price_cents)
    if max_price_cents is not None:
        query = query.where(Product.price_cents <= max_price_cents)
        count_query = count_query.where(Product.price_cents <= max_price_cents)
    if in_stock_only:
        query = query.where(Product.stock_quantity > 0)
        count_query = count_query.where(Product.stock_quantity > 0)

    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(_SORT_CLAUSES[sort]).offset(params.offset).limit(params.page_size)
    items = list((await db.execute(query)).scalars().unique().all())

    return items, total


async def create_product(db: AsyncSession, data: ProductCreate) -> Product:
    await _ensure_unique_slug(db, Product, data.slug)
    await _ensure_unique_sku(db, data.sku)

    product = Product(
        name=data.name,
        slug=data.slug,
        description=data.description,
        brand_id=data.brand_id,
        category_id=data.category_id,
        price_cents=data.price_cents,
        currency=data.currency,
        sku=data.sku,
        stock_quantity=data.stock_quantity,
        is_active=data.is_active,
    )
    product.images = [
        ProductImage(url=img.url, alt_text=img.alt_text, sort_order=img.sort_order)
        for img in data.images
    ]
    db.add(product)
    await db.commit()
    return await get_product_or_404(db, product.id)


async def update_product(db: AsyncSession, product_id: str, data: ProductUpdate) -> Product:
    product = await get_product_or_404(db, product_id)

    updates = data.model_dump(exclude_unset=True, exclude={"images"})

    if "slug" in updates and updates["slug"] != product.slug:
        await _ensure_unique_slug(db, Product, updates["slug"], exclude_id=product.id)
    if "sku" in updates and updates["sku"] != product.sku:
        await _ensure_unique_sku(db, updates["sku"], exclude_id=product.id)

    for field, value in updates.items():
        setattr(product, field, value)

    if data.images is not None:
        product.images = [
            ProductImage(url=img.url, alt_text=img.alt_text, sort_order=img.sort_order)
            for img in data.images
        ]

    await db.commit()
    return await get_product_or_404(db, product.id)


# Raw core Tables (not ORM model imports) used solely to check whether a
# product is referenced by the `orders` module before deleting it — catalog
# may not import `orders`' SQLAlchemy models (orders already imports catalog,
# so the reverse import would be circular), per docs/ARCHITECTURE.md's rule
# that a module may only reach another module's *tables* via raw FK columns
# / ad hoc reads by table name, never its SQLAlchemy model class. Mirrors the
# identical technique `orders.service._products_table` already uses in
# reverse (reading `products.sku` without importing catalog's `Product`).
_order_items_table = table("order_items", column("id"), column("product_id"))
_cart_items_table = table("cart_items", column("id"), column("product_id"))


async def delete_product(db: AsyncSession, product_id: str) -> None:
    product = await get_product_or_404(db, product_id)

    in_order = (
        await db.execute(
            select(_order_items_table.c.id).where(_order_items_table.c.product_id == product_id).limit(1)
        )
    ).scalar_one_or_none()
    if in_order is not None:
        raise AppError(
            ErrorCode.PRODUCT_IN_USE,
            "Product cannot be deleted because it has been ordered. Mark it inactive instead.",
            status.HTTP_409_CONFLICT,
            {"product_id": product_id},
        )

    in_cart = (
        await db.execute(
            select(_cart_items_table.c.id).where(_cart_items_table.c.product_id == product_id).limit(1)
        )
    ).scalar_one_or_none()
    if in_cart is not None:
        raise AppError(
            ErrorCode.PRODUCT_IN_USE,
            "Product cannot be deleted because it is in a customer's cart. Mark it inactive instead.",
            status.HTTP_409_CONFLICT,
            {"product_id": product_id},
        )

    await db.delete(product)
    await db.commit()


# ---------------------------------------------------------------------------
# Cross-module contract consumed by `orders`.
#
#     async def get_available_product(db: AsyncSession, product_id: str)
#         -> ProductOrderView | None
#
# Returns None if the product does not exist OR is_active is False.
# Otherwise returns the current price_cents/currency/stock_quantity as a
# ProductOrderView. Orders must treat None as "not purchasable".
# ---------------------------------------------------------------------------


async def get_available_product(db: AsyncSession, product_id: str) -> ProductOrderView | None:
    product = await db.get(Product, product_id)
    if product is None or not product.is_active:
        return None
    return ProductOrderView.model_validate(product)


# ---------------------------------------------------------------------------
# Uniqueness helpers
# ---------------------------------------------------------------------------


async def _ensure_unique_slug(db: AsyncSession, model, slug: str, exclude_id: str | None = None) -> None:
    query = select(model.id).where(model.slug == slug)
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    existing = (await db.execute(query)).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            ErrorCode.DUPLICATE_SLUG,
            f"{model.__name__} slug '{slug}' already exists",
            status.HTTP_409_CONFLICT,
            {"slug": slug},
        )


async def _ensure_unique_sku(db: AsyncSession, sku: str, exclude_id: str | None = None) -> None:
    query = select(Product.id).where(Product.sku == sku)
    if exclude_id is not None:
        query = query.where(Product.id != exclude_id)
    existing = (await db.execute(query)).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            ErrorCode.DUPLICATE_SKU,
            f"Product sku '{sku}' already exists",
            status.HTTP_409_CONFLICT,
            {"sku": sku},
        )
