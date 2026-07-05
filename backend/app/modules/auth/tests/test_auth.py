"""API-level tests for the auth router, using the shared `client` fixture
from backend/tests/conftest.py (real FastAPI app + in-memory sqlite).

The auth router isn't mounted in app/main.py yet -- that's the Main
Coordinator's job at integration time -- so we mount it here, temporarily,
guarded so re-running/importing this module twice in the same session
doesn't double-register the routes.
"""

from app.main import app
from app.modules.auth.router import router as auth_router

# The shared `client`/`db_session` fixtures live in backend/tests/conftest.py,
# which is not an ancestor directory of this test module, so pytest won't
# auto-discover it -- register it explicitly as a plugin instead.
pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", "").startswith("/api/v1/auth") for r in app.routes):
    app.include_router(auth_router, prefix="/api/v1/auth")


REGISTER_PAYLOAD = {
    "email": "alice@example.com",
    "password": "correct-horse-battery-staple",
    "full_name": "Alice Example",
}


async def _register(client, payload=None):
    return await client.post("/api/v1/auth/register", json=payload or REGISTER_PAYLOAD)


async def _login(client, email=None, password=None):
    return await client.post(
        "/api/v1/auth/login",
        json={
            "email": email or REGISTER_PAYLOAD["email"],
            "password": password or REGISTER_PAYLOAD["password"],
        },
    )


async def test_register_returns_user_without_password(client):
    resp = await _register(client)

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert body["full_name"] == REGISTER_PAYLOAD["full_name"]
    assert body["role"] == "customer"
    assert body["is_active"] is True
    assert "id" in body
    assert "created_at" in body
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_duplicate_email_returns_409(client):
    first = await _register(client)
    assert first.status_code == 201

    second = await _register(client)
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_login_success_returns_token_pair(client):
    await _register(client)

    resp = await _login(client)

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_wrong_password_returns_401(client):
    await _register(client)

    resp = await _login(client, password="totally-wrong-password")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_unknown_email_returns_401(client):
    resp = await _login(client, email="nobody@example.com")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_refresh_rotates_token_and_invalidates_old_one(client):
    await _register(client)
    login_resp = await _login(client)
    old_refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert refresh_resp.status_code == 200
    new_body = refresh_resp.json()
    assert new_body["access_token"]
    assert new_body["refresh_token"]
    assert new_body["refresh_token"] != old_refresh_token

    # Reusing the now-rotated (revoked) refresh token must fail.
    reuse_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # The newly issued refresh token still works.
    new_refresh_token = new_body["refresh_token"]
    second_refresh_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_refresh_token}
    )
    assert second_refresh_resp.status_code == 200


async def test_refresh_with_garbage_token_returns_401(client):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_logout_revokes_refresh_token(client):
    await _register(client)
    login_resp = await _login(client)
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": refresh_token}
    )
    assert logout_resp.status_code == 204

    reuse_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_logout_with_unknown_token_is_idempotent(client):
    resp = await client.post("/api/v1/auth/logout", json={"refresh_token": "does-not-exist"})

    assert resp.status_code == 204


async def test_me_with_valid_token_returns_current_user(client):
    await _register(client)
    login_resp = await _login(client)
    access_token = login_resp.json()["access_token"]

    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]


async def test_me_without_token_returns_401(client):
    resp = await client.get("/api/v1/auth/me")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


async def test_me_with_invalid_token_returns_401(client):
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"}
    )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
