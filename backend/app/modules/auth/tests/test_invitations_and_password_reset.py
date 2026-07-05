"""Tests for the User Invitation, Password Reset & Audit Log foundation
scope: role-hierarchy enforcement on invite/role-assignment, the full
invitation lifecycle, forgot/reset-password (including rate limiting and
refresh-token invalidation), and audit log entries for role/status
changes.

Follows the same temporary-mount pattern as test_auth.py/test_admin_users.py:
`router`/`admin_router` aren't wired into app/main.py yet, so we mount
them here, guarded against double registration.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.main import app
from app.modules.audit.service import list_audit_logs
from app.modules.auth import service
from app.modules.auth.models import PasswordResetToken, User
from app.modules.auth.router import admin_router
from app.modules.auth.router import router as auth_router
from app.shared.base_model import utcnow
from app.shared.pagination import PageParams

pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", "").startswith("/api/v1/auth") for r in app.routes):
    app.include_router(auth_router, prefix="/api/v1/auth")

if not any(getattr(r, "path", None) == "/api/v1/users" for r in app.routes):
    app.include_router(admin_router, prefix="/api/v1")


DEFAULT_PASSWORD = "correct-horse-battery-staple"


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    db_session, email: str, role: str, password: str = DEFAULT_PASSWORD, is_active: bool = True
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=f"{role.title()} User",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _invite(db_session, actor: User, email: str, role: str = "customer", full_name: str = "Invitee"):
    return await service.invite_user(
        db_session, actor=actor, email=email, full_name=full_name, role=role, notes=None
    )


# ---------------------------------------------------------------------------
# Role hierarchy matrix (POST /api/v1/users/invite)
# ---------------------------------------------------------------------------


async def test_super_admin_can_invite_admin(client, db_session):
    await _create_user(db_session, "root@example.com", "super_admin")
    tokens = await _login(client, "root@example.com")

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": "newadmin@example.com", "full_name": "New Admin", "role": "admin"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "newadmin@example.com"
    assert body["role"] == "admin"
    assert "token" not in body
    assert body["accepted_at"] is None


async def test_super_admin_can_invite_super_admin(client, db_session):
    await _create_user(db_session, "root2@example.com", "super_admin")
    tokens = await _login(client, "root2@example.com")

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": "newsuper@example.com", "full_name": "New Super", "role": "super_admin"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 201, resp.text


async def test_admin_cannot_invite_admin(client, db_session):
    await _create_user(db_session, "admin1@example.com", "admin")
    tokens = await _login(client, "admin1@example.com")

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": "shouldfail@example.com", "full_name": "Nope", "role": "admin"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE_PRIVILEGE"


async def test_admin_cannot_invite_super_admin(client, db_session):
    await _create_user(db_session, "admin1b@example.com", "admin")
    tokens = await _login(client, "admin1b@example.com")

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": "shouldfail2@example.com", "full_name": "Nope", "role": "super_admin"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE_PRIVILEGE"


async def test_admin_can_invite_manager_and_customer(client, db_session):
    await _create_user(db_session, "admin2@example.com", "admin")
    tokens = await _login(client, "admin2@example.com")

    for role in ("manager", "customer"):
        resp = await client.post(
            "/api/v1/users/invite",
            json={"email": f"{role}@example.com", "full_name": role, "role": role},
            headers=_auth_headers(tokens["access_token"]),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["role"] == role


async def test_manager_cannot_access_invite_endpoint(client, db_session):
    await _create_user(db_session, "mgr@example.com", "manager")
    tokens = await _login(client, "mgr@example.com")

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": "z@example.com", "full_name": "Z", "role": "customer"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"


async def test_customer_cannot_access_invite_endpoint(client, db_session):
    await _create_user(db_session, "cust0@example.com", "customer")
    tokens = await _login(client, "cust0@example.com")

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": "z2@example.com", "full_name": "Z2", "role": "customer"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"


async def test_invite_duplicate_email_returns_409(client, db_session):
    admin = await _create_user(db_session, "admin2b@example.com", "admin")
    tokens = await _login(client, "admin2b@example.com")

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": admin.email, "full_name": "Dupe", "role": "customer"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_role_hierarchy_also_enforced_on_patch_role(client, db_session):
    admin = await _create_user(db_session, "admin2c@example.com", "admin")
    tokens = await _login(client, "admin2c@example.com")
    customer = await _create_user(db_session, "cust2c@example.com", "customer")

    resp = await client.patch(
        f"/api/v1/users/{customer.id}/role",
        json={"role": "admin"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE_PRIVILEGE"


# ---------------------------------------------------------------------------
# Invitation lifecycle
# ---------------------------------------------------------------------------


async def test_invitation_preview_returns_context(client, db_session):
    admin = await _create_user(db_session, "admin3@example.com", "admin")
    invitation, raw_token = await _invite(db_session, admin, "invitee1@example.com", role="manager")

    resp = await client.get(f"/api/v1/auth/invitations/{raw_token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "invitee1@example.com"
    assert body["role"] == "manager"
    assert "token" not in body


async def test_get_invitation_unknown_token_returns_404(client):
    resp = await client.get("/api/v1/auth/invitations/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "INVITATION_INVALID"


async def test_accept_invitation_activates_user_and_allows_login(client, db_session):
    admin = await _create_user(db_session, "admin4@example.com", "admin")
    invitation, raw_token = await _invite(db_session, admin, "invitee2@example.com")

    # Inactive/invited user cannot log in yet.
    pre_login = await client.post(
        "/api/v1/auth/login", json={"email": "invitee2@example.com", "password": "whatever"}
    )
    assert pre_login.status_code == 401

    accept_resp = await client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw_token, "password": "brand-new-password-1"},
    )
    assert accept_resp.status_code == 201, accept_resp.text
    body = accept_resp.json()
    assert body["access_token"]
    assert body["refresh_token"]

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "invitee2@example.com", "password": "brand-new-password-1"},
    )
    assert login_resp.status_code == 200


async def test_accept_invitation_already_accepted_returns_409(client, db_session):
    admin = await _create_user(db_session, "admin5@example.com", "admin")
    invitation, raw_token = await _invite(db_session, admin, "invitee3@example.com")

    first = await client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw_token, "password": "brand-new-password-1"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw_token, "password": "another-password-2"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "INVITATION_ALREADY_ACCEPTED"


async def test_get_invitation_already_accepted_returns_409(client, db_session):
    admin = await _create_user(db_session, "admin5b@example.com", "admin")
    invitation, raw_token = await _invite(db_session, admin, "invitee3b@example.com")

    await client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw_token, "password": "brand-new-password-1"},
    )

    resp = await client.get(f"/api/v1/auth/invitations/{raw_token}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVITATION_ALREADY_ACCEPTED"


async def test_get_invitation_expired_returns_410(client, db_session):
    admin = await _create_user(db_session, "admin6@example.com", "admin")
    invitation, raw_token = await _invite(db_session, admin, "invitee4@example.com")

    invitation.expires_at = utcnow() - timedelta(hours=1)
    db_session.add(invitation)
    await db_session.commit()

    resp = await client.get(f"/api/v1/auth/invitations/{raw_token}")
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "INVITATION_EXPIRED"


async def test_accept_invitation_expired_returns_410(client, db_session):
    admin = await _create_user(db_session, "admin7@example.com", "admin")
    invitation, raw_token = await _invite(db_session, admin, "invitee5@example.com")

    invitation.expires_at = utcnow() - timedelta(hours=1)
    db_session.add(invitation)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw_token, "password": "brand-new-password-1"},
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "INVITATION_EXPIRED"


async def test_invite_schedules_invitation_email(client, db_session, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.modules.auth.router.send_email",
        lambda to, subject, html_body: calls.append((to, subject, html_body)),
    )

    await _create_user(db_session, "admin8@example.com", "admin")
    tokens = await _login(client, "admin8@example.com")

    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": "invitee6@example.com", "full_name": "Invitee Six", "role": "customer"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    assert len(calls) == 1
    to, subject, html_body = calls[0]
    assert to == "invitee6@example.com"
    assert "accept-invitation" in html_body


async def test_role_changed_and_invitation_accepted_create_audit_logs(client, db_session):
    admin = await _create_user(db_session, "admin9@example.com", "admin")
    invitation, raw_token = await _invite(db_session, admin, "invitee7@example.com", role="manager")

    await client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw_token, "password": "brand-new-password-1"},
    )

    items, total = await list_audit_logs(
        db_session, PageParams(page=1, page_size=20), action="user.invitation_accepted"
    )
    assert total == 1
    assert items[0].resource_type == "user"

    invited_items, invited_total = await list_audit_logs(
        db_session, PageParams(page=1, page_size=20), action="user.invited"
    )
    assert invited_total == 1
    assert invited_items[0].actor_user_id == admin.id


# ---------------------------------------------------------------------------
# forgot-password / reset-password
# ---------------------------------------------------------------------------


async def test_forgot_password_always_returns_202_regardless_of_email_existing(client, db_session):
    await _create_user(db_session, "known1@example.com", "customer")

    known_resp = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "known1@example.com"}
    )
    assert known_resp.status_code == 202

    unknown_resp = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody-here@example.com"}
    )
    assert unknown_resp.status_code == 202


async def test_forgot_password_only_schedules_email_for_known_active_user(
    client, db_session, monkeypatch
):
    await _create_user(db_session, "known2@example.com", "customer")
    await _create_user(db_session, "inactive1@example.com", "customer", is_active=False)

    calls = []
    monkeypatch.setattr(
        "app.modules.auth.router.send_email",
        lambda to, subject, html_body: calls.append(to),
    )

    await client.post("/api/v1/auth/forgot-password", json={"email": "known2@example.com"})
    await client.post("/api/v1/auth/forgot-password", json={"email": "nobody-else@example.com"})
    await client.post("/api/v1/auth/forgot-password", json={"email": "inactive1@example.com"})

    assert calls == ["known2@example.com"]


async def test_forgot_password_rate_limits_silently(client, db_session, monkeypatch):
    await _create_user(db_session, "ratelimited@example.com", "customer")

    calls = []
    monkeypatch.setattr(
        "app.modules.auth.router.send_email",
        lambda to, subject, html_body: calls.append(to),
    )

    limit = settings.password_reset_rate_limit_per_hour
    for _ in range(limit):
        resp = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "ratelimited@example.com"}
        )
        assert resp.status_code == 202
    assert len(calls) == limit

    # One more request beyond the limit must still return 202 (no leaked
    # rate-limit state) but must not schedule another email.
    over_limit_resp = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "ratelimited@example.com"}
    )
    assert over_limit_resp.status_code == 202
    assert len(calls) == limit


async def test_reset_password_updates_password_and_revokes_refresh_tokens(client, db_session):
    await _create_user(db_session, "resetme@example.com", "customer", password="old-password-123")

    login_resp = await _login(client, "resetme@example.com", password="old-password-123")
    old_refresh_token = login_resp["refresh_token"]

    result = await service.request_password_reset(db_session, "resetme@example.com")
    assert result is not None
    _user, raw_token = result

    reset_resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "brand-new-password-2"},
    )
    assert reset_resp.status_code == 204

    # Old refresh token must be revoked (existing sessions invalidated).
    refresh_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
    )
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    # Old password no longer works, new one does.
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "resetme@example.com", "password": "old-password-123"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "resetme@example.com", "password": "brand-new-password-2"},
    )
    assert new_login.status_code == 200

    items, total = await list_audit_logs(
        db_session, PageParams(page=1, page_size=20), action="user.password_reset_completed"
    )
    assert total == 1


async def test_reset_password_unknown_token_returns_404(client):
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "whatever-12345"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESET_TOKEN_INVALID"


async def test_reset_password_used_token_returns_404(client, db_session):
    await _create_user(db_session, "usedreset@example.com", "customer")
    result = await service.request_password_reset(db_session, "usedreset@example.com")
    assert result is not None
    _user, raw_token = result

    first = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "first-new-password-1"},
    )
    assert first.status_code == 204

    second = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "second-new-password-2"},
    )
    assert second.status_code == 404
    assert second.json()["error"]["code"] == "RESET_TOKEN_INVALID"


async def test_reset_password_expired_token_returns_410(client, db_session):
    user = await _create_user(db_session, "expiredreset@example.com", "customer")
    result = await service.request_password_reset(db_session, "expiredreset@example.com")
    assert result is not None
    _user, raw_token = result

    row = (
        await db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
    ).scalar_one()
    row.expires_at = utcnow() - timedelta(minutes=1)
    db_session.add(row)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "whatever-12345"},
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "RESET_TOKEN_EXPIRED"


# ---------------------------------------------------------------------------
# Audit log for role/status changes
# ---------------------------------------------------------------------------


async def test_role_change_creates_audit_log_with_before_after(client, db_session):
    admin = await _create_user(db_session, "admin10@example.com", "admin")
    tokens = await _login(client, "admin10@example.com")
    customer = await _create_user(db_session, "cust10@example.com", "customer")

    resp = await client.patch(
        f"/api/v1/users/{customer.id}/role",
        json={"role": "manager"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 200, resp.text

    items, total = await list_audit_logs(
        db_session, PageParams(page=1, page_size=20), action="user.role_changed"
    )
    assert total == 1
    assert items[0].before_state == {"role": "customer"}
    assert items[0].after_state == {"role": "manager"}
    assert items[0].actor_user_id == admin.id
    assert items[0].resource_id == customer.id


async def test_status_change_creates_audit_log_with_before_after(client, db_session):
    admin = await _create_user(db_session, "admin11@example.com", "admin")
    tokens = await _login(client, "admin11@example.com")
    customer = await _create_user(db_session, "cust11@example.com", "customer")

    resp = await client.patch(
        f"/api/v1/users/{customer.id}/status",
        json={"is_active": False},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert resp.status_code == 200, resp.text

    items, total = await list_audit_logs(
        db_session, PageParams(page=1, page_size=20), action="user.status_changed"
    )
    assert total == 1
    assert items[0].before_state == {"is_active": True}
    assert items[0].after_state == {"is_active": False}
    assert items[0].actor_user_id == admin.id
