"""Audit HTTP routes. Mounted at /api/v1 by the Main Coordinator in
app/main.py (path here is `/audit-logs`, carrying no prefix of its own)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_role
from app.shared.pagination import Page, PageParams

from . import service
from .schemas import AuditLogOut

router = APIRouter()

# Resolved once at import time so tests can override this exact dependency
# callable via app.dependency_overrides[require_admin] = ...
require_admin = require_role("admin", "super_admin")


@router.get("/audit-logs", response_model=Page[AuditLogOut])
async def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> Page[AuditLogOut]:
    params = PageParams(page=page, page_size=page_size)
    items, total = await service.list_audit_logs(
        db,
        params,
        action=action,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
    )
    return Page[AuditLogOut](
        items=[AuditLogOut.model_validate(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
