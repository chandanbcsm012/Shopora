"""Business logic for the audit module: append-only logging of admin
actions, plus the paginated/filterable read path used by the router. This
is infrastructure other modules call directly (like `media`/`email`), not
a business-domain module other modules must avoid touching.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.shared.pagination import PageParams


async def log_action(
    db: AsyncSession,
    *,
    actor_user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        before_state=before,
        after_state=after,
    )
    db.add(entry)
    await db.commit()


async def list_audit_logs(
    db: AsyncSession,
    params: PageParams,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: str | None = None,
) -> tuple[list[AuditLog], int]:
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    if actor_user_id:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
        count_query = count_query.where(AuditLog.actor_user_id == actor_user_id)

    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(AuditLog.created_at.desc()).offset(params.offset).limit(params.page_size)
    items = list((await db.execute(query)).scalars().all())

    return items, total
