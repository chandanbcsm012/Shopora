"""Business logic for the site module: newsletter subscription, contact
form submission, and the admin contact-message inbox, per
docs/CONTRACTS.md."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.pagination import PageParams

from .models import ContactMessage, NewsletterSubscriber


async def subscribe_to_newsletter(db: AsyncSession, email: str) -> None:
    """Always succeeds from the caller's perspective, no exception either
    way — the router always responds 202 regardless of whether the email
    was already subscribed (no enumeration leak, the same philosophy
    `auth.service.request_password_reset` already uses for
    forgot-password). Checks first via `select` rather than relying on
    catching an IntegrityError, matching the query-then-act style used
    elsewhere in this codebase (e.g. `catalog.service._ensure_unique_slug`,
    `wishlist.service.add_to_wishlist`)."""
    existing = (
        await db.execute(select(NewsletterSubscriber.id).where(NewsletterSubscriber.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        return

    db.add(NewsletterSubscriber(email=email))
    await db.commit()


async def submit_contact_message(
    db: AsyncSession, name: str, email: str, subject: str, message: str
) -> ContactMessage:
    contact_message = ContactMessage(name=name, email=email, subject=subject, message=message)
    db.add(contact_message)
    await db.commit()
    await db.refresh(contact_message)
    return contact_message


async def list_contact_messages(
    db: AsyncSession, params: PageParams
) -> tuple[list[ContactMessage], int]:
    """Newest first, per docs/CONTRACTS.md."""
    count_query = select(func.count()).select_from(ContactMessage)
    total = (await db.execute(count_query)).scalar_one()

    query = (
        select(ContactMessage)
        .order_by(ContactMessage.created_at.desc())
        .offset(params.offset)
        .limit(params.page_size)
    )
    items = list((await db.execute(query)).scalars().all())

    return items, total
