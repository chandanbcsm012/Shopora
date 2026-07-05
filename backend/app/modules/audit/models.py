# audit.AuditLog — id, actor_user_id (FK users, nullable), action,
# resource_type, resource_id (nullable), ip_address (nullable),
# user_agent (nullable), before_state (JSON, nullable), after_state
# (JSON, nullable), created_at (per docs/CONTRACTS.md).
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, UUIDPKMixin, utcnow


class AuditLog(UUIDPKMixin, Base):
    """audit.AuditLog — append-only audit trail of admin actions. No
    `updated_at`: audit rows are immutable, the same reasoning
    `auth.RefreshToken` uses for skipping `TimestampMixin`."""

    __tablename__ = "audit_logs"

    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
