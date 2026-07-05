"""HTTP routes for the site module (newsletter/contact forms + admin contact
inbox), per docs/CONTRACTS.md. Mounted by the Main Coordinator at
`/api/v1` (paths here carry no prefix of their own).

`router` holds the public newsletter/contact endpoints. `admin_router`
holds the admin-only contact-message inbox — mirrors the exact
`router`/`admin_router` split style already used in `auth`/`orders`/
`catalog`."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_role
from app.shared.pagination import Page, PageParams

from . import service
from .schemas import ContactMessageCreate, ContactMessageOut, NewsletterSubscribeRequest

router = APIRouter()


@router.post("/newsletter/subscribe", status_code=status.HTTP_202_ACCEPTED)
async def subscribe_to_newsletter(
    data: NewsletterSubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    # Always 202 regardless of outcome -- no enumeration leak, whether or
    # not this email was already subscribed.
    await service.subscribe_to_newsletter(db, data.email)


@router.post("/contact", status_code=status.HTTP_201_CREATED)
async def submit_contact_message(
    data: ContactMessageCreate,
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.submit_contact_message(db, data.name, data.email, data.subject, data.message)


# ---------------------------------------------------------------------------
# Admin-only contact-message inbox.
# ---------------------------------------------------------------------------
admin_router = APIRouter()

# Resolved once at import time so tests can override this exact dependency
# callable via app.dependency_overrides[require_admin] = ...
require_admin = require_role("admin", "super_admin")


@admin_router.get("/admin/contact-messages", response_model=Page[ContactMessageOut])
async def admin_list_contact_messages(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
) -> Page[ContactMessageOut]:
    params = PageParams(page=page, page_size=page_size)
    items, total = await service.list_contact_messages(db, params)
    return Page[ContactMessageOut](
        items=[ContactMessageOut.model_validate(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
