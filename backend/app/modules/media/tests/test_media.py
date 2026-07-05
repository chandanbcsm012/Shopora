"""Tests for the media module: validated image upload (admin only).

Follows the same pattern as catalog/auth tests: `app.modules.media.router`
isn't wired into app/main.py yet (that's the Main Coordinator's job, along
with the `/media` StaticFiles mount), so we mount it here temporarily,
guarded against double registration, and drive it through the real
FastAPI app + HTTP client.
"""
from __future__ import annotations

import shutil

import pytest

from app.main import app
from app.modules.media import service
from app.modules.media.router import require_admin, router

pytest_plugins = ["tests.conftest"]

if not any(getattr(r, "path", None) == "/api/v1/media/upload" for r in app.routes):
    app.include_router(router, prefix="/api/v1/media")


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


@pytest.fixture(autouse=True)
def _isolated_media_dir(tmp_path, monkeypatch):
    """Redirect uploads to a per-test tmp dir so tests don't pollute (or
    depend on) the real backend/media_storage/ directory."""
    monkeypatch.setattr(service, "MEDIA_STORAGE_DIR", tmp_path)
    yield
    shutil.rmtree(tmp_path, ignore_errors=True)


# A minimal valid-enough JPEG/PNG byte sequence -- content is never
# actually decoded as an image by this module, only the declared
# content-type and byte size are validated.
TINY_JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 100 + b"\xff\xd9"
TINY_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 100


async def test_upload_jpeg_succeeds_and_file_exists(client):
    resp = await client.post(
        "/api/v1/media/upload",
        files={"file": ("photo.jpg", TINY_JPEG_BYTES, "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["url"].startswith("/media/")
    assert body["url"].endswith(".jpg")

    filename = body["url"].removeprefix("/media/")
    saved_path = service.MEDIA_STORAGE_DIR / filename
    assert saved_path.exists()
    assert saved_path.read_bytes() == TINY_JPEG_BYTES


async def test_upload_png_succeeds(client):
    resp = await client.post(
        "/api/v1/media/upload",
        files={"file": ("photo.png", TINY_PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"].endswith(".png")


async def test_upload_rejects_unsupported_content_type(client):
    resp = await client.post(
        "/api/v1/media/upload",
        files={"file": ("doc.pdf", b"%PDF-1.4 ...", "application/pdf")},
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


async def test_upload_rejects_oversized_file(client):
    oversized = b"0" * (5 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/media/upload",
        files={"file": ("big.jpg", oversized, "image/jpeg")},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_upload_at_exactly_max_size_succeeds(client):
    exactly_max = b"0" * (5 * 1024 * 1024)
    resp = await client.post(
        "/api/v1/media/upload",
        files={"file": ("max.jpg", exactly_max, "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text


async def test_upload_without_auth_returns_401(client):
    app.dependency_overrides.pop(require_admin, None)
    try:
        resp = await client.post(
            "/api/v1/media/upload",
            files={"file": ("photo.jpg", TINY_JPEG_BYTES, "image/jpeg")},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    finally:
        app.dependency_overrides[require_admin] = _override_admin


async def test_upload_requires_admin_role_not_just_authentication(client):
    from app.modules.auth.dependencies import get_current_user

    class _Customer:
        id = "customer-under-test"
        role = "customer"

    async def _override_current_user():
        return _Customer()

    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides[get_current_user] = _override_current_user
    try:
        resp = await client.post(
            "/api/v1/media/upload",
            files={"file": ("photo.jpg", TINY_JPEG_BYTES, "image/jpeg")},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[require_admin] = _override_admin
