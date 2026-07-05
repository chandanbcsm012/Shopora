"""Model-level tests for orders.models — run against an in-memory sqlite
engine, independent of the FastAPI app fixture (see backend/tests/conftest.py
for the API-level equivalent pattern).

Cart/CartItem/Order/OrderItem carry FKs into auth.users and
catalog.products, so auth.models and catalog.models are imported here
purely to register those tables on the shared Base.metadata for the test
schema — this is a test-only concern, not a production import of another
module's models (see docs/ARCHITECTURE.md module boundary rule)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.auth.models import User  # noqa: F401 (registers users table)
from app.modules.catalog.models import Category, Product
from app.modules.orders.models import Cart, CartItem, Order, OrderItem, OrderStatus
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


async def _make_user_and_product(session, email="cart-user@example.com", sku="SKU-ORD-1"):
    user = User(email=email, hashed_password="x", full_name="Cart User")
    category = Category(name="Cat", slug=f"cat-{sku}".lower())
    session.add_all([user, category])
    await session.commit()

    product = Product(
        name="P",
        slug=f"p-{sku}".lower(),
        category_id=category.id,
        price_cents=500,
        currency="USD",
        sku=sku,
    )
    session.add(product)
    await session.commit()
    return user, product


async def test_cart_and_cart_item_relationship(session):
    user, product = await _make_user_and_product(session)

    cart = Cart(user_id=user.id)
    session.add(cart)
    await session.commit()

    item = CartItem(cart_id=cart.id, product_id=product.id, quantity=2, unit_price_cents=500)
    session.add(item)
    await session.commit()

    await session.refresh(cart, attribute_names=["items"])
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2


async def test_cart_is_one_per_user(session):
    user, _ = await _make_user_and_product(session)

    session.add(Cart(user_id=user.id))
    await session.commit()

    session.add(Cart(user_id=user.id))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_order_default_status_and_order_items(session):
    user, product = await _make_user_and_product(session)

    order = Order(user_id=user.id, total_cents=1000, currency="USD")
    session.add(order)
    await session.commit()

    # default per docs/CONTRACTS.md status enum
    assert order.status == OrderStatus.PENDING

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        product_name_snapshot=product.name,
        quantity=2,
        unit_price_cents=500,
    )
    session.add(item)
    await session.commit()

    await session.refresh(order, attribute_names=["items"])
    assert len(order.items) == 1
    assert order.items[0].product_name_snapshot == "P"


async def test_order_status_can_be_set_explicitly(session):
    user, _ = await _make_user_and_product(session)

    order = Order(user_id=user.id, total_cents=100, currency="USD", status=OrderStatus.PAID)
    session.add(order)
    await session.commit()
    await session.refresh(order)

    assert order.status == OrderStatus.PAID


async def test_order_item_deleted_when_order_deleted(session):
    user, product = await _make_user_and_product(session)
    order = Order(user_id=user.id, total_cents=500, currency="USD")
    session.add(order)
    await session.commit()

    session.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            quantity=1,
            unit_price_cents=500,
        )
    )
    await session.commit()

    await session.delete(order)
    await session.commit()

    from sqlalchemy import select

    result = await session.execute(select(OrderItem))
    assert result.scalars().all() == []
