"""Tests for the admin-panel additions to the auth module: bootstrap
(public, self-limiting) and /users management (admin only).

Follows the same mounting pattern as test_auth.py: the auth `router` (for
bootstrap-status/bootstrap, same /api/v1/auth prefix) and the new
`admin_router` (for /users*, plain /api/v1 prefix) aren't wired into
app/main.py yet -- that's the Main Coordinator's job -- so we mount them
here temporarily, guarded against double registration.
"""

from app.main import app
from app.modules.auth.router import admin_router
from app.modules.auth.router import router as auth_router

pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", "").startswith("/api/v1/auth") for r in app.routes):
    app.include_router(auth_router, prefix="/api/v1/auth")

if not any(getattr(r, "path", None) == "/api/v1/users" for r in app.routes):
    app.include_router(admin_router, prefix="/api/v1")


ADMIN_PAYLOAD = {
    "email": "root@example.com",
    "password": "correct-horse-battery-staple",
    "full_name": "Root Admin",
}


async def _bootstrap(client, payload=None):
    return await client.post("/api/v1/auth/bootstrap", json=payload or ADMIN_PAYLOAD)


async def _register_customer(client, email="customer@example.com", full_name="Cust Omer"):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery-staple", "full_name": full_name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client, email, password="correct-horse-battery-staple"):
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# bootstrap-status / bootstrap
# ---------------------------------------------------------------------------


async def test_bootstrap_status_false_when_no_admin(client):
    resp = await client.get("/api/v1/auth/bootstrap-status")
    assert resp.status_code == 200
    assert resp.json() == {"admin_exists": False}


async def test_bootstrap_creates_super_admin_and_returns_token_pair(client):
    resp = await _bootstrap(client)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    status_resp = await client.get("/api/v1/auth/bootstrap-status")
    assert status_resp.json() == {"admin_exists": True}

    me_resp = await client.get("/api/v1/auth/me", headers=_auth_headers(body["access_token"]))
    assert me_resp.status_code == 200
    # Must be super_admin, not plain admin: an "admin" can only ever assign
    # manager/customer (see the role hierarchy), which would make
    # super_admin permanently unreachable without direct DB access if the
    # very first bootstrapped account weren't already at the top rank.
    assert me_resp.json()["role"] == "super_admin"


async def test_bootstrap_twice_returns_409(client):
    first = await _bootstrap(client)
    assert first.status_code == 201

    second = await _bootstrap(client, payload={**ADMIN_PAYLOAD, "email": "other-admin@example.com"})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SETUP_ALREADY_COMPLETED"


async def test_bootstrap_duplicate_email_returns_409(client):
    await _register_customer(client, email=ADMIN_PAYLOAD["email"])

    resp = await _bootstrap(client)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


# ---------------------------------------------------------------------------
# GET /api/v1/users
# ---------------------------------------------------------------------------


async def test_list_users_requires_admin(client):
    await _register_customer(client)
    login = await _login(client, "customer@example.com")

    resp = await client.get("/api/v1/users", headers=_auth_headers(login["access_token"]))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"


async def test_list_users_without_auth_returns_401(client):
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


async def test_list_users_paginated_and_searchable(client):
    admin_tokens = await _bootstrap(client)
    admin_access = admin_tokens.json()["access_token"]

    await _register_customer(client, email="alice@example.com", full_name="Alice Example")
    await _register_customer(client, email="bob@example.com", full_name="Bob Builder")

    resp = await client.get("/api/v1/users", headers=_auth_headers(admin_access))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3  # admin + alice + bob
    assert body["page"] == 1
    assert body["page_size"] == 20

    by_query_email = await client.get(
        "/api/v1/users", params={"q": "alice"}, headers=_auth_headers(admin_access)
    )
    assert by_query_email.json()["total"] == 1
    assert by_query_email.json()["items"][0]["email"] == "alice@example.com"

    by_query_name = await client.get(
        "/api/v1/users", params={"q": "builder"}, headers=_auth_headers(admin_access)
    )
    assert by_query_name.json()["total"] == 1
    assert by_query_name.json()["items"][0]["email"] == "bob@example.com"

    paged = await client.get(
        "/api/v1/users", params={"page": 1, "page_size": 2}, headers=_auth_headers(admin_access)
    )
    assert len(paged.json()["items"]) == 2


# ---------------------------------------------------------------------------
# PATCH /api/v1/users/{id}/role
# ---------------------------------------------------------------------------


async def test_patch_user_role_promotes_to_manager(client):
    # Bootstrap always creates a plain "admin" (never "super_admin"), and
    # per the role hierarchy an "admin" may only assign "manager"/"customer"
    # -- promoting to "admin"/"super_admin" is covered in
    # test_invitations_and_password_reset.py's hierarchy matrix tests.
    admin_tokens = (await _bootstrap(client)).json()
    admin_access = admin_tokens["access_token"]

    customer = await _register_customer(client)

    resp = await client.patch(
        f"/api/v1/users/{customer['id']}/role",
        json={"role": "manager"},
        headers=_auth_headers(admin_access),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "manager"


async def test_patch_user_role_rejects_invalid_role(client):
    admin_tokens = (await _bootstrap(client)).json()
    admin_access = admin_tokens["access_token"]
    customer = await _register_customer(client)

    resp = await client.patch(
        f"/api/v1/users/{customer['id']}/role",
        json={"role": "superuser"},
        headers=_auth_headers(admin_access),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_patch_user_role_cannot_modify_self(client):
    admin_tokens = (await _bootstrap(client)).json()
    admin_access = admin_tokens["access_token"]
    me = await client.get("/api/v1/auth/me", headers=_auth_headers(admin_access))
    admin_id = me.json()["id"]

    resp = await client.patch(
        f"/api/v1/users/{admin_id}/role",
        json={"role": "customer"},
        headers=_auth_headers(admin_access),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CANNOT_MODIFY_OWN_ACCOUNT"


async def test_patch_user_role_missing_user_404(client):
    admin_tokens = (await _bootstrap(client)).json()
    admin_access = admin_tokens["access_token"]

    resp = await client.patch(
        "/api/v1/users/does-not-exist/role",
        json={"role": "admin"},
        headers=_auth_headers(admin_access),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# PATCH /api/v1/users/{id}/status
# ---------------------------------------------------------------------------


async def test_patch_user_status_deactivates_user(client):
    admin_tokens = (await _bootstrap(client)).json()
    admin_access = admin_tokens["access_token"]
    customer = await _register_customer(client)

    resp = await client.patch(
        f"/api/v1/users/{customer['id']}/status",
        json={"is_active": False},
        headers=_auth_headers(admin_access),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": customer["email"], "password": "correct-horse-battery-staple"},
    )
    assert login_resp.status_code == 401


async def test_patch_user_status_cannot_modify_self(client):
    admin_tokens = (await _bootstrap(client)).json()
    admin_access = admin_tokens["access_token"]
    me = await client.get("/api/v1/auth/me", headers=_auth_headers(admin_access))
    admin_id = me.json()["id"]

    resp = await client.patch(
        f"/api/v1/users/{admin_id}/status",
        json={"is_active": False},
        headers=_auth_headers(admin_access),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CANNOT_MODIFY_OWN_ACCOUNT"


async def test_patch_user_status_missing_user_404(client):
    admin_tokens = (await _bootstrap(client)).json()
    admin_access = admin_tokens["access_token"]

    resp = await client.patch(
        "/api/v1/users/does-not-exist/status",
        json={"is_active": False},
        headers=_auth_headers(admin_access),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_patch_user_status_requires_admin(client):
    customer = await _register_customer(client)
    login = await _login(client, customer["email"])

    resp = await client.patch(
        f"/api/v1/users/{customer['id']}/status",
        json={"is_active": False},
        headers=_auth_headers(login["access_token"]),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"
