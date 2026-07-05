"""Tests for the wishlist module: add/list/remove, idempotent add/remove,
404 on a nonexistent product, and "a user only ever sees their own
wishlist", per docs/CONTRACTS.md.

Follows the same temporary-mount pattern as other modules' router tests
(e.g. app/modules/addresses/tests/test_addresses.py): `router` isn't wired
into app/main.py yet (that's the Main Coordinator's job), so it's mounted
here, guarded against double registration.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import AppError
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User  # noqa: F401 (registers users table)
from app.modules.catalog.models import Brand, Category, Product  # noqa: F401 (registers products table)
from app.modules.wishlist import service
from app.modules.wishlist.models import WishlistItem  # noqa: F401 (registers wishlist_items table)
from app.modules.wishlist.router import router as wishlist_router
from app.shared.base_model import Base

pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", None) == "/api/v1/wishlist" for r in app.routes):
    app.include_router(wishlist_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Service-layer fixtures/helpers (no FastAPI app involved)
# ---------------------------------------------------------------------------


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


async def _make_user(session, email="wishlist-user@example.com") -> User:
    user = User(email=email, hashed_password="x", full_name="Wishlist User")
    session.add(user)
    await session.commit()
    return user


async def _make_category(session, slug="cat") -> Category:
    category = Category(name="Category", slug=slug)
    session.add(category)
    await session.commit()
    return category


async def _make_product(session, category, sku="SKU-1", slug="widget", is_active=True) -> Product:
    product = Product(
        name="Widget",
        slug=slug,
        category_id=category.id,
        price_cents=1999,
        currency="USD",
        sku=sku,
        stock_quantity=10,
        is_active=is_active,
    )
    session.add(product)
    await session.commit()
    return product


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


async def test_add_list_and_remove(session):
    user = await _make_user(session)
    category = await _make_category(session)
    product = await _make_product(session, category)

    item = await service.add_to_wishlist(session, user.id, product.id)
    assert item.product_id == product.id
    assert item.user_id == user.id

    items = await service.list_wishlist(session, user.id)
    assert len(items) == 1
    assert items[0].id == item.id

    await service.remove_from_wishlist(session, user.id, product.id)
    assert await service.list_wishlist(session, user.id) == []


async def test_add_to_wishlist_is_idempotent(session):
    user = await _make_user(session)
    category = await _make_category(session)
    product = await _make_product(session, category)

    first = await service.add_to_wishlist(session, user.id, product.id)
    second = await service.add_to_wishlist(session, user.id, product.id)

    assert first.id == second.id

    items = await service.list_wishlist(session, user.id)
    assert len(items) == 1


async def test_remove_from_wishlist_is_idempotent(session):
    user = await _make_user(session)
    category = await _make_category(session)
    product = await _make_product(session, category)

    await service.add_to_wishlist(session, user.id, product.id)
    await service.remove_from_wishlist(session, user.id, product.id)

    # Removing again must not raise.
    await service.remove_from_wishlist(session, user.id, product.id)
    assert await service.list_wishlist(session, user.id) == []


async def test_remove_nonexistent_item_does_not_error(session):
    user = await _make_user(session)

    # Never wishlisted anything -- removing a random product id is a no-op.
    await service.remove_from_wishlist(session, user.id, "does-not-exist")


async def test_add_to_wishlist_with_nonexistent_product_raises_404(session):
    user = await _make_user(session)

    with pytest.raises(AppError) as exc_info:
        await service.add_to_wishlist(session, user.id, "does-not-exist")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code.value == "RESOURCE_NOT_FOUND"


async def test_add_to_wishlist_allows_inactive_product(session):
    """A customer can wishlist something that later goes inactive and still
    see it listed -- mirrors how cart/orders handle unavailable products."""
    user = await _make_user(session)
    category = await _make_category(session)
    product = await _make_product(session, category, is_active=False)

    item = await service.add_to_wishlist(session, user.id, product.id)
    assert item.product_id == product.id


async def test_user_only_sees_own_wishlist(session):
    user_a = await _make_user(session, email="a@example.com")
    user_b = await _make_user(session, email="b@example.com")
    category = await _make_category(session)
    product = await _make_product(session, category)

    await service.add_to_wishlist(session, user_a.id, product.id)

    assert await service.list_wishlist(session, user_b.id) == []

    # User B "removing" a product they never wishlisted is a no-op, and
    # must not affect user A's actual wishlist item.
    await service.remove_from_wishlist(session, user_b.id, product.id)

    items_a = await service.list_wishlist(session, user_a.id)
    assert len(items_a) == 1
    assert items_a[0].product_id == product.id


# ---------------------------------------------------------------------------
# Router-level tests: real FastAPI app + HTTP client.
# ---------------------------------------------------------------------------


class _FakeUser:
    def __init__(self, id: str):
        self.id = id


@pytest.fixture
def current_user_id():
    return "router-wishlist-user"


@pytest.fixture(autouse=True)
def _auth_override(current_user_id):
    async def _fake_current_user():
        return _FakeUser(current_user_id)

    app.dependency_overrides[get_current_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def _create_category_via_api(client, name="Electronics", slug="electronics"):
    resp = await client.post("/api/v1/categories", json={"name": name, "slug": slug})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_product_via_api(client, category_id, **overrides):
    payload = {
        "name": "Widget",
        "slug": "widget",
        "category_id": category_id,
        "price_cents": 1999,
        "currency": "USD",
        "sku": "SKU-1",
        "stock_quantity": 10,
        "is_active": True,
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/products", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture(autouse=True)
def _catalog_admin_override():
    """Product/category creation via the HTTP API requires catalog's
    require_admin dependency; grant it for the duration of these router
    tests so setup helpers above can create fixture data."""
    from app.modules.catalog.router import require_admin

    async def _override_admin():
        class _Admin:
            id = "admin-under-test"
            role = "admin"

        return _Admin()

    app.dependency_overrides[require_admin] = _override_admin
    yield
    app.dependency_overrides.pop(require_admin, None)


async def test_router_add_list_and_remove(client, db_session):
    category = await _create_category_via_api(client)
    product = await _create_product_via_api(client, category["id"])

    add_resp = await client.post("/api/v1/wishlist", json={"product_id": product["id"]})
    assert add_resp.status_code == 201, add_resp.text
    body = add_resp.json()
    assert body["product_id"] == product["id"]
    assert "created_at" in body
    assert "id" in body

    list_resp = await client.get("/api/v1/wishlist")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    delete_resp = await client.delete(f"/api/v1/wishlist/{product['id']}")
    assert delete_resp.status_code == 204

    list_resp_after = await client.get("/api/v1/wishlist")
    assert list_resp_after.json() == []


async def test_router_add_is_idempotent(client, db_session):
    category = await _create_category_via_api(client)
    product = await _create_product_via_api(client, category["id"])

    first = await client.post("/api/v1/wishlist", json={"product_id": product["id"]})
    second = await client.post("/api/v1/wishlist", json={"product_id": product["id"]})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    list_resp = await client.get("/api/v1/wishlist")
    assert len(list_resp.json()) == 1


async def test_router_remove_is_idempotent(client, db_session):
    category = await _create_category_via_api(client)
    product = await _create_product_via_api(client, category["id"])

    await client.post("/api/v1/wishlist", json={"product_id": product["id"]})

    first_delete = await client.delete(f"/api/v1/wishlist/{product['id']}")
    second_delete = await client.delete(f"/api/v1/wishlist/{product['id']}")
    assert first_delete.status_code == 204
    assert second_delete.status_code == 204


async def test_router_add_nonexistent_product_returns_404(client, db_session):
    resp = await client.post("/api/v1/wishlist", json={"product_id": "does-not-exist"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_router_user_only_sees_own_wishlist(client, db_session):
    category = await _create_category_via_api(client)
    product = await _create_product_via_api(client, category["id"])

    async def _fake_user_a():
        return _FakeUser("user-a")

    app.dependency_overrides[get_current_user] = _fake_user_a
    add_resp = await client.post("/api/v1/wishlist", json={"product_id": product["id"]})
    assert add_resp.status_code == 201

    async def _fake_user_b():
        return _FakeUser("user-b")

    app.dependency_overrides[get_current_user] = _fake_user_b

    list_resp = await client.get("/api/v1/wishlist")
    assert list_resp.json() == []

    # User B removing user A's wishlisted product is a no-op, not an error.
    delete_resp = await client.delete(f"/api/v1/wishlist/{product['id']}")
    assert delete_resp.status_code == 204

    # Switch back to user A -- their wishlist item must be untouched.
    app.dependency_overrides[get_current_user] = _fake_user_a
    list_resp_a = await client.get("/api/v1/wishlist")
    assert len(list_resp_a.json()) == 1
    assert list_resp_a.json()[0]["product_id"] == product["id"]


async def test_router_requires_authentication(client, db_session):
    app.dependency_overrides.pop(get_current_user, None)

    resp = await client.get("/api/v1/wishlist")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
