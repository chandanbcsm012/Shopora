"""Tests for the audit module: `log_action` service function plus the
`GET /audit-logs` router (admin/super_admin only), following the same
temporary-mount pattern as media/catalog tests (the router isn't wired
into app/main.py yet -- that's the Main Coordinator's job).
"""
from __future__ import annotations

import pytest

from app.main import app
from app.modules.audit import service
from app.modules.audit.router import require_admin, router

pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", None) == "/api/v1/audit-logs" for r in app.routes):
    app.include_router(router, prefix="/api/v1")


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


async def test_log_action_persists_entry(db_session):
    await service.log_action(
        db_session,
        actor_user_id="user-1",
        action="user.role_changed",
        resource_type="user",
        resource_id="user-2",
        ip_address="127.0.0.1",
        user_agent="pytest",
        before={"role": "customer"},
        after={"role": "admin"},
    )

    items, total = await service.list_audit_logs(db_session, _params())
    assert total == 1
    assert items[0].action == "user.role_changed"
    assert items[0].before_state == {"role": "customer"}
    assert items[0].after_state == {"role": "admin"}
    assert items[0].actor_user_id == "user-1"


def _params():
    from app.shared.pagination import PageParams

    return PageParams(page=1, page_size=20)


async def test_list_audit_logs_endpoint_requires_admin(client):
    app.dependency_overrides.pop(require_admin, None)
    from app.modules.auth.dependencies import get_current_user

    class _Customer:
        id = "customer-under-test"
        role = "customer"

    async def _override_current_user():
        return _Customer()

    app.dependency_overrides[get_current_user] = _override_current_user
    try:
        resp = await client.get("/api/v1/audit-logs")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[require_admin] = _override_admin


async def test_list_audit_logs_endpoint_paginated_and_filterable(client, db_session):
    await service.log_action(
        db_session, actor_user_id="u1", action="user.invited", resource_type="user", resource_id="u2"
    )
    await service.log_action(
        db_session,
        actor_user_id="u1",
        action="user.role_changed",
        resource_type="user",
        resource_id="u3",
    )

    resp = await client.get("/api/v1/audit-logs")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    # newest-first
    assert body["items"][0]["action"] == "user.role_changed"

    filtered = await client.get("/api/v1/audit-logs", params={"action": "user.invited"})
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["action"] == "user.invited"

    by_resource = await client.get("/api/v1/audit-logs", params={"resource_type": "user"})
    assert by_resource.json()["total"] == 2

    by_actor = await client.get("/api/v1/audit-logs", params={"actor_user_id": "u1"})
    assert by_actor.json()["total"] == 2
