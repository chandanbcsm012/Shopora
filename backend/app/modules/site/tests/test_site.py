"""Tests for the site module: newsletter subscription (including the
"always the same response, idempotent, no enumeration leak" contract),
contact-message submission, and the admin contact-message inbox
(role-gated, paginated, newest-first), per docs/CONTRACTS.md.

Follows the same temporary-mount pattern as other modules' router tests
(e.g. app/modules/addresses/tests/test_addresses.py): `router`/
`admin_router` aren't wired into app/main.py yet (that's the Main
Coordinator's job), so they're mounted here, guarded against double
registration.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.site import service
from app.modules.site.models import ContactMessage, NewsletterSubscriber
from app.modules.site.router import admin_router as site_admin_router
from app.modules.site.router import require_admin
from app.modules.site.router import router as site_router
from app.shared.base_model import Base
from app.shared.pagination import PageParams

pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", None) == "/api/v1/contact" for r in app.routes):
    app.include_router(site_router, prefix="/api/v1")
if not any(getattr(r, "path", None) == "/api/v1/admin/contact-messages" for r in app.routes):
    app.include_router(site_admin_router, prefix="/api/v1")


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


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


async def test_subscribe_to_newsletter_creates_a_row(session):
    await service.subscribe_to_newsletter(session, "shopper@example.com")

    rows = (await session.execute(select(NewsletterSubscriber))).scalars().all()
    assert len(rows) == 1
    assert rows[0].email == "shopper@example.com"


async def test_subscribing_same_email_twice_does_not_duplicate(session):
    await service.subscribe_to_newsletter(session, "shopper@example.com")
    await service.subscribe_to_newsletter(session, "shopper@example.com")

    rows = (await session.execute(select(NewsletterSubscriber))).scalars().all()
    assert len(rows) == 1


async def test_submit_contact_message_creates_row_with_correct_fields(session):
    message = await service.submit_contact_message(
        session, "Ada Lovelace", "ada@example.com", "Order question", "Where is my order?"
    )

    assert message.name == "Ada Lovelace"
    assert message.email == "ada@example.com"
    assert message.subject == "Order question"
    assert message.message == "Where is my order?"
    assert message.id is not None
    assert message.created_at is not None

    rows = (await session.execute(select(ContactMessage))).scalars().all()
    assert len(rows) == 1


async def test_list_contact_messages_newest_first_and_paginated(session):
    for i in range(25):
        await service.submit_contact_message(
            session, f"User {i}", f"user{i}@example.com", f"Subject {i}", f"Message {i}"
        )

    page_1, total = await service.list_contact_messages(session, PageParams(page=1, page_size=20))
    assert total == 25
    assert len(page_1) == 20
    # Newest first: the most-recently-created message (index 24) leads.
    assert page_1[0].subject == "Subject 24"

    page_2, total_2 = await service.list_contact_messages(session, PageParams(page=2, page_size=20))
    assert total_2 == 25
    assert len(page_2) == 5


# ---------------------------------------------------------------------------
# Router-level tests: real FastAPI app + HTTP client.
# ---------------------------------------------------------------------------


async def test_router_newsletter_subscribe_returns_202(client, db_session):
    resp = await client.post("/api/v1/newsletter/subscribe", json={"email": "shopper@example.com"})
    assert resp.status_code == 202


async def test_router_newsletter_subscribe_twice_does_not_duplicate(client, db_session):
    first = await client.post("/api/v1/newsletter/subscribe", json={"email": "shopper@example.com"})
    second = await client.post("/api/v1/newsletter/subscribe", json={"email": "shopper@example.com"})
    assert first.status_code == 202
    assert second.status_code == 202

    rows = (await db_session.execute(select(NewsletterSubscriber))).scalars().all()
    assert len(rows) == 1


async def test_router_contact_submission_returns_201(client, db_session):
    resp = await client.post(
        "/api/v1/contact",
        json={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "subject": "Order question",
            "message": "Where is my order?",
        },
    )
    assert resp.status_code == 201, resp.text

    rows = (await db_session.execute(select(ContactMessage))).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "Ada Lovelace"


class _FakeUser:
    def __init__(self, id: str = "test-user-id", role: str = "customer"):
        self.id = id
        self.role = role


async def test_admin_contact_messages_requires_admin_role(client, db_session):
    async def _fake_customer():
        return _FakeUser(role="customer")

    app.dependency_overrides[get_current_user] = _fake_customer
    try:
        resp = await client.get("/api/v1/admin/contact-messages")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_admin_contact_messages_rejects_manager_role(client, db_session):
    """Per docs/CONTRACTS.md, only admin/super_admin may read the contact
    inbox -- `manager` (which does have some catalog-admin privileges
    elsewhere) is not enough."""

    async def _fake_manager():
        return _FakeUser(role="manager")

    app.dependency_overrides[get_current_user] = _fake_manager
    try:
        resp = await client.get("/api/v1/admin/contact-messages")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_admin_contact_messages_allows_admin_and_paginates(client, db_session):
    for i in range(22):
        await client.post(
            "/api/v1/contact",
            json={
                "name": f"User {i}",
                "email": f"user{i}@example.com",
                "subject": f"Subject {i}",
                "message": f"Message {i}",
            },
        )

    async def _override_admin():
        return _FakeUser(role="admin")

    app.dependency_overrides[require_admin] = _override_admin
    try:
        resp = await client.get("/api/v1/admin/contact-messages")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 22
        assert len(body["items"]) == 20
        # newest first
        assert body["items"][0]["subject"] == "Subject 21"

        page_2 = await client.get("/api/v1/admin/contact-messages", params={"page": 2})
        assert len(page_2.json()["items"]) == 2
    finally:
        app.dependency_overrides.pop(require_admin, None)
