"""Tests for the addresses module: CRUD, the "only one default
shipping/billing address at a time" invariant, 404-not-403 on another
user's address, and the cross-module `get_address_for_user` contract
`orders` depends on, per docs/CONTRACTS.md.

Follows the same temporary-mount pattern as other modules' router tests
(e.g. app/modules/auth/tests/test_admin_users.py): `router` isn't wired
into app/main.py yet (that's the Main Coordinator's job), so it's mounted
here, guarded against double registration.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.errors import AppError
from app.main import app
from app.modules.addresses import service
from app.modules.addresses.router import router as addresses_router
from app.modules.addresses.schemas import AddressCreate, AddressUpdate
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User  # noqa: F401 (registers users table)
from app.shared.base_model import Base

pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", None) == "/api/v1/addresses" for r in app.routes):
    app.include_router(addresses_router, prefix="/api/v1")


BASE_ADDRESS = dict(
    full_name="Ada Lovelace",
    phone="+1-555-0100",
    address_line1="123 Analytical Engine Way",
    city="London",
    state="LDN",
    country="UK",
    postal_code="SW1A",
)


def _address_payload(**overrides) -> dict:
    payload = dict(BASE_ADDRESS)
    payload.update(overrides)
    return payload


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


async def _make_user(session, email="addr-user@example.com") -> User:
    user = User(email=email, hashed_password="x", full_name="Addr User")
    session.add(user)
    await session.commit()
    return user


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


async def test_create_and_list_addresses(session):
    user = await _make_user(session)

    created = await service.create_address(session, user.id, AddressCreate(**_address_payload()))
    assert created.user_id == user.id
    assert created.address_type == "home"
    assert created.is_default_shipping is False

    addresses = await service.list_addresses_for_user(session, user.id)
    assert len(addresses) == 1
    assert addresses[0].id == created.id


async def test_list_addresses_only_returns_own(session):
    user_a = await _make_user(session, email="a@example.com")
    user_b = await _make_user(session, email="b@example.com")

    await service.create_address(session, user_a.id, AddressCreate(**_address_payload()))

    addresses_b = await service.list_addresses_for_user(session, user_b.id)
    assert addresses_b == []


async def test_setting_new_default_shipping_clears_old_default(session):
    user = await _make_user(session)

    first = await service.create_address(
        session, user.id, AddressCreate(**_address_payload(is_default_shipping=True))
    )
    assert first.is_default_shipping is True

    second = await service.create_address(
        session,
        user.id,
        AddressCreate(**_address_payload(full_name="Grace Hopper", is_default_shipping=True)),
    )
    assert second.is_default_shipping is True

    addresses = {a.id: a for a in await service.list_addresses_for_user(session, user.id)}
    assert addresses[first.id].is_default_shipping is False
    assert addresses[second.id].is_default_shipping is True


async def test_setting_new_default_billing_clears_old_default_on_update(session):
    user = await _make_user(session)

    first = await service.create_address(
        session, user.id, AddressCreate(**_address_payload(is_default_billing=True))
    )
    second = await service.create_address(session, user.id, AddressCreate(**_address_payload()))

    updated_second = await service.update_address(
        session, second.id, user.id, AddressUpdate(is_default_billing=True)
    )
    assert updated_second.is_default_billing is True

    refreshed_first = await service.update_address(session, first.id, user.id, AddressUpdate())
    assert refreshed_first.is_default_billing is False


async def test_default_shipping_and_billing_are_independent(session):
    user = await _make_user(session)

    a1 = await service.create_address(
        session, user.id, AddressCreate(**_address_payload(is_default_shipping=True))
    )
    a2 = await service.create_address(
        session,
        user.id,
        AddressCreate(**_address_payload(full_name="Grace Hopper", is_default_billing=True)),
    )

    addresses = {a.id: a for a in await service.list_addresses_for_user(session, user.id)}
    # a1 keeps its default-shipping flag; a2's default-billing flag doesn't
    # touch a1's default-shipping flag (independent invariants).
    assert addresses[a1.id].is_default_shipping is True
    assert addresses[a2.id].is_default_billing is True


async def test_update_address_changes_fields(session):
    user = await _make_user(session)
    address = await service.create_address(session, user.id, AddressCreate(**_address_payload()))

    updated = await service.update_address(
        session, address.id, user.id, AddressUpdate(city="Manchester")
    )
    assert updated.city == "Manchester"
    assert updated.full_name == "Ada Lovelace"  # untouched fields preserved


async def test_update_address_not_owned_raises_404(session):
    owner = await _make_user(session, email="owner@example.com")
    intruder = await _make_user(session, email="intruder@example.com")
    address = await service.create_address(session, owner.id, AddressCreate(**_address_payload()))

    with pytest.raises(AppError) as exc_info:
        await service.update_address(session, address.id, intruder.id, AddressUpdate(city="Nope"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.code.value == "RESOURCE_NOT_FOUND"


async def test_update_address_missing_raises_404(session):
    user = await _make_user(session)

    with pytest.raises(AppError) as exc_info:
        await service.update_address(session, "does-not-exist", user.id, AddressUpdate(city="X"))

    assert exc_info.value.status_code == 404


async def test_delete_address_removes_it(session):
    user = await _make_user(session)
    address = await service.create_address(session, user.id, AddressCreate(**_address_payload()))

    await service.delete_address(session, address.id, user.id)

    assert await service.list_addresses_for_user(session, user.id) == []


async def test_delete_address_not_owned_raises_404(session):
    owner = await _make_user(session, email="owner2@example.com")
    intruder = await _make_user(session, email="intruder2@example.com")
    address = await service.create_address(session, owner.id, AddressCreate(**_address_payload()))

    with pytest.raises(AppError) as exc_info:
        await service.delete_address(session, address.id, intruder.id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code.value == "RESOURCE_NOT_FOUND"

    # Address must still exist, untouched, for its actual owner.
    remaining = await service.list_addresses_for_user(session, owner.id)
    assert len(remaining) == 1


# ---------------------------------------------------------------------------
# Cross-module contract: get_address_for_user (consumed directly by orders)
# ---------------------------------------------------------------------------


async def test_get_address_for_user_returns_address_for_owner(session):
    user = await _make_user(session)
    address = await service.create_address(session, user.id, AddressCreate(**_address_payload()))

    found = await service.get_address_for_user(session, address.id, user.id)
    assert found is not None
    assert found.id == address.id


async def test_get_address_for_user_returns_none_for_non_owner(session):
    owner = await _make_user(session, email="owner3@example.com")
    intruder = await _make_user(session, email="intruder3@example.com")
    address = await service.create_address(session, owner.id, AddressCreate(**_address_payload()))

    found = await service.get_address_for_user(session, address.id, intruder.id)
    assert found is None


async def test_get_address_for_user_returns_none_for_missing_address(session):
    user = await _make_user(session)

    found = await service.get_address_for_user(session, "does-not-exist", user.id)
    assert found is None


# ---------------------------------------------------------------------------
# Router-level tests: real FastAPI app + HTTP client.
# ---------------------------------------------------------------------------


class _FakeUser:
    def __init__(self, id: str):
        self.id = id


@pytest.fixture
def current_user_id():
    return "router-addr-user"


@pytest.fixture(autouse=True)
def _auth_override(current_user_id):
    async def _fake_current_user():
        return _FakeUser(current_user_id)

    app.dependency_overrides[get_current_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def test_router_create_list_addresses(client, db_session):
    resp = await client.post("/api/v1/addresses", json=_address_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["full_name"] == "Ada Lovelace"
    assert body["address_type"] == "home"

    list_resp = await client.get("/api/v1/addresses")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_router_patch_address(client, db_session):
    create_resp = await client.post("/api/v1/addresses", json=_address_payload())
    address_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/v1/addresses/{address_id}", json={"city": "Manchester"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["city"] == "Manchester"


async def test_router_delete_address(client, db_session):
    create_resp = await client.post("/api/v1/addresses", json=_address_payload())
    address_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/addresses/{address_id}")
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/addresses")
    assert list_resp.json() == []


async def test_router_patch_another_users_address_returns_404_not_403(client, db_session):
    # Register address as user A.
    async def _fake_user_a():
        return _FakeUser("user-a")

    app.dependency_overrides[get_current_user] = _fake_user_a
    create_resp = await client.post("/api/v1/addresses", json=_address_payload())
    assert create_resp.status_code == 201
    address_id = create_resp.json()["id"]

    # Switch to user B and try to patch/delete user A's address.
    async def _fake_user_b():
        return _FakeUser("user-b")

    app.dependency_overrides[get_current_user] = _fake_user_b

    patch_resp = await client.patch(f"/api/v1/addresses/{address_id}", json={"city": "Nope"})
    assert patch_resp.status_code == 404
    assert patch_resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    delete_resp = await client.delete(f"/api/v1/addresses/{address_id}")
    assert delete_resp.status_code == 404
    assert delete_resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_router_requires_authentication(client, db_session):
    app.dependency_overrides.pop(get_current_user, None)

    resp = await client.get("/api/v1/addresses")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


# ---------------------------------------------------------------------------
# INR Currency & GST (foundation scope): `gstin` format validation.
# Format only (not checksum/government lookup) per docs/CONTRACTS.md --
# `None` stays fully optional so every address/test without a GSTIN keeps
# working unchanged.
# ---------------------------------------------------------------------------

VALID_GSTIN = "27AAPFU0939F1ZV"


def test_address_create_accepts_none_gstin():
    address = AddressCreate(**_address_payload())
    assert address.gstin is None


def test_address_create_accepts_valid_gstin():
    address = AddressCreate(**_address_payload(gstin=VALID_GSTIN))
    assert address.gstin == VALID_GSTIN


@pytest.mark.parametrize(
    "bad_gstin",
    [
        "not-a-gstin",
        "27AAPFU0939F1Z",  # one character short
        "27aapfu0939f1zv",  # lowercase
        "27AAPFU0939F1ZV1",  # one character too long
    ],
)
def test_address_create_rejects_malformed_gstin(bad_gstin):
    with pytest.raises(ValidationError):
        AddressCreate(**_address_payload(gstin=bad_gstin))


def test_address_update_accepts_none_and_valid_gstin():
    assert AddressUpdate(gstin=None).gstin is None
    assert AddressUpdate(gstin=VALID_GSTIN).gstin == VALID_GSTIN


def test_address_update_rejects_malformed_gstin():
    with pytest.raises(ValidationError):
        AddressUpdate(gstin="bad-gstin")


async def test_router_create_address_with_malformed_gstin_returns_422_validation_error(
    client, db_session
):
    resp = await client.post("/api/v1/addresses", json=_address_payload(gstin="bad-gstin"))

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_router_create_address_with_valid_gstin_is_accepted(client, db_session):
    resp = await client.post("/api/v1/addresses", json=_address_payload(gstin=VALID_GSTIN))

    assert resp.status_code == 201, resp.text
    assert resp.json()["gstin"] == VALID_GSTIN


async def test_router_create_address_without_gstin_still_works(client, db_session):
    resp = await client.post("/api/v1/addresses", json=_address_payload())

    assert resp.status_code == 201, resp.text
    assert resp.json()["gstin"] is None


async def test_router_patch_address_with_malformed_gstin_returns_422(client, db_session):
    create_resp = await client.post("/api/v1/addresses", json=_address_payload())
    address_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/addresses/{address_id}", json={"gstin": "bad-gstin"})

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
