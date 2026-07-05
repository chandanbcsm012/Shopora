"""Tests for the orders module: cart management, checkout, and order
history, per docs/CONTRACTS.md.

Cross-module dependency handling
---------------------------------
`orders.service` calls into two modules being built in parallel by other
teams:

  * `app.modules.catalog.service.get_available_product` (Catalog Team)
  * `app.modules.auth.dependencies.get_current_user` (Identity & Security
    Team)

At the time this file was written, `app.modules.auth.dependencies` *was*
importable (real `get_current_user`), but to keep these tests hermetic and
scoped strictly to the orders module's own logic (not accidentally asserting
on catalog's business rules), we still:

  * Monkeypatch `app.modules.orders.service.get_available_product` in every
    test (service-level *and* router-level) with a small in-memory fake
    that returns duck-typed stand-ins for `ProductOrderView`
    (`id/name/price_cents/currency/stock_quantity`). `orders/service.py`
    wraps its top-level `from app.modules.catalog.service import
    get_available_product` in a try/except so this module stays importable
    even if catalog.service.py doesn't exist yet — the monkeypatch works
    either way, whether the real function or the fallback stub got bound at
    import time.
  * Use real `app.modules.auth.dependencies.get_current_user` for the
    import (it's available), but override it via
    `app.dependency_overrides` for router tests, per the standard FastAPI
    testing pattern already used by the auth/catalog modules' own test
    suites (see app/modules/auth/tests/test_auth.py,
    app/modules/catalog/tests/test_catalog.py) — this avoids needing to
    mint real JWTs and keeps orders' router tests independent of auth's
    token/login implementation details.

Product rows: `app.modules.catalog.models.Product` is a Database-Team-owned
model that already exists (only catalog's service.py/schemas.py were being
built in parallel), so it's fine to insert raw `Product` rows directly for
FK integrity in the service-layer tests, per the task brief.
"""
from __future__ import annotations

import types

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import AppError
from app.modules.auth.models import User  # noqa: F401 (registers users table)
from app.modules.catalog.models import Category, Product  # noqa: F401 (registers tables)
from app.modules.orders import service
from app.modules.orders.models import OrderStatus
from app.shared.base_model import Base
from app.shared.pagination import PageParams

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


async def _make_user(session, email="cart-user@example.com") -> User:
    user = User(email=email, hashed_password="x", full_name="Cart User")
    session.add(user)
    await session.commit()
    return user


def _fake_product(product_id: str, *, name="Widget", price_cents=500, currency="USD", stock=10):
    return types.SimpleNamespace(
        id=product_id, name=name, price_cents=price_cents, currency=currency, stock_quantity=stock
    )


def _stub_catalog(monkeypatch, products: dict[str, object]):
    async def _fake_get_available_product(db, product_id):
        return products.get(product_id)

    monkeypatch.setattr(service, "get_available_product", _fake_get_available_product)
    return products


# ---------------------------------------------------------------------------
# get_or_create_cart
# ---------------------------------------------------------------------------


async def test_get_or_create_cart_creates_empty_cart_then_reuses(session):
    user = await _make_user(session)

    cart1 = await service.get_or_create_cart(session, user.id)
    assert cart1.user_id == user.id
    assert cart1.items == []

    cart2 = await service.get_or_create_cart(session, user.id)
    assert cart2.id == cart1.id


# ---------------------------------------------------------------------------
# add_item_to_cart
# ---------------------------------------------------------------------------


async def test_add_item_to_cart_creates_item_with_snapshotted_price(session, monkeypatch):
    user = await _make_user(session)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", price_cents=999, stock=5)})

    cart = await service.add_item_to_cart(session, user.id, "p1", 2)

    assert len(cart.items) == 1
    item = cart.items[0]
    assert item.product_id == "p1"
    assert item.quantity == 2
    assert item.unit_price_cents == 999


async def test_add_item_to_cart_accumulates_quantity_for_same_product(session, monkeypatch):
    user = await _make_user(session)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", price_cents=100, stock=10)})

    await service.add_item_to_cart(session, user.id, "p1", 2)
    cart = await service.add_item_to_cart(session, user.id, "p1", 3)

    assert len(cart.items) == 1
    assert cart.items[0].quantity == 5


async def test_add_item_to_cart_product_not_found_raises_404(session, monkeypatch):
    user = await _make_user(session)
    _stub_catalog(monkeypatch, {})

    with pytest.raises(AppError) as exc_info:
        await service.add_item_to_cart(session, user.id, "does-not-exist", 1)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code.value == "RESOURCE_NOT_FOUND"


async def test_add_item_to_cart_insufficient_stock_raises_409(session, monkeypatch):
    user = await _make_user(session)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=2)})

    with pytest.raises(AppError) as exc_info:
        await service.add_item_to_cart(session, user.id, "p1", 3)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code.value == "INSUFFICIENT_STOCK"


async def test_add_item_to_cart_insufficient_stock_on_accumulated_quantity(session, monkeypatch):
    user = await _make_user(session)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=4)})

    await service.add_item_to_cart(session, user.id, "p1", 3)
    with pytest.raises(AppError) as exc_info:
        await service.add_item_to_cart(session, user.id, "p1", 2)  # would total 5 > stock 4

    assert exc_info.value.code.value == "INSUFFICIENT_STOCK"
    # first successful add must not have been rolled back
    cart = await service.get_or_create_cart(session, user.id)
    assert cart.items[0].quantity == 3


# ---------------------------------------------------------------------------
# update_cart_item / remove_cart_item
# ---------------------------------------------------------------------------


async def test_update_cart_item_changes_quantity(session, monkeypatch):
    user = await _make_user(session)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=10)})
    cart = await service.add_item_to_cart(session, user.id, "p1", 1)
    item_id = cart.items[0].id

    updated = await service.update_cart_item(session, user.id, item_id, 7)

    assert updated.items[0].quantity == 7


async def test_update_cart_item_not_owned_raises_404(session, monkeypatch):
    owner = await _make_user(session, email="owner@example.com")
    intruder = await _make_user(session, email="intruder@example.com")
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=10)})
    cart = await service.add_item_to_cart(session, owner.id, "p1", 1)
    item_id = cart.items[0].id

    with pytest.raises(AppError) as exc_info:
        await service.update_cart_item(session, intruder.id, item_id, 2)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code.value == "RESOURCE_NOT_FOUND"


async def test_remove_cart_item_removes_it(session, monkeypatch):
    user = await _make_user(session)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=10)})
    cart = await service.add_item_to_cart(session, user.id, "p1", 1)
    item_id = cart.items[0].id

    updated = await service.remove_cart_item(session, user.id, item_id)

    assert updated.items == []


async def test_remove_cart_item_not_found_raises_404(session):
    user = await _make_user(session)

    with pytest.raises(AppError) as exc_info:
        await service.remove_cart_item(session, user.id, "no-such-item")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# checkout
#
# `checkout()` now requires a `CheckoutRequest` (shipping/billing address ids
# + payment method) per the Checkout/Addresses/Payments/Invoices addition to
# docs/CONTRACTS.md. `_make_address` inserts a raw `addresses.models.Address`
# row directly (same rationale the module docstring already gives for
# inserting raw `catalog.models.Product` rows: it's a Database-Team-owned
# model that already exists, so it's fine for FK integrity in these
# service-layer tests). `_checkout_request` builds a COD request by default
# since COD always succeeds deterministically without touching the
# TestCardProvider's succeed/decline branching (that branching gets its own
# dedicated coverage in test_checkout_payments_invoices.py).
# ---------------------------------------------------------------------------

from app.modules.addresses.models import Address  # noqa: E402 (registers addresses table)
from app.modules.orders.schemas import CheckoutRequest  # noqa: E402


async def _make_address(session, user_id: str, **overrides) -> Address:
    address = Address(
        user_id=user_id,
        full_name=overrides.pop("full_name", "Test User"),
        phone=overrides.pop("phone", "+1-555-0100"),
        address_line1=overrides.pop("address_line1", "123 Main St"),
        city=overrides.pop("city", "Springfield"),
        state=overrides.pop("state", "IL"),
        country=overrides.pop("country", "US"),
        postal_code=overrides.pop("postal_code", "62701"),
        **overrides,
    )
    session.add(address)
    await session.commit()
    await session.refresh(address)
    return address


def _checkout_request(shipping_id: str, billing_id: str, method: str = "cod", outcome: str = "succeed") -> CheckoutRequest:
    return CheckoutRequest(
        shipping_address_id=shipping_id,
        billing_address_id=billing_id,
        payment_method=method,
        test_card_outcome=outcome,
    )


async def test_checkout_empty_cart_raises_400(session):
    user = await _make_user(session)

    with pytest.raises(AppError) as exc_info:
        await service.checkout(session, user.id, _checkout_request("no-such-addr", "no-such-addr"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.code.value == "EMPTY_CART"


async def test_checkout_creates_order_and_empties_cart(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    products = _stub_catalog(
        monkeypatch,
        {
            "p1": _fake_product("p1", name="Widget", price_cents=500, stock=10),
            "p2": _fake_product("p2", name="Gadget", price_cents=250, stock=10),
        },
    )
    await service.add_item_to_cart(session, user.id, "p1", 2)  # 1000
    await service.add_item_to_cart(session, user.id, "p2", 3)  # 750

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id))

    # COD always "succeeds" at the order-confirmation level ("paid" here
    # means "order confirmed, payment method accepted", not "cash
    # collected" -- see docs/CONTRACTS.md).
    assert order.status == OrderStatus.PAID
    assert order.total_cents == 1000 + 750
    assert order.currency == "USD"
    assert order.shipping_address_id == address.id
    assert order.billing_address_id == address.id
    assert {oi.product_id for oi in order.items} == {"p1", "p2"}
    widget_item = next(oi for oi in order.items if oi.product_id == "p1")
    assert widget_item.product_name_snapshot == "Widget"
    assert widget_item.quantity == 2
    assert widget_item.unit_price_cents == 500

    # cart is now empty but still exists
    cart = await service.get_or_create_cart(session, user.id)
    assert cart.items == []


async def test_checkout_locks_price_from_cart_snapshot_not_current_catalog_price(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    products = _stub_catalog(monkeypatch, {"p1": _fake_product("p1", price_cents=500, stock=10)})
    await service.add_item_to_cart(session, user.id, "p1", 1)

    # price changes in the catalog after add-to-cart but before checkout
    products["p1"].price_cents = 999

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id))

    assert order.items[0].unit_price_cents == 500
    assert order.total_cents == 500


async def test_checkout_raises_insufficient_stock_when_stock_dropped_since_add(session, monkeypatch):
    user = await _make_user(session)
    products = _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=10)})
    await service.add_item_to_cart(session, user.id, "p1", 5)

    # someone else bought stock between add-to-cart and checkout
    products["p1"].stock_quantity = 2

    with pytest.raises(AppError) as exc_info:
        await service.checkout(session, user.id, _checkout_request("no-such-addr", "no-such-addr"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code.value == "INSUFFICIENT_STOCK"

    # cart must be left intact when checkout fails
    cart = await service.get_or_create_cart(session, user.id)
    assert len(cart.items) == 1


async def test_checkout_raises_product_inactive_when_product_unavailable(session, monkeypatch):
    user = await _make_user(session)
    products = _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=10)})
    await service.add_item_to_cart(session, user.id, "p1", 1)

    # product was deactivated/deleted before checkout
    del products["p1"]

    with pytest.raises(AppError) as exc_info:
        await service.checkout(session, user.id, _checkout_request("no-such-addr", "no-such-addr"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code.value == "PRODUCT_INACTIVE"


async def test_checkout_unknown_shipping_address_raises_404(session, monkeypatch):
    user = await _make_user(session)
    billing = await _make_address(session, user.id)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=10)})
    await service.add_item_to_cart(session, user.id, "p1", 1)

    with pytest.raises(AppError) as exc_info:
        await service.checkout(session, user.id, _checkout_request("does-not-exist", billing.id))

    assert exc_info.value.status_code == 404
    assert exc_info.value.code.value == "RESOURCE_NOT_FOUND"


async def test_checkout_address_owned_by_another_user_raises_404(session, monkeypatch):
    user = await _make_user(session, email="buyer@example.com")
    other_user = await _make_user(session, email="other@example.com")
    other_address = await _make_address(session, other_user.id)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=10)})
    await service.add_item_to_cart(session, user.id, "p1", 1)

    with pytest.raises(AppError) as exc_info:
        await service.checkout(session, user.id, _checkout_request(other_address.id, other_address.id))

    assert exc_info.value.status_code == 404
    assert exc_info.value.code.value == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# list_orders / get_order
# ---------------------------------------------------------------------------


async def test_list_orders_pagination(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=100)})

    for _ in range(3):
        await service.add_item_to_cart(session, user.id, "p1", 1)
        await service.checkout(session, user.id, _checkout_request(address.id, address.id))

    page1 = await service.list_orders(session, user.id, PageParams(page=1, page_size=2))
    assert page1.total == 3
    assert len(page1.items) == 2
    assert page1.page == 1
    assert page1.page_size == 2

    page2 = await service.list_orders(session, user.id, PageParams(page=2, page_size=2))
    assert len(page2.items) == 1


async def test_list_orders_only_returns_own_orders(session, monkeypatch):
    user_a = await _make_user(session, email="a@example.com")
    user_b = await _make_user(session, email="b@example.com")
    address_a = await _make_address(session, user_a.id)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=100)})

    await service.add_item_to_cart(session, user_a.id, "p1", 1)
    await service.checkout(session, user_a.id, _checkout_request(address_a.id, address_a.id))

    page = await service.list_orders(session, user_b.id, PageParams())
    assert page.total == 0
    assert page.items == []


async def test_get_order_not_owned_raises_404(session, monkeypatch):
    owner = await _make_user(session, email="owner2@example.com")
    intruder = await _make_user(session, email="intruder2@example.com")
    address = await _make_address(session, owner.id)
    _stub_catalog(monkeypatch, {"p1": _fake_product("p1", stock=100)})

    await service.add_item_to_cart(session, owner.id, "p1", 1)
    order = await service.checkout(session, owner.id, _checkout_request(address.id, address.id))

    with pytest.raises(AppError) as exc_info:
        await service.get_order(session, intruder.id, order.id)
    assert exc_info.value.status_code == 404

    found = await service.get_order(session, owner.id, order.id)
    assert found.id == order.id


# ---------------------------------------------------------------------------
# Router-level tests: real FastAPI app + HTTP client (shared fixtures from
# backend/tests/conftest.py, re-exported at backend/conftest.py). Auth is
# handled via `app.dependency_overrides[get_current_user]` (real import —
# the Identity & Security team's dependencies.py was available when these
# tests were written) rather than minting real JWTs, mirroring the pattern
# already used in app/modules/auth/tests/test_auth.py and
# app/modules/catalog/tests/test_catalog.py. Catalog stock/pricing is still
# stubbed via monkeypatch (see module docstring) so these tests only
# exercise orders' own router/service logic.
# ---------------------------------------------------------------------------

from app.main import app  # noqa: E402
from app.modules.auth.dependencies import get_current_user  # noqa: E402
from app.modules.orders.router import router as orders_router  # noqa: E402
from tests.conftest import client, db_session  # noqa: E402,F401

if not any(getattr(r, "path", None) == "/api/v1/cart" for r in app.routes):
    app.include_router(orders_router, prefix="/api/v1")


class _FakeUser:
    def __init__(self, id: str, email: str = "router-test-user@example.com", role: str = "customer"):
        self.id = id
        self.email = email
        self.full_name = "Router Test User"
        self.role = role


@pytest.fixture
def current_user_id():
    return "router-test-user"


@pytest.fixture(autouse=True)
def _auth_override(current_user_id):
    async def _fake_current_user():
        return _FakeUser(current_user_id)

    app.dependency_overrides[get_current_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _catalog_stub(monkeypatch):
    products = {
        "p1": _fake_product("p1", name="Widget", price_cents=500, stock=10),
        "p2": _fake_product("p2", name="Gadget", price_cents=250, stock=10),
    }
    _stub_catalog(monkeypatch, products)
    return products


@pytest.fixture(autouse=True)
def _email_spy(monkeypatch):
    """Never hit real SMTP in router tests -- same rationale as the
    invitation/password-reset router tests monkeypatching `send_email`."""
    calls = []
    monkeypatch.setattr(
        "app.modules.orders.router.send_email",
        lambda to, subject, html_body: calls.append((to, subject, html_body)),
    )
    return calls


@pytest.fixture
async def router_address(db_session, current_user_id):
    """A real, owned Address row for the router-level fake current user, so
    `POST /orders/checkout` (which now requires shipping/billing address
    ids) has something valid to reference."""
    address = await _make_address(db_session, current_user_id)
    return address


def _checkout_body(address_id: str, method: str = "cod", outcome: str = "succeed") -> dict:
    return {
        "shipping_address_id": address_id,
        "billing_address_id": address_id,
        "payment_method": method,
        "test_card_outcome": outcome,
    }


async def test_router_get_cart_auto_creates_empty_cart(client, db_session):
    resp = await client.get("/api/v1/cart")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["subtotal_cents"] == 0


async def test_router_add_update_remove_cart_item(client, db_session):
    add_resp = await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 2})
    assert add_resp.status_code == 200, add_resp.text
    body = add_resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["quantity"] == 2
    assert item["unit_price_cents"] == 500
    assert item["line_total_cents"] == 1000
    assert body["subtotal_cents"] == 1000

    item_id = item["id"]
    patch_resp = await client.patch(f"/api/v1/cart/items/{item_id}", json={"quantity": 5})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["items"][0]["quantity"] == 5

    delete_resp = await client.delete(f"/api/v1/cart/items/{item_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["items"] == []


async def test_router_add_item_insufficient_stock_returns_409(client, db_session):
    resp = await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 999})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"


async def test_router_add_item_unknown_product_returns_404(client, db_session):
    resp = await client.post("/api/v1/cart/items", json={"product_id": "does-not-exist", "quantity": 1})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_router_checkout_returns_201_and_empties_cart(client, db_session, router_address):
    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 2})
    await client.post("/api/v1/cart/items", json={"product_id": "p2", "quantity": 1})

    checkout_resp = await client.post(
        "/api/v1/orders/checkout", json=_checkout_body(router_address.id)
    )
    assert checkout_resp.status_code == 201, checkout_resp.text
    order = checkout_resp.json()
    # COD immediately confirms the order ("paid" = "order confirmed, method
    # accepted", not "cash already collected" -- see docs/CONTRACTS.md).
    assert order["status"] == "paid"
    assert order["payment_status"] == "pending"
    assert order["invoice_number"] is not None
    assert order["total_cents"] == 2 * 500 + 1 * 250
    assert len(order["items"]) == 2
    assert order["shipping_address"]["id"] == router_address.id

    cart_resp = await client.get("/api/v1/cart")
    assert cart_resp.json()["items"] == []


async def test_router_checkout_empty_cart_returns_400(client, db_session, router_address):
    resp = await client.post("/api/v1/orders/checkout", json=_checkout_body(router_address.id))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "EMPTY_CART"


async def test_router_checkout_unknown_address_returns_404(client, db_session):
    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 1})

    resp = await client.post("/api/v1/orders/checkout", json=_checkout_body("does-not-exist"))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_router_list_and_get_order(client, db_session, router_address):
    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 1})
    checkout_resp = await client.post(
        "/api/v1/orders/checkout", json=_checkout_body(router_address.id)
    )
    order_id = checkout_resp.json()["id"]

    list_resp = await client.get("/api/v1/orders")
    assert list_resp.status_code == 200
    page = list_resp.json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == order_id

    get_resp = await client.get(f"/api/v1/orders/{order_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == order_id


async def test_router_get_order_not_found_returns_404(client, db_session):
    resp = await client.get("/api/v1/orders/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_router_requires_authentication(client, db_session):
    # Remove the auth override installed by the autouse fixture to exercise
    # the real `get_current_user` dependency (no token supplied).
    app.dependency_overrides.pop(get_current_user, None)

    resp = await client.get("/api/v1/cart")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
