# Owned by the `site` module. Defines the NewsletterSubscriber and
# ContactMessage SQLAlchemy models per docs/CONTRACTS.md's "Storefront:
# Homepage, Filtering, Wishlist & Static Pages (foundation scope)" section.
# Neither table references another module's table (no FKs here), so there's
# no cross-module boundary concern for these two models.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, UUIDPKMixin, utcnow


class NewsletterSubscriber(UUIDPKMixin, Base):
    """site.NewsletterSubscriber — id, email (unique), created_at, per
    docs/CONTRACTS.md. No `updated_at` — a subscription row never changes
    after creation."""

    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ContactMessage(UUIDPKMixin, Base):
    """site.ContactMessage — id, name, email, subject, message, created_at,
    per docs/CONTRACTS.md. No `updated_at` — a submitted message is never
    edited after the fact."""

    __tablename__ = "contact_messages"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(5000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
