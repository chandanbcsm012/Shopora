"""Media HTTP routes. Mounted at /api/v1/media by the Main Coordinator in
app/main.py (paths here carry no prefix of their own). The Main
Coordinator is also expected to mount `/media` as a StaticFiles directory
serving `media_storage/` so the URLs this module returns are servable."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.modules.auth.dependencies import require_role
from app.modules.auth.models import User

from . import service

router = APIRouter()

# Same role set as catalog's write routes (media uploads exist to back
# product/category images) — resolved once at import time so tests can
# override this exact dependency callable via
# app.dependency_overrides[require_admin] = ...
require_admin = require_role("admin", "super_admin", "manager")


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    _admin: User = Depends(require_admin),
) -> dict:
    url = await service.save_upload(file)
    return {"url": url}
