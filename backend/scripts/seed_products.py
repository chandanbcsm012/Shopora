"""Seed the catalog with real sample product data from DummyJSON
(https://dummyjson.com/products), a free, no-auth-required, open product
API meant for exactly this kind of dev/demo seeding.

Goes through the catalog service layer (create_category/create_brand/
create_product) rather than raw model inserts, so the same uniqueness
rules and defaults the API itself enforces apply here too. Idempotent:
re-running skips categories/brands/products that already exist by slug.

Also backfills each category's `image_url` (added for the storefront's
homepage category showcase) using its first product's first photo, since
DummyJSON doesn't provide dedicated category images -- reusing real
product photography instead of fabricating placeholder image URLs.

Usage (from backend/, with the venv active):
    python -m scripts.seed_products
    python -m scripts.seed_products --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import SessionLocal
from app.modules.catalog import service
from app.modules.catalog.models import Brand, Category, Product
from app.modules.catalog.schemas import (
    BrandCreate,
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductImageCreate,
)

DUMMYJSON_URL = "https://dummyjson.com/products"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "item"


async def fetch_products(limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(DUMMYJSON_URL, params={"limit": limit})
        resp.raise_for_status()
        return resp.json()["products"]


async def get_or_create_category(db, cache: dict[str, Category], name: str) -> Category:
    slug = slugify(name)
    if slug in cache:
        return cache[slug]

    existing = (await db.execute(select(Category).where(Category.slug == slug))).scalar_one_or_none()
    if existing is not None:
        cache[slug] = existing
        return existing

    category = await service.create_category(db, CategoryCreate(name=name.title(), slug=slug))
    cache[slug] = category
    print(f"  + category: {category.name}")
    return category


async def get_or_create_brand(db, cache: dict[str, Brand], name: str) -> Brand:
    slug = slugify(name)
    if slug in cache:
        return cache[slug]

    existing = (await db.execute(select(Brand).where(Brand.slug == slug))).scalar_one_or_none()
    if existing is not None:
        cache[slug] = existing
        return existing

    brand = await service.create_brand(db, BrandCreate(name=name, slug=slug))
    cache[slug] = brand
    print(f"  + brand: {brand.name}")
    return brand


async def backfill_category_images(db) -> int:
    """Set `image_url` on any category that doesn't have one yet, using its
    first product's first image as a representative thumbnail. Avoids
    fabricating placeholder image URLs or requiring a manual upload per
    category -- reuses real product photography already in the catalog.
    Idempotent: only touches categories where `image_url IS NULL`.
    """
    categories = (
        await db.execute(select(Category).where(Category.image_url.is_(None)))
    ).scalars().all()

    updated = 0
    for category in categories:
        product = (
            await db.execute(
                select(Product)
                .where(Product.category_id == category.id, Product.is_active.is_(True))
                .options(selectinload(Product.images))
                .order_by(Product.created_at)
                .limit(1)
            )
        ).scalars().first()
        if product is None or not product.images:
            continue

        first_image = min(product.images, key=lambda img: img.sort_order)
        await service.update_category(db, category.id, CategoryUpdate(image_url=first_image.url))
        updated += 1
        print(f"  + category image: {category.name} -> {first_image.url}")

    return updated


async def seed(limit: int) -> None:
    print(f"Fetching up to {limit} products from {DUMMYJSON_URL} ...")
    raw_products = await fetch_products(limit)
    print(f"Fetched {len(raw_products)} products.")

    category_cache: dict[str, Category] = {}
    brand_cache: dict[str, Brand] = {}
    created, skipped = 0, 0

    async with SessionLocal() as db:
        for item in raw_products:
            slug = f"{slugify(item['title'])}-{item['id']}"

            existing = (await db.execute(select(Product).where(Product.slug == slug))).scalar_one_or_none()
            if existing is not None:
                skipped += 1
                continue

            category = await get_or_create_category(db, category_cache, item["category"])
            brand = None
            if item.get("brand"):
                brand = await get_or_create_brand(db, brand_cache, item["brand"])

            sku = item.get("sku") or f"DJ-{item['id']}"
            existing_sku = (await db.execute(select(Product).where(Product.sku == sku))).scalar_one_or_none()
            if existing_sku is not None:
                sku = f"{sku}-{item['id']}"

            images = [
                ProductImageCreate(url=url, alt_text=item["title"], sort_order=i)
                for i, url in enumerate(item.get("images") or [item["thumbnail"]])
            ]

            await service.create_product(
                db,
                ProductCreate(
                    name=item["title"],
                    slug=slug,
                    description=item.get("description"),
                    brand_id=brand.id if brand else None,
                    category_id=category.id,
                    price_cents=round(float(item["price"]) * 100),
                    currency="USD",
                    sku=sku,
                    stock_quantity=int(item.get("stock", 0)),
                    is_active=True,
                    images=images,
                ),
            )
            created += 1
            print(f"  + product: {item['title']} (${item['price']}, stock={item.get('stock', 0)})")

        print("\nBackfilling category images from existing product photos...")
        images_set = await backfill_category_images(db)

    print(
        f"\nDone. Created {created} products, skipped {skipped} already-seeded products. "
        f"Set images on {images_set} categories."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="Max products to fetch (default: 100, max ~194)")
    args = parser.parse_args()

    try:
        asyncio.run(seed(args.limit))
    except httpx.HTTPError as exc:
        print(f"Failed to fetch from DummyJSON: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
