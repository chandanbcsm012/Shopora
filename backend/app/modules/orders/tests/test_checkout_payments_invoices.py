"""Tests for the Checkout, Addresses, Payments & Invoices foundation-scope
addition to the orders module, per docs/CONTRACTS.md: checkout's extended
flow (address resolution, payment processing, order-status-history writes,
invoice creation, confirmation email scheduling), invoice download, order
timeline, and the new admin order-management endpoints.

Follows the same conventions as test_orders.py (see its module docstring):
catalog is stubbed via monkeypatching `service.get_available_product`;
`addresses`/`payments` are real sibling modules built alongside this
extension, so their rows are exercised for real (SQLite in-memory for
service-layer tests, the shared `client`/`db_session` fixtures for router
tests). `router`/`admin_router` aren't wired into app/main.py yet (Main
Coordinator's job), so both are mounted here, guarded against double
registration -- the same pattern test_orders.py/test_admin_users.py use.
"""
from __future__ import annotations

import types

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.errors import AppError
from app.main import app
from app.modules.addresses.models import Address
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User  # noqa: F401 (registers users table)
from app.modules.catalog.models import Category, Product  # noqa: F401 (registers tables)
from app.modules.orders import service
from app.modules.orders.models import Invoice, Order, OrderStatus, OrderStatusHistory
from app.modules.orders.router import admin_router
from app.modules.orders.router import router as orders_router
from app.modules.orders.schemas import CheckoutRequest
from app.modules.payments.models import Payment
from app.shared.base_model import Base

pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", None) == "/api/v1/cart" for r in app.routes):
    app.include_router(orders_router, prefix="/api/v1")

if not any(getattr(r, "path", None) == "/api/v1/admin/orders" for r in app.routes):
    app.include_router(admin_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_orders.py's conventions)
# ---------------------------------------------------------------------------


def _fake_product(product_id: str, *, name="Widget", price_cents=500, currency="USD", stock=10):
    return types.SimpleNamespace(
        id=product_id, name=name, price_cents=price_cents, currency=currency, stock_quantity=stock
    )


def _stub_catalog(monkeypatch, products: dict[str, object]):
    async def _fake_get_available_product(db, product_id):
        return products.get(product_id)

    monkeypatch.setattr(service, "get_available_product", _fake_get_available_product)
    return products


def _checkout_request(shipping_id, billing_id, method="cod", outcome="succeed") -> CheckoutRequest:
    return CheckoutRequest(
        shipping_address_id=shipping_id,
        billing_address_id=billing_id,
        payment_method=method,
        test_card_outcome=outcome,
    )


def _checkout_body(address_id, method="cod", outcome="succeed") -> dict:
    return {
        "shipping_address_id": address_id,
        "billing_address_id": address_id,
        "payment_method": method,
        "test_card_outcome": outcome,
    }


# ---------------------------------------------------------------------------
# Service-layer fixtures
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


async def _make_user(session, email="checkout-user@example.com", role="customer") -> User:
    user = User(email=email, hashed_password="x", full_name="Checkout User", role=role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_address(session, user_id: str, *, state="IL", country="US") -> Address:
    address = Address(
        user_id=user_id,
        full_name="Test User",
        phone="+1-555-0100",
        address_line1="123 Main St",
        city="Springfield",
        state=state,
        country=country,
        postal_code="62701",
    )
    session.add(address)
    await session.commit()
    await session.refresh(address)
    return address


async def _setup_cart(
    session, monkeypatch, user, address, *, price_cents=500, stock=10, currency="USD"
) -> None:
    _stub_catalog(
        monkeypatch,
        {"p1": _fake_product("p1", price_cents=price_cents, stock=stock, currency=currency)},
    )
    await service.add_item_to_cart(session, user.id, "p1", 1)


# ---------------------------------------------------------------------------
# Service-layer: checkout outcomes
# ---------------------------------------------------------------------------


async def test_checkout_cod_confirms_order_and_creates_pending_payment_and_invoice(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address, price_cents=1000)

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    assert order.status == OrderStatus.PAID

    payment = (
        await session.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one()
    assert payment.status == "pending"
    assert payment.method == "cod"
    assert payment.amount_cents == order.total_cents

    invoice = (
        await session.execute(select(Invoice).where(Invoice.order_id == order.id))
    ).scalar_one_or_none()
    assert invoice is not None
    assert invoice.sequence_number >= 1


async def test_checkout_test_card_succeed_captures_payment_and_creates_invoice(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address)

    order = await service.checkout(
        session, user.id, _checkout_request(address.id, address.id, "test_card", "succeed")
    )

    assert order.status == OrderStatus.PAID
    payment = (
        await session.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one()
    assert payment.status == "captured"
    assert payment.provider_reference.startswith("TEST-")

    invoice = (
        await session.execute(select(Invoice).where(Invoice.order_id == order.id))
    ).scalar_one_or_none()
    assert invoice is not None


async def test_checkout_test_card_decline_cancels_order_and_raises_payment_failed(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address)

    with pytest.raises(AppError) as exc_info:
        await service.checkout(
            session, user.id, _checkout_request(address.id, address.id, "test_card", "decline")
        )

    assert exc_info.value.status_code == 402
    assert exc_info.value.code.value == "PAYMENT_FAILED"

    # The (cancelled) Order row is real and committed, despite the error.
    order = (await session.execute(select(Order).where(Order.user_id == user.id))).scalar_one()
    assert order.status == OrderStatus.CANCELLED

    payment = (
        await session.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one()
    assert payment.status == "failed"
    assert payment.failure_reason

    # No invoice for a failed payment.
    invoice = (
        await session.execute(select(Invoice).where(Invoice.order_id == order.id))
    ).scalar_one_or_none()
    assert invoice is None


async def test_checkout_full_history_sequence_for_successful_order(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address)

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    history = await service.get_order_timeline(session, order.id, user.id, is_admin=False)
    transitions = [(h.from_status, h.to_status) for h in history]
    assert transitions == [(None, "pending"), ("pending", "paid")]


async def test_checkout_failed_payment_records_history_row(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address)

    with pytest.raises(AppError):
        await service.checkout(
            session, user.id, _checkout_request(address.id, address.id, "test_card", "decline")
        )

    order = (await session.execute(select(Order).where(Order.user_id == user.id))).scalar_one()
    history = await service.get_order_timeline(session, order.id, user.id, is_admin=False)
    transitions = [(h.from_status, h.to_status) for h in history]
    assert transitions == [(None, "pending"), ("pending", "cancelled")]
    assert history[-1].note  # failure reason recorded


# ---------------------------------------------------------------------------
# Service-layer: invoice bytes
# ---------------------------------------------------------------------------


async def test_get_invoice_pdf_bytes_raises_before_payment_succeeds(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address)

    with pytest.raises(AppError):
        await service.checkout(
            session, user.id, _checkout_request(address.id, address.id, "test_card", "decline")
        )
    order = (await session.execute(select(Order).where(Order.user_id == user.id))).scalar_one()

    with pytest.raises(AppError) as exc_info:
        await service.get_invoice_pdf_bytes(session, order.id, user.id, is_admin=False)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code.value == "INVOICE_NOT_AVAILABLE"


async def test_get_invoice_pdf_bytes_returns_real_pdf_after_success(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address)

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    pdf_bytes = await service.get_invoice_pdf_bytes(session, order.id, user.id, is_admin=False)

    assert pdf_bytes.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# Service-layer: admin management
# ---------------------------------------------------------------------------


async def test_admin_update_status_records_history(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address)
    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    updated = await service.admin_update_status(session, order.id, "shipped", "left warehouse")

    assert updated.status == OrderStatus.SHIPPED
    history = await service.get_order_timeline(session, order.id, user.id, is_admin=True)
    assert history[-1].from_status == "paid"
    assert history[-1].to_status == "shipped"
    assert history[-1].note == "left warehouse"


async def test_admin_refund_full_amount(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address, price_cents=1000)
    order = await service.checkout(
        session, user.id, _checkout_request(address.id, address.id, "test_card", "succeed")
    )

    payment = await service.admin_refund(session, order.id, None)

    assert payment.status == "refunded"
    assert payment.refunded_amount_cents == order.total_cents


async def test_admin_refund_partial_amount(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address, price_cents=1000)
    order = await service.checkout(
        session, user.id, _checkout_request(address.id, address.id, "test_card", "succeed")
    )

    payment = await service.admin_refund(session, order.id, 400)

    assert payment.status == "partially_refunded"
    assert payment.refunded_amount_cents == 400


async def test_admin_refund_cod_pending_payment_raises_not_refundable(session, monkeypatch):
    user = await _make_user(session)
    address = await _make_address(session, user.id)
    await _setup_cart(session, monkeypatch, user, address)
    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    with pytest.raises(AppError) as exc_info:
        await service.admin_refund(session, order.id, None)

    assert exc_info.value.code.value == "PAYMENT_NOT_REFUNDABLE"


# ---------------------------------------------------------------------------
# Router-level tests
# ---------------------------------------------------------------------------


class _FakeUser:
    def __init__(self, id: str, email: str, role: str = "customer"):
        self.id = id
        self.email = email
        self.full_name = "Router Test User"
        self.role = role


def _override_user(user: _FakeUser) -> None:
    async def _fake_current_user():
        return user

    app.dependency_overrides[get_current_user] = _fake_current_user


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _email_spy(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.modules.orders.router.send_email",
        lambda to, subject, html_body: calls.append((to, subject, html_body)),
    )
    return calls


@pytest.fixture(autouse=True)
def _catalog_stub_router(monkeypatch):
    products = {"p1": _fake_product("p1", name="Widget", price_cents=500, stock=10)}
    _stub_catalog(monkeypatch, products)
    return products


async def test_router_checkout_cod_schedules_confirmation_email(client, db_session, _email_spy):
    user = _FakeUser("cust-cod", "cust-cod@example.com")
    _override_user(user)
    address = await _make_address(db_session, user.id)

    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 2})
    resp = await client.post("/api/v1/orders/checkout", json=_checkout_body(address.id, "cod"))

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "paid"
    assert body["payment_status"] == "pending"
    assert body["invoice_number"]

    assert len(_email_spy) == 1
    to, subject, html_body = _email_spy[0]
    assert to == user.email
    assert body["id"] in html_body


async def test_router_checkout_test_card_decline_returns_402_but_order_exists(client, db_session):
    user = _FakeUser("cust-decline", "cust-decline@example.com")
    _override_user(user)
    address = await _make_address(db_session, user.id)

    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 1})
    resp = await client.post(
        "/api/v1/orders/checkout", json=_checkout_body(address.id, "test_card", "decline")
    )

    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "PAYMENT_FAILED"

    order_row = (
        await db_session.execute(select(Order).where(Order.user_id == user.id))
    ).scalar_one()
    assert order_row.status == OrderStatus.CANCELLED

    history_rows = (
        await db_session.execute(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == order_row.id)
        )
    ).scalars().all()
    assert any(h.to_status == "cancelled" for h in history_rows)


async def test_router_checkout_foreign_address_returns_404(client, db_session):
    owner = _FakeUser("owner-x", "owner-x@example.com")
    intruder = _FakeUser("intruder-x", "intruder-x@example.com")

    _override_user(owner)
    owned_address = await _make_address(db_session, owner.id)

    _override_user(intruder)
    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 1})
    resp = await client.post(
        "/api/v1/orders/checkout", json=_checkout_body(owned_address.id, "cod")
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_router_invoice_download_before_and_after_payment(client, db_session):
    user = _FakeUser("cust-invoice", "cust-invoice@example.com")
    _override_user(user)
    address = await _make_address(db_session, user.id)

    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 1})
    decline_resp = await client.post(
        "/api/v1/orders/checkout", json=_checkout_body(address.id, "test_card", "decline")
    )
    assert decline_resp.status_code == 402
    order_row = (
        await db_session.execute(select(Order).where(Order.user_id == user.id))
    ).scalar_one()

    invoice_resp = await client.get(f"/api/v1/orders/{order_row.id}/invoice")
    assert invoice_resp.status_code == 404
    assert invoice_resp.json()["error"]["code"] == "INVOICE_NOT_AVAILABLE"

    # A fresh successful checkout on a new cart does get a downloadable
    # invoice.
    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 1})
    success_resp = await client.post(
        "/api/v1/orders/checkout", json=_checkout_body(address.id, "cod")
    )
    assert success_resp.status_code == 201
    success_order_id = success_resp.json()["id"]

    pdf_resp = await client.get(f"/api/v1/orders/{success_order_id}/invoice")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")


async def test_router_order_timeline(client, db_session):
    user = _FakeUser("cust-timeline", "cust-timeline@example.com")
    _override_user(user)
    address = await _make_address(db_session, user.id)

    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 1})
    checkout_resp = await client.post(
        "/api/v1/orders/checkout", json=_checkout_body(address.id, "cod")
    )
    order_id = checkout_resp.json()["id"]

    timeline_resp = await client.get(f"/api/v1/orders/{order_id}/timeline")
    assert timeline_resp.status_code == 200
    events = timeline_resp.json()
    assert [e["to_status"] for e in events] == ["pending", "paid"]
    assert events[0]["from_status"] is None
    assert events[1]["from_status"] == "pending"


# ---------------------------------------------------------------------------
# Admin endpoints: RBAC + behavior
# ---------------------------------------------------------------------------


@pytest.fixture
async def paid_order(client, db_session):
    user = _FakeUser("admin-target-user", "admin-target-user@example.com")
    _override_user(user)
    address = await _make_address(db_session, user.id)

    await client.post("/api/v1/cart/items", json={"product_id": "p1", "quantity": 1})
    resp = await client.post(
        "/api/v1/orders/checkout", json=_checkout_body(address.id, "test_card", "succeed")
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.parametrize("role", ["admin", "super_admin"])
async def test_admin_list_orders_allowed_for_admin_roles(client, db_session, paid_order, role):
    _override_user(_FakeUser("staff", "staff@example.com", role=role))

    resp = await client.get("/api/v1/admin/orders")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1


@pytest.mark.parametrize("role", ["manager", "customer"])
async def test_admin_list_orders_forbidden_for_non_admin_roles(client, db_session, paid_order, role):
    _override_user(_FakeUser("staff2", "staff2@example.com", role=role))

    resp = await client.get("/api/v1/admin/orders")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"


async def test_admin_list_orders_filters_by_status(client, db_session, paid_order):
    _override_user(_FakeUser("staff3", "staff3@example.com", role="admin"))

    resp = await client.get("/api/v1/admin/orders", params={"status": "paid"})
    assert resp.status_code == 200
    assert all(o["status"] == "paid" for o in resp.json()["items"])

    resp_none = await client.get("/api/v1/admin/orders", params={"status": "shipped"})
    assert resp_none.json()["total"] == 0


async def test_admin_update_status_allowed_for_admin(client, db_session, paid_order):
    _override_user(_FakeUser("staff4", "staff4@example.com", role="admin"))

    resp = await client.patch(
        f"/api/v1/admin/orders/{paid_order['id']}/status",
        json={"status": "shipped", "note": "left warehouse"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "shipped"


@pytest.mark.parametrize("role", ["manager", "customer"])
async def test_admin_update_status_forbidden_for_non_admin_roles(client, db_session, paid_order, role):
    _override_user(_FakeUser("staff5", "staff5@example.com", role=role))

    resp = await client.patch(
        f"/api/v1/admin/orders/{paid_order['id']}/status", json={"status": "shipped"}
    )
    assert resp.status_code == 403


async def test_admin_refund_allowed_for_admin(client, db_session, paid_order):
    _override_user(_FakeUser("staff6", "staff6@example.com", role="super_admin"))

    resp = await client.post(f"/api/v1/admin/orders/{paid_order['id']}/refund", json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "refunded"


async def test_router_admin_refund_partial_amount(client, db_session, paid_order):
    _override_user(_FakeUser("staff7", "staff7@example.com", role="admin"))

    resp = await client.post(
        f"/api/v1/admin/orders/{paid_order['id']}/refund", json={"amount_cents": 100}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "partially_refunded"
    assert resp.json()["refunded_amount_cents"] == 100


@pytest.mark.parametrize("role", ["manager", "customer"])
async def test_admin_refund_forbidden_for_non_admin_roles(client, db_session, paid_order, role):
    _override_user(_FakeUser("staff8", "staff8@example.com", role=role))

    resp = await client.post(f"/api/v1/admin/orders/{paid_order['id']}/refund", json={})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# INR Currency & GST (foundation scope): checkout integration.
#
# GST is fully opt-in (`settings.gst_enabled` defaults to False) and
# India-specific (`order.currency == "INR"` only) -- these tests exercise
# the real `service.checkout` path (not `calculate_gst` directly, which has
# its own exhaustive pure-function coverage in test_tax.py) to prove the
# wiring: tax fields land on the persisted Order, the Payment is charged
# `grand_total_cents` (not `total_cents`) when tax applies, and every
# existing USD/no-tax path is completely unaffected.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _gst_settings_reset(monkeypatch):
    """Every GST test controls its own settings explicitly; this just
    guarantees a clean, documented-default starting point and that nothing
    leaks into other test modules (monkeypatch auto-reverts after each
    test)."""
    monkeypatch.setattr(settings, "gst_enabled", False)
    monkeypatch.setattr(settings, "default_gst_rate_percent", 18.0)
    monkeypatch.setattr(settings, "seller_state", "Maharashtra")
    monkeypatch.setattr(settings, "tax_inclusive_pricing", False)


async def test_checkout_inr_intrastate_applies_cgst_sgst_and_charges_grand_total(
    session, monkeypatch
):
    settings.gst_enabled = True
    user = await _make_user(session)
    address = await _make_address(session, user.id, state="Maharashtra", country="IN")
    await _setup_cart(session, monkeypatch, user, address, price_cents=10000, currency="INR")

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    assert order.currency == "INR"
    assert order.total_cents == 10000
    assert order.taxable_amount_cents == 10000
    assert order.cgst_cents == 900
    assert order.sgst_cents == 900
    assert order.igst_cents == 0
    assert order.tax_total_cents == 1800
    assert order.grand_total_cents == 11800

    payment = (
        await session.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one()
    assert payment.amount_cents == order.grand_total_cents
    assert payment.amount_cents != order.total_cents

    # Invoice generation doesn't raise and still produces a real PDF with
    # the tax fields present (asserting on PDF byte content directly is
    # unreliable -- matches the existing invoice test's style of only
    # checking the %PDF prefix).
    pdf_bytes = await service.get_invoice_pdf_bytes(session, order.id, user.id, is_admin=False)
    assert pdf_bytes.startswith(b"%PDF")


async def test_checkout_inr_interstate_applies_igst_only(session, monkeypatch):
    settings.gst_enabled = True
    user = await _make_user(session)
    address = await _make_address(session, user.id, state="Karnataka", country="IN")
    await _setup_cart(session, monkeypatch, user, address, price_cents=10000, currency="INR")

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    assert order.cgst_cents == 0
    assert order.sgst_cents == 0
    assert order.igst_cents == 1800
    assert order.tax_total_cents == 1800
    assert order.grand_total_cents == 11800

    payment = (
        await session.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one()
    assert payment.amount_cents == 11800


async def test_checkout_usd_order_unaffected_by_gst_even_when_enabled(session, monkeypatch):
    # GST only ever applies to INR orders -- a USD checkout must behave
    # byte-for-byte as before, even with gst_enabled=True.
    settings.gst_enabled = True
    user = await _make_user(session)
    address = await _make_address(session, user.id, state="Maharashtra", country="US")
    await _setup_cart(session, monkeypatch, user, address, price_cents=10000, currency="USD")

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    assert order.currency == "USD"
    assert order.taxable_amount_cents is None
    assert order.cgst_cents is None
    assert order.sgst_cents is None
    assert order.igst_cents is None
    assert order.tax_total_cents is None
    assert order.grand_total_cents is None

    payment = (
        await session.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one()
    assert payment.amount_cents == order.total_cents == 10000


async def test_checkout_inr_order_with_gst_disabled_by_default_gets_no_tax_fields(
    session, monkeypatch
):
    # gst_enabled defaults to False -- proves the feature is fully opt-in,
    # even for an INR order with a valid buyer state.
    assert settings.gst_enabled is False
    user = await _make_user(session)
    address = await _make_address(session, user.id, state="Maharashtra", country="IN")
    await _setup_cart(session, monkeypatch, user, address, price_cents=10000, currency="INR")

    order = await service.checkout(session, user.id, _checkout_request(address.id, address.id, "cod"))

    assert order.currency == "INR"
    assert order.tax_total_cents is None
    assert order.grand_total_cents is None

    payment = (
        await session.execute(select(Payment).where(Payment.order_id == order.id))
    ).scalar_one()
    assert payment.amount_cents == order.total_cents == 10000
