# Owned by the Database Team. Define the User and RefreshToken
# SQLAlchemy models here per docs/CONTRACTS.md.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin, UUIDPKMixin, utcnow


class User(UUIDPKMixin, TimestampMixin, Base):
    """auth.User — id, email (unique), hashed_password, full_name, role,
    is_active, created_at, updated_at (per docs/CONTRACTS.md)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="customer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(UUIDPKMixin, Base):
    """auth.RefreshToken — id, user_id (FK users), token_hash, expires_at,
    revoked_at (nullable), created_at (per docs/CONTRACTS.md; note: no
    updated_at on this table, so TimestampMixin is intentionally not used)."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class Invitation(UUIDPKMixin, Base):
    """auth.Invitation — id, email, full_name, role, notes (nullable),
    invited_by_user_id (FK users), token_hash, expires_at, accepted_at
    (nullable), created_at (per docs/CONTRACTS.md; no updated_at, same
    reasoning as RefreshToken)."""

    __tablename__ = "invitations"

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    invited_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class PasswordResetToken(UUIDPKMixin, Base):
    """auth.PasswordResetToken — id, user_id (FK users), token_hash,
    expires_at, used_at (nullable), created_at (per docs/CONTRACTS.md; no
    updated_at, same reasoning as RefreshToken)."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
