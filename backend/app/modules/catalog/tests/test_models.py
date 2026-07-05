"""Model-level tests for catalog.models — run against an in-memory sqlite
engine, independent of the FastAPI app fixture (see backend/tests/conftest.py
for the API-level equivalent pattern)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.catalog.models import Brand, Category, Product, ProductImage
from app.shared.base_model import Base


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


async def _make_category(session, name="Widgets", slug="widgets"):
    category = Category(name=name, slug=slug)
    session.add(category)
    await session.commit()
    return category


async def test_category_parent_child_relationship(session):
    parent = await _make_category(session, "Electronics", "electronics")
    child = Category(name="Phones", slug="phones", parent_id=parent.id)
    session.add(child)
    await session.commit()

    assert child.parent_id == parent.id
    await session.refresh(parent, attribute_names=["children"])
    assert [c.slug for c in parent.children] == ["phones"]


async def test_category_duplicate_slug_raises_integrity_error(session):
    await _make_category(session, "A", "dup-slug")
    session.add(Category(name="B", slug="dup-slug"))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_brand_duplicate_slug_raises_integrity_error(session):
    session.add(Brand(name="Acme", slug="acme"))
    await session.commit()

    session.add(Brand(name="Acme Two", slug="acme"))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_product_defaults_and_images_relationship(session):
    category = await _make_category(session)
    brand = Brand(name="Acme", slug="acme")
    session.add(brand)
    await session.commit()

    product = Product(
        name="Widget",
        slug="widget",
        brand_id=brand.id,
        category_id=category.id,
        price_cents=1999,
        currency="USD",
        sku="SKU-1",
    )
    session.add(product)
    await session.commit()

    # defaults per docs/CONTRACTS.md
    assert product.stock_quantity == 0
    assert product.is_active is True

    image = ProductImage(product_id=product.id, url="https://example.com/1.png", sort_order=0)
    session.add(image)
    await session.commit()

    await session.refresh(product, attribute_names=["images"])
    assert len(product.images) == 1
    assert product.images[0].url == "https://example.com/1.png"


async def test_product_without_brand_is_allowed(session):
    category = await _make_category(session)
    product = Product(
        name="No Brand Widget",
        slug="no-brand-widget",
        category_id=category.id,
        price_cents=500,
        currency="USD",
        sku="SKU-NO-BRAND",
    )
    session.add(product)
    await session.commit()

    assert product.brand_id is None


async def test_product_duplicate_slug_raises_integrity_error(session):
    category = await _make_category(session)
    session.add(
        Product(
            name="P1", slug="dup-product", category_id=category.id,
            price_cents=100, currency="USD", sku="SKU-A",
        )
    )
    await session.commit()

    session.add(
        Product(
            name="P2", slug="dup-product", category_id=category.id,
            price_cents=200, currency="USD", sku="SKU-B",
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_product_duplicate_sku_raises_integrity_error(session):
    category = await _make_category(session)
    session.add(
        Product(
            name="P1", slug="p1", category_id=category.id,
            price_cents=100, currency="USD", sku="SKU-DUP",
        )
    )
    await session.commit()

    session.add(
        Product(
            name="P2", slug="p2", category_id=category.id,
            price_cents=200, currency="USD", sku="SKU-DUP",
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()
