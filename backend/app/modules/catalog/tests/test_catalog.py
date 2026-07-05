"""Catalog module tests.

Public GET routes are exercised through the real FastAPI app + HTTP client
(reusing the shared `db_session`/`client` fixtures from backend/tests/conftest.py).

Admin-only write routes (POST/PATCH/DELETE) require `require_role("admin")`
from `app.modules.auth.dependencies`. That module is being built in parallel
by the Identity & Security team and did not exist at the time these tests
were written. To avoid blocking on it we:

  1. Try to import the real `app.modules.auth.dependencies`.
  2. If it isn't there yet, install a minimal in-memory stand-in module in
     `sys.modules` under that exact dotted path (no files are written under
     app/modules/auth/ — this is purely a test-time shim) so that
     `app/modules/catalog/router.py`'s
     `from app.modules.auth.dependencies import require_role` import
     succeeds, and so we can still exercise the admin routes end-to-end via
     `app.dependency_overrides`.

Once the real auth module lands, step 1 succeeds and this shim is a no-op —
the Main Coordinator can then also add genuine router-level auth-rejection
tests (401/403) that this file does not attempt to cover.
"""
from __future__ import annotations

import sys
import types

import pytest

from app.main import app

try:
    from app.modules.auth.dependencies import require_role  # noqa: F401

    AUTH_MODULE_STUBBED = False
except ImportError:
    AUTH_MODULE_STUBBED = True

    _fake_auth_dependencies = types.ModuleType("app.modules.auth.dependencies")

    class _FakeUser:
        def __init__(self, id: str = "test-user-id", role: str = "admin"):
            self.id = id
            self.role = role

    async def _fake_get_current_user() -> _FakeUser:
        return _FakeUser()

    def _fake_require_role(role: str):
        async def _dependency() -> _FakeUser:
            return _FakeUser(role=role)

        return _dependency

    _fake_auth_dependencies.get_current_user = _fake_get_current_user
    _fake_auth_dependencies.require_role = _fake_require_role
    sys.modules["app.modules.auth.dependencies"] = _fake_auth_dependencies

from app.modules.catalog.router import admin_router, require_admin, router  # noqa: E402

# Reuse the shared fixtures rather than redefining them.
from tests.conftest import client, db_session  # noqa: E402,F401

# Mount the catalog router the same way the Main Coordinator will at
# integration time, guarding against double registration if this module is
# imported more than once in a single test session.
if not any(getattr(r, "path", None) == "/api/v1/categories" for r in app.routes):
    app.include_router(router, prefix="/api/v1")
if not any(getattr(r, "path", None) == "/api/v1/admin/products" for r in app.routes):
    app.include_router(admin_router, prefix="/api/v1")


async def _override_admin():
    class _Admin:
        id = "admin-under-test"
        role = "admin"

    return _Admin()


@pytest.fixture(autouse=True)
def _admin_override():
    app.dependency_overrides[require_admin] = _override_admin
    yield
    app.dependency_overrides.pop(require_admin, None)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _create_category(client, name="Electronics", slug="electronics"):
    resp = await client.post("/api/v1/categories", json={"name": name, "slug": slug})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_brand(client, name="Acme", slug="acme"):
    resp = await client.post("/api/v1/brands", json={"name": name, "slug": slug})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_product(client, category_id, brand_id=None, **overrides):
    payload = {
        "name": "Widget",
        "slug": "widget",
        "category_id": category_id,
        "brand_id": brand_id,
        "price_cents": 1999,
        "currency": "USD",
        "sku": "SKU-1",
        "stock_quantity": 10,
        "is_active": True,
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/products", json=payload)
    return resp


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


async def test_create_and_list_categories(client):
    await _create_category(client)
    resp = await client.get("/api/v1/categories")
    assert resp.status_code == 200
    slugs = [c["slug"] for c in resp.json()]
    assert "electronics" in slugs


async def test_duplicate_category_slug_conflicts(client):
    await _create_category(client)
    resp = await client.post("/api/v1/categories", json={"name": "Dup", "slug": "electronics"})
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "DUPLICATE_SLUG"


async def test_create_category_with_image_url(client):
    resp = await client.post(
        "/api/v1/categories",
        json={"name": "Books", "slug": "books", "image_url": "https://example.com/books.png"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["image_url"] == "https://example.com/books.png"


async def test_patch_category_partial_update(client):
    category = await _create_category(client)

    resp = await client.patch(
        f"/api/v1/categories/{category['id']}",
        json={"image_url": "https://example.com/electronics.png"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["image_url"] == "https://example.com/electronics.png"
    # untouched fields remain as-is
    assert body["name"] == "Electronics"
    assert body["slug"] == "electronics"


async def test_patch_category_slug_uniqueness_enforced(client):
    await _create_category(client, name="A", slug="cat-a")
    cat_b = await _create_category(client, name="B", slug="cat-b")

    resp = await client.patch(f"/api/v1/categories/{cat_b['id']}", json={"slug": "cat-a"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_SLUG"


async def test_patch_category_missing_404(client):
    resp = await client.patch("/api/v1/categories/does-not-exist", json={"name": "X"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_delete_category_success(client):
    category = await _create_category(client)

    resp = await client.delete(f"/api/v1/categories/{category['id']}")
    assert resp.status_code == 204

    list_resp = await client.get("/api/v1/categories")
    assert category["id"] not in [c["id"] for c in list_resp.json()]


async def test_delete_category_blocked_by_product(client):
    category = await _create_category(client)
    await _create_product(client, category_id=category["id"])

    resp = await client.delete(f"/api/v1/categories/{category['id']}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CATEGORY_IN_USE"


async def test_delete_category_blocked_by_child_category(client):
    parent = await _create_category(client, name="Parent", slug="parent")
    await client.post(
        "/api/v1/categories", json={"name": "Child", "slug": "child", "parent_id": parent["id"]}
    )

    resp = await client.delete(f"/api/v1/categories/{parent['id']}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CATEGORY_IN_USE"


async def test_delete_category_missing_404(client):
    resp = await client.delete("/api/v1/categories/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------


async def test_create_and_list_brands(client):
    await _create_brand(client)
    resp = await client.get("/api/v1/brands")
    assert resp.status_code == 200
    slugs = [b["slug"] for b in resp.json()]
    assert "acme" in slugs


async def test_duplicate_brand_slug_conflicts(client):
    await _create_brand(client)
    resp = await client.post("/api/v1/brands", json={"name": "Dup", "slug": "acme"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_SLUG"


async def test_patch_brand_partial_update(client):
    brand = await _create_brand(client)

    resp = await client.patch(f"/api/v1/brands/{brand['id']}", json={"name": "Acme Corp"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Acme Corp"
    assert body["slug"] == "acme"


async def test_patch_brand_slug_uniqueness_enforced(client):
    await _create_brand(client, name="A", slug="brand-a")
    brand_b = await _create_brand(client, name="B", slug="brand-b")

    resp = await client.patch(f"/api/v1/brands/{brand_b['id']}", json={"slug": "brand-a"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "DUPLICATE_SLUG"


async def test_patch_brand_missing_404(client):
    resp = await client.patch("/api/v1/brands/does-not-exist", json={"name": "X"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_delete_brand_success(client):
    brand = await _create_brand(client)

    resp = await client.delete(f"/api/v1/brands/{brand['id']}")
    assert resp.status_code == 204

    list_resp = await client.get("/api/v1/brands")
    assert brand["id"] not in [b["id"] for b in list_resp.json()]


async def test_delete_brand_blocked_by_product(client):
    category = await _create_category(client)
    brand = await _create_brand(client)
    await _create_product(client, category_id=category["id"], brand_id=brand["id"])

    resp = await client.delete(f"/api/v1/brands/{brand['id']}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BRAND_IN_USE"


async def test_delete_brand_missing_404(client):
    resp = await client.delete("/api/v1/brands/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


async def test_create_get_and_list_product(client):
    category = await _create_category(client)
    brand = await _create_brand(client)

    resp = await _create_product(client, category_id=category["id"], brand_id=brand["id"])
    assert resp.status_code == 201, resp.text
    product = resp.json()
    assert product["sku"] == "SKU-1"
    assert product["images"] == []

    get_resp = await client.get(f"/api/v1/products/{product['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == product["id"]

    list_resp = await client.get("/api/v1/products")
    assert list_resp.status_code == 200
    page = list_resp.json()
    assert page["total"] == 1
    assert page["page"] == 1
    assert page["page_size"] == 20
    assert len(page["items"]) == 1


async def test_get_missing_product_404(client):
    resp = await client.get("/api/v1/products/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_duplicate_product_slug_and_sku_conflict(client):
    category = await _create_category(client)
    await _create_product(client, category_id=category["id"])

    dup_slug = await _create_product(client, category_id=category["id"], sku="SKU-2")
    assert dup_slug.status_code == 409
    assert dup_slug.json()["error"]["code"] == "DUPLICATE_SLUG"

    dup_sku = await _create_product(client, category_id=category["id"], slug="widget-2")
    assert dup_sku.status_code == 409
    assert dup_sku.json()["error"]["code"] == "DUPLICATE_SKU"


async def test_product_with_images(client):
    category = await _create_category(client)
    resp = await _create_product(
        client,
        category_id=category["id"],
        images=[{"url": "https://example.com/a.png", "alt_text": "A", "sort_order": 0}],
    )
    assert resp.status_code == 201, resp.text
    product = resp.json()
    assert len(product["images"]) == 1
    assert product["images"][0]["url"] == "https://example.com/a.png"


async def test_update_product(client):
    category = await _create_category(client)
    created = (await _create_product(client, category_id=category["id"])).json()

    resp = await client.patch(f"/api/v1/products/{created['id']}", json={"price_cents": 2999})
    assert resp.status_code == 200
    assert resp.json()["price_cents"] == 2999
    # untouched fields remain as-is
    assert resp.json()["sku"] == "SKU-1"


async def test_delete_product(client):
    category = await _create_category(client)
    created = (await _create_product(client, category_id=category["id"])).json()

    resp = await client.delete(f"/api/v1/products/{created['id']}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/products/{created['id']}")
    assert get_resp.status_code == 404


async def test_delete_product_blocked_when_referenced_by_order_item(client, db_session):
    """Regression test: deleting a product that's been ordered used to raise
    a raw FK IntegrityError (500) instead of a clean 409 -- see the
    `order_items_product_id_fkey` constraint. Inserted via a raw Core table
    (not an `orders` model import) since catalog can't depend on orders."""
    from datetime import datetime, timezone

    from sqlalchemy import column, insert, table

    category = await _create_category(client)
    created = (await _create_product(client, category_id=category["id"])).json()

    now = datetime.now(timezone.utc)

    order_items_table = table(
        "order_items",
        column("id"),
        column("order_id"),
        column("product_id"),
        column("product_name_snapshot"),
        column("sku_snapshot"),
        column("quantity"),
        column("unit_price_cents"),
    )
    orders_table = table(
        "orders",
        column("id"),
        column("user_id"),
        column("status"),
        column("total_cents"),
        column("currency"),
        column("created_at"),
        column("updated_at"),
    )
    users_table = table(
        "users",
        column("id"),
        column("email"),
        column("hashed_password"),
        column("full_name"),
        column("role"),
        column("is_active"),
        column("created_at"),
        column("updated_at"),
    )

    await db_session.execute(
        insert(users_table).values(
            id="user-for-order-item-test",
            email="orderer@example.com",
            hashed_password="x",
            full_name="Orderer",
            role="customer",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.execute(
        insert(orders_table).values(
            id="order-for-product-in-use-test",
            user_id="user-for-order-item-test",
            status="paid",
            total_cents=1999,
            currency="USD",
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.execute(
        insert(order_items_table).values(
            id="order-item-for-product-in-use-test",
            order_id="order-for-product-in-use-test",
            product_id=created["id"],
            product_name_snapshot=created["name"],
            sku_snapshot=created["sku"],
            quantity=1,
            unit_price_cents=created["price_cents"],
        )
    )
    await db_session.commit()

    resp = await client.delete(f"/api/v1/products/{created['id']}")
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "PRODUCT_IN_USE"

    # Product must still exist -- the blocked delete shouldn't have partially applied.
    get_resp = await client.get(f"/api/v1/products/{created['id']}")
    assert get_resp.status_code == 200


async def test_list_products_filters_by_category_brand_and_query(client):
    cat_a = await _create_category(client, name="Cat A", slug="cat-a")
    cat_b = await _create_category(client, name="Cat B", slug="cat-b")
    brand = await _create_brand(client)

    await _create_product(client, category_id=cat_a["id"], brand_id=brand["id"], slug="red-widget", sku="SKU-A", name="Red Widget")
    await _create_product(client, category_id=cat_b["id"], slug="blue-gadget", sku="SKU-B", name="Blue Gadget")

    by_category = await client.get("/api/v1/products", params={"category_id": cat_a["id"]})
    assert by_category.json()["total"] == 1
    assert by_category.json()["items"][0]["slug"] == "red-widget"

    by_brand = await client.get("/api/v1/products", params={"brand_id": brand["id"]})
    assert by_brand.json()["total"] == 1
    assert by_brand.json()["items"][0]["slug"] == "red-widget"

    by_query = await client.get("/api/v1/products", params={"q": "gadget"})
    assert by_query.json()["total"] == 1
    assert by_query.json()["items"][0]["slug"] == "blue-gadget"

    # case-insensitive
    by_query_upper = await client.get("/api/v1/products", params={"q": "GADGET"})
    assert by_query_upper.json()["total"] == 1


async def test_products_pagination(client):
    category = await _create_category(client)
    for i in range(5):
        await _create_product(
            client, category_id=category["id"], slug=f"widget-{i}", sku=f"SKU-{i}"
        )

    resp = await client.get("/api/v1/products", params={"page": 1, "page_size": 2})
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2

    resp_page3 = await client.get("/api/v1/products", params={"page": 3, "page_size": 2})
    assert len(resp_page3.json()["items"]) == 1


# ---------------------------------------------------------------------------
# Inactive product visibility (regression: the public listing/detail routes
# had no is_active filter at all, so a "deactivated" product was still
# fully browsable and directly viewable by anyone).
# ---------------------------------------------------------------------------


async def test_public_product_list_excludes_inactive_products(client):
    category = await _create_category(client)
    active = (await _create_product(client, category_id=category["id"], slug="active-widget", sku="SKU-ACTIVE")).json()
    inactive = (
        await _create_product(
            client, category_id=category["id"], slug="inactive-widget", sku="SKU-INACTIVE", is_active=False
        )
    ).json()

    resp = await client.get("/api/v1/products")
    slugs = [p["slug"] for p in resp.json()["items"]]
    assert active["slug"] in slugs
    assert inactive["slug"] not in slugs
    # total must reflect the filtered count, not just the returned page
    assert resp.json()["total"] == 1


async def test_public_product_detail_404s_for_inactive_product(client):
    category = await _create_category(client)
    inactive = (
        await _create_product(client, category_id=category["id"], slug="hidden-widget", sku="SKU-HIDDEN", is_active=False)
    ).json()

    resp = await client.get(f"/api/v1/products/{inactive['id']}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_admin_product_list_includes_inactive_products(client):
    category = await _create_category(client)
    active = (await _create_product(client, category_id=category["id"], slug="active-2", sku="SKU-A2")).json()
    inactive = (
        await _create_product(client, category_id=category["id"], slug="inactive-2", sku="SKU-I2", is_active=False)
    ).json()

    resp = await client.get("/api/v1/admin/products")
    assert resp.status_code == 200
    slugs = [p["slug"] for p in resp.json()["items"]]
    assert active["slug"] in slugs
    assert inactive["slug"] in slugs
    assert resp.json()["total"] == 2


async def test_admin_product_detail_returns_inactive_product(client):
    category = await _create_category(client)
    inactive = (
        await _create_product(client, category_id=category["id"], slug="hidden-2", sku="SKU-HIDDEN-2", is_active=False)
    ).json()

    resp = await client.get(f"/api/v1/admin/products/{inactive['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == inactive["id"]
    assert resp.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Cross-module contract: orders team depends on this exact function.
#
#   async def get_available_product(db, product_id) -> ProductOrderView | None
#
# Tested directly at the service layer (no HTTP/auth involved) since this is
# an in-process call, not a route.
# ---------------------------------------------------------------------------


async def test_get_available_product_returns_view_for_active_product(db_session):
    from app.modules.catalog import service
    from app.modules.catalog.schemas import CategoryCreate, ProductCreate, ProductOrderView

    category = await service.create_category(db_session, CategoryCreate(name="C", slug="c"))
    product = await service.create_product(
        db_session,
        ProductCreate(
            name="Gizmo",
            slug="gizmo",
            category_id=category.id,
            price_cents=500,
            currency="USD",
            sku="SKU-GIZMO",
            stock_quantity=3,
            is_active=True,
        ),
    )

    view = await service.get_available_product(db_session, product.id)
    assert isinstance(view, ProductOrderView)
    assert view.id == product.id
    assert view.price_cents == 500
    assert view.currency == "USD"
    assert view.stock_quantity == 3


async def test_get_available_product_returns_none_for_inactive_product(db_session):
    from app.modules.catalog import service
    from app.modules.catalog.schemas import CategoryCreate, ProductCreate

    category = await service.create_category(db_session, CategoryCreate(name="C2", slug="c2"))
    product = await service.create_product(
        db_session,
        ProductCreate(
            name="Discontinued",
            slug="discontinued",
            category_id=category.id,
            price_cents=100,
            currency="USD",
            sku="SKU-OLD",
            is_active=False,
        ),
    )

    view = await service.get_available_product(db_session, product.id)
    assert view is None


async def test_get_available_product_returns_none_for_missing_product(db_session):
    from app.modules.catalog import service

    view = await service.get_available_product(db_session, "does-not-exist")
    assert view is None


# ---------------------------------------------------------------------------
# Storefront filtering/sorting: min_price_cents/max_price_cents/
# in_stock_only/sort, per docs/CONTRACTS.md "Storefront: Homepage,
# Filtering, Wishlist & Static Pages (foundation scope)".
# ---------------------------------------------------------------------------


async def _set_created_at(db_session, product_id: str, created_at) -> None:
    """Directly overwrites a product's created_at via a raw Core table
    (mirrors test_delete_product_blocked_when_referenced_by_order_item's
    raw-table-insert technique) so "newest"/pagination-order tests don't
    depend on real wall-clock timing between fast successive inserts."""
    from sqlalchemy import column, table, update

    products_table = table("products", column("id"), column("created_at"))
    await db_session.execute(
        update(products_table).where(products_table.c.id == product_id).values(created_at=created_at)
    )
    await db_session.commit()


async def _make_sortable_products(client, db_session, category_id):
    """Three products with distinct prices, names, and creation times:

        slug          name    price_cents  stock_quantity  created (order)
        alpha-widget  Alpha   3000         5               1st (oldest)
        beta-widget   Beta    1000         0               2nd
        gamma-widget  Gamma   2000         10              3rd (newest)
    """
    from datetime import datetime, timedelta, timezone

    base = datetime(2025, 1, 1, tzinfo=timezone.utc)

    alpha = (
        await _create_product(
            client,
            category_id=category_id,
            slug="alpha-widget",
            sku="SKU-ALPHA",
            name="Alpha",
            price_cents=3000,
            stock_quantity=5,
        )
    ).json()
    beta = (
        await _create_product(
            client,
            category_id=category_id,
            slug="beta-widget",
            sku="SKU-BETA",
            name="Beta",
            price_cents=1000,
            stock_quantity=0,
        )
    ).json()
    gamma = (
        await _create_product(
            client,
            category_id=category_id,
            slug="gamma-widget",
            sku="SKU-GAMMA",
            name="Gamma",
            price_cents=2000,
            stock_quantity=10,
        )
    ).json()

    await _set_created_at(db_session, alpha["id"], base)
    await _set_created_at(db_session, beta["id"], base + timedelta(minutes=1))
    await _set_created_at(db_session, gamma["id"], base + timedelta(minutes=2))

    return alpha, beta, gamma


async def test_min_price_filter_excludes_cheaper_products(client, db_session):
    category = await _create_category(client)
    alpha, beta, gamma = await _make_sortable_products(client, db_session, category["id"])

    resp = await client.get("/api/v1/products", params={"min_price_cents": 2000})
    slugs = {p["slug"] for p in resp.json()["items"]}
    assert slugs == {alpha["slug"], gamma["slug"]}
    assert resp.json()["total"] == 2


async def test_max_price_filter_excludes_pricier_products(client, db_session):
    category = await _create_category(client)
    alpha, beta, gamma = await _make_sortable_products(client, db_session, category["id"])

    resp = await client.get("/api/v1/products", params={"max_price_cents": 2000})
    slugs = {p["slug"] for p in resp.json()["items"]}
    assert slugs == {beta["slug"], gamma["slug"]}
    assert resp.json()["total"] == 2


async def test_price_range_filter_combines_min_and_max(client, db_session):
    category = await _create_category(client)
    alpha, beta, gamma = await _make_sortable_products(client, db_session, category["id"])

    resp = await client.get(
        "/api/v1/products", params={"min_price_cents": 1500, "max_price_cents": 2500}
    )
    slugs = {p["slug"] for p in resp.json()["items"]}
    assert slugs == {gamma["slug"]}
    assert resp.json()["total"] == 1


async def test_in_stock_only_excludes_zero_stock_products(client, db_session):
    category = await _create_category(client)
    alpha, beta, gamma = await _make_sortable_products(client, db_session, category["id"])

    resp = await client.get("/api/v1/products", params={"in_stock_only": True})
    slugs = {p["slug"] for p in resp.json()["items"]}
    assert slugs == {alpha["slug"], gamma["slug"]}
    assert beta["slug"] not in slugs
    assert resp.json()["total"] == 2


@pytest.mark.parametrize(
    "sort,expected_order",
    [
        ("newest", ["gamma-widget", "beta-widget", "alpha-widget"]),
        ("price_asc", ["beta-widget", "gamma-widget", "alpha-widget"]),
        ("price_desc", ["alpha-widget", "gamma-widget", "beta-widget"]),
        ("name_asc", ["alpha-widget", "beta-widget", "gamma-widget"]),
        ("name_desc", ["gamma-widget", "beta-widget", "alpha-widget"]),
    ],
)
async def test_sort_orders_produce_expected_sequence(client, db_session, sort, expected_order):
    category = await _create_category(client)
    await _make_sortable_products(client, db_session, category["id"])

    resp = await client.get("/api/v1/products", params={"sort": sort})
    slugs = [p["slug"] for p in resp.json()["items"]]
    assert slugs == expected_order


async def test_no_sort_or_filter_params_behaves_exactly_like_before(client, db_session):
    """Regression guard: a request with none of the new params set must
    produce the exact same ordering/results as the pre-existing hardcoded
    `order_by(Product.created_at.desc())` default."""
    category = await _create_category(client)
    await _make_sortable_products(client, db_session, category["id"])

    default_resp = await client.get("/api/v1/products")
    newest_resp = await client.get("/api/v1/products", params={"sort": "newest"})

    assert [p["slug"] for p in default_resp.json()["items"]] == [
        p["slug"] for p in newest_resp.json()["items"]
    ]
    assert [p["slug"] for p in default_resp.json()["items"]] == [
        "gamma-widget",
        "beta-widget",
        "alpha-widget",
    ]


async def test_price_and_stock_filters_combine_with_category_and_query(client, db_session):
    cat_a = await _create_category(client, name="Cat A", slug="cat-a-sort")
    cat_b = await _create_category(client, name="Cat B", slug="cat-b-sort")

    matching = (
        await _create_product(
            client,
            category_id=cat_a["id"],
            slug="matching-widget",
            sku="SKU-MATCH",
            name="Matching Gadget",
            price_cents=1500,
            stock_quantity=4,
        )
    ).json()
    # Wrong category.
    await _create_product(
        client,
        category_id=cat_b["id"],
        slug="wrong-category-gadget",
        sku="SKU-WRONGCAT",
        name="Wrong Category Gadget",
        price_cents=1500,
        stock_quantity=4,
    )
    # Right category, wrong price range.
    await _create_product(
        client,
        category_id=cat_a["id"],
        slug="too-expensive-gadget",
        sku="SKU-EXPENSIVE",
        name="Too Expensive Gadget",
        price_cents=9000,
        stock_quantity=4,
    )
    # Right category and price, but doesn't match query and out of stock.
    await _create_product(
        client,
        category_id=cat_a["id"],
        slug="out-of-stock-widget",
        sku="SKU-OOS",
        name="Out Of Stock Widget",
        price_cents=1500,
        stock_quantity=0,
    )

    resp = await client.get(
        "/api/v1/products",
        params={
            "category_id": cat_a["id"],
            "q": "gadget",
            "min_price_cents": 1000,
            "max_price_cents": 2000,
            "in_stock_only": True,
        },
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == matching["slug"]


async def test_admin_products_support_same_filter_and_sort_params(client, db_session):
    category = await _create_category(client)
    alpha, beta, gamma = await _make_sortable_products(client, db_session, category["id"])

    resp = await client.get(
        "/api/v1/admin/products",
        params={"min_price_cents": 1500, "sort": "price_asc"},
    )
    slugs = [p["slug"] for p in resp.json()["items"]]
    assert slugs == [gamma["slug"], alpha["slug"]]
