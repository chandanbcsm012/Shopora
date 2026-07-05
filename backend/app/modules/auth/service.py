from __future__ import annotations

import secrets
from datetime import timedelta, timezone

from fastapi import status
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.modules.audit import service as audit_service
from app.modules.auth.models import Invitation, PasswordResetToken, RefreshToken, User
from app.modules.auth.schemas import BootstrapRequest, InvitationPreview, TokenPair, UserCreate
from app.shared.base_model import utcnow
from app.shared.error_codes import ErrorCode
from app.shared.pagination import PageParams


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    existing = await get_user_by_email(db, data.email)
    if existing is not None:
        raise AppError(
            ErrorCode.EMAIL_ALREADY_REGISTERED,
            "A user with this email is already registered.",
            409,
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role="customer",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AppError(
            ErrorCode.INVALID_CREDENTIALS,
            "Invalid email or password.",
            401,
        )
    if not user.is_active:
        raise AppError(
            ErrorCode.INVALID_CREDENTIALS,
            "Invalid email or password.",
            401,
        )
    return user


async def issue_token_pair(db: AsyncSession, user: User) -> TokenPair:
    access_token = create_access_token(user_id=user.id, role=user.role)

    raw_refresh_token = generate_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_token)
    await db.commit()

    return TokenPair(access_token=access_token, refresh_token=raw_refresh_token)


async def _get_valid_refresh_token(db: AsyncSession, raw_refresh_token: str) -> RefreshToken:
    # Refresh tokens are opaque and hashed deterministically, so look up
    # candidates and verify with a constant-time comparison.
    token_hash = hash_refresh_token(raw_refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token_row = result.scalar_one_or_none()

    invalid = AppError(
        ErrorCode.INVALID_REFRESH_TOKEN,
        "Refresh token is invalid, expired, or revoked.",
        401,
    )

    if token_row is None or not verify_refresh_token(raw_refresh_token, token_row.token_hash):
        raise invalid
    if token_row.revoked_at is not None:
        raise invalid

    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        # sqlite (used in tests) doesn't round-trip tzinfo on DateTime
        # columns, so treat naive values as UTC (which is what we always
        # write) rather than letting the comparison raise.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utcnow():
        raise invalid

    return token_row


async def rotate_refresh_token(db: AsyncSession, raw_refresh_token: str) -> TokenPair:
    token_row = await _get_valid_refresh_token(db, raw_refresh_token)

    result = await db.execute(select(User).where(User.id == token_row.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppError(
            ErrorCode.INVALID_REFRESH_TOKEN,
            "Refresh token is invalid, expired, or revoked.",
            401,
        )

    token_row.revoked_at = utcnow()
    db.add(token_row)
    await db.commit()

    return await issue_token_pair(db, user)


async def revoke_refresh_token(db: AsyncSession, raw_refresh_token: str) -> None:
    token_hash = hash_refresh_token(raw_refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    token_row = result.scalar_one_or_none()

    if token_row is None or not verify_refresh_token(raw_refresh_token, token_row.token_hash):
        # Logout is idempotent from the client's perspective: an
        # unknown/garbage token still results in "you are logged out".
        return

    if token_row.revoked_at is None:
        token_row.revoked_at = utcnow()
        db.add(token_row)
        await db.commit()


# ---------------------------------------------------------------------------
# Admin panel additions
# ---------------------------------------------------------------------------


async def admin_exists(db: AsyncSession) -> bool:
    # Bootstrap creates a "super_admin" (see bootstrap_admin), so both
    # admin-tier roles must count here — otherwise admin_exists() would
    # report False right after a successful bootstrap and the one-time
    # setup wizard could be run again.
    query = select(exists().where(User.role.in_(["admin", "super_admin"])))
    return bool((await db.execute(query)).scalar())


async def bootstrap_admin(db: AsyncSession, data: BootstrapRequest) -> TokenPair:
    if await admin_exists(db):
        raise AppError(
            ErrorCode.SETUP_ALREADY_COMPLETED,
            "Setup has already been completed; an admin account already exists.",
            status.HTTP_409_CONFLICT,
        )

    existing = await get_user_by_email(db, data.email)
    if existing is not None:
        raise AppError(
            ErrorCode.EMAIL_ALREADY_REGISTERED,
            "A user with this email is already registered.",
            409,
        )

    # The very first account must be able to reach every other role via the
    # invite/role-assignment hierarchy (see _assert_can_assign_role) — an
    # "admin" can only assign manager/customer, which would make
    # "super_admin" permanently unreachable without direct DB access.
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role="super_admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return await issue_token_pair(db, user)


async def list_users(
    db: AsyncSession, params: PageParams, q: str | None = None
) -> tuple[list[User], int]:
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if q:
        pattern = f"%{q.lower()}%"
        clause = or_(func.lower(User.email).like(pattern), func.lower(User.full_name).like(pattern))
        query = query.where(clause)
        count_query = count_query.where(clause)

    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(User.created_at.desc()).offset(params.offset).limit(params.page_size)
    items = list((await db.execute(query)).scalars().all())

    return items, total


async def get_user_or_404(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "User not found",
            status.HTTP_404_NOT_FOUND,
            {"user_id": user_id},
        )
    return user


def _ensure_not_self(current_user: User, user_id: str) -> None:
    if current_user.id == user_id:
        raise AppError(
            ErrorCode.CANNOT_MODIFY_OWN_ACCOUNT,
            "You cannot modify your own account.",
            status.HTTP_400_BAD_REQUEST,
        )


# ---------------------------------------------------------------------------
# User Invitation, Password Reset & Audit Log additions
# ---------------------------------------------------------------------------

# `super_admin > admin > manager > customer`, per docs/CONTRACTS.md's role
# hierarchy section.
_ASSIGNABLE_BY_ADMIN = {"manager", "customer"}


def _assert_can_assign_role(actor: User, target_role: str) -> None:
    """Enforce the role hierarchy in the service layer (not just at the
    route level): `super_admin` may assign any role; `admin` may only
    assign `manager`/`customer`; anyone else shouldn't reach this code
    (route-level `require_role` already blocks `manager`/`customer` from
    the invite/role-update endpoints)."""

    if actor.role == "super_admin":
        return
    if actor.role == "admin" and target_role in _ASSIGNABLE_BY_ADMIN:
        return
    raise AppError(
        ErrorCode.INSUFFICIENT_ROLE_PRIVILEGE,
        f"Role '{actor.role}' is not permitted to assign role '{target_role}'.",
        status.HTTP_403_FORBIDDEN,
    )


async def update_user_role(
    db: AsyncSession,
    current_user: User,
    user_id: str,
    role: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    _ensure_not_self(current_user, user_id)
    user = await get_user_or_404(db, user_id)
    _assert_can_assign_role(current_user, role)
    old_role = user.role
    user.role = role
    await db.commit()
    await db.refresh(user)

    await audit_service.log_action(
        db,
        actor_user_id=current_user.id,
        action="user.role_changed",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        before={"role": old_role},
        after={"role": role},
    )
    return user


async def update_user_status(
    db: AsyncSession,
    current_user: User,
    user_id: str,
    is_active: bool,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User:
    _ensure_not_self(current_user, user_id)
    user = await get_user_or_404(db, user_id)
    old_status = user.is_active
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)

    await audit_service.log_action(
        db,
        actor_user_id=current_user.id,
        action="user.status_changed",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        before={"is_active": old_status},
        after={"is_active": is_active},
    )
    return user


async def invite_user(
    db: AsyncSession,
    *,
    actor: User,
    email: str,
    full_name: str,
    role: str,
    notes: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[Invitation, str]:
    _assert_can_assign_role(actor, role)

    existing = await get_user_by_email(db, email)
    if existing is not None:
        raise AppError(
            ErrorCode.EMAIL_ALREADY_REGISTERED,
            "A user with this email is already registered.",
            409,
        )

    # An inactive user with an unusable, never-logged/returned random
    # password placeholder. `authenticate_user` already rejects inactive
    # users, so this is belt-and-suspenders, not the primary safeguard.
    user = User(
        email=email,
        hashed_password=hash_password(secrets.token_urlsafe(32)),
        full_name=full_name,
        role=role,
        is_active=False,
    )
    db.add(user)

    raw_token = generate_refresh_token()
    invitation = Invitation(
        email=email,
        full_name=full_name,
        role=role,
        notes=notes,
        invited_by_user_id=actor.id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=utcnow() + timedelta(hours=settings.invitation_token_expire_hours),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    await db.refresh(user)

    await audit_service.log_action(
        db,
        actor_user_id=actor.id,
        action="user.invited",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        after={"email": email, "role": role},
    )

    return invitation, raw_token


async def _get_invitation_or_error(db: AsyncSession, raw_token: str) -> Invitation:
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(select(Invitation).where(Invitation.token_hash == token_hash))
    invitation = result.scalar_one_or_none()

    if invitation is None or not verify_refresh_token(raw_token, invitation.token_hash):
        raise AppError(
            ErrorCode.INVITATION_INVALID,
            "Invitation is invalid.",
            status.HTTP_404_NOT_FOUND,
        )

    if invitation.accepted_at is not None:
        raise AppError(
            ErrorCode.INVITATION_ALREADY_ACCEPTED,
            "This invitation has already been accepted.",
            status.HTTP_409_CONFLICT,
        )

    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        # sqlite (used in tests) doesn't round-trip tzinfo on DateTime
        # columns, so treat naive values as UTC (which is what we always
        # write) rather than letting the comparison raise.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utcnow():
        raise AppError(
            ErrorCode.INVITATION_EXPIRED,
            "This invitation has expired.",
            status.HTTP_410_GONE,
        )

    return invitation


async def get_invitation_preview(db: AsyncSession, raw_token: str) -> InvitationPreview:
    invitation = await _get_invitation_or_error(db, raw_token)
    return InvitationPreview(
        email=invitation.email,
        full_name=invitation.full_name,
        role=invitation.role,
        expires_at=invitation.expires_at,
    )


async def accept_invitation(
    db: AsyncSession,
    raw_token: str,
    password: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TokenPair:
    invitation = await _get_invitation_or_error(db, raw_token)

    user = await get_user_by_email(db, invitation.email)
    if user is None:
        # Shouldn't happen: invite_user always creates the user alongside
        # the invitation row. Treat it the same as an invalid token rather
        # than a 500 if it somehow does.
        raise AppError(
            ErrorCode.INVITATION_INVALID,
            "Invitation is invalid.",
            status.HTTP_404_NOT_FOUND,
        )

    user.hashed_password = hash_password(password)
    user.is_active = True
    invitation.accepted_at = utcnow()
    db.add(user)
    db.add(invitation)
    await db.commit()
    await db.refresh(user)

    await audit_service.log_action(
        db,
        actor_user_id=user.id,
        action="user.invitation_accepted",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return await issue_token_pair(db, user)


async def request_password_reset(
    db: AsyncSession,
    email: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str] | None:
    """Returns `(user, raw_token)` if a reset email should be sent, or
    `None` if there's nothing to send (unknown/inactive email, or the
    rate limit has been hit). The caller (router) must always respond 202
    regardless, to avoid leaking either user existence or rate-limit
    state."""

    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None

    since = utcnow() - timedelta(hours=1)
    count_query = (
        select(func.count())
        .select_from(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.created_at >= since)
    )
    count = (await db.execute(count_query)).scalar_one()
    if count >= settings.password_reset_rate_limit_per_hour:
        return None

    raw_token = generate_refresh_token()
    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=utcnow() + timedelta(minutes=settings.password_reset_token_expire_minutes),
    )
    db.add(token_row)
    await db.commit()

    await audit_service.log_action(
        db,
        actor_user_id=user.id,
        action="user.password_reset_requested",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return user, raw_token


async def reset_password(
    db: AsyncSession,
    raw_token: str,
    new_password: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    token_row = result.scalar_one_or_none()

    invalid = AppError(
        ErrorCode.RESET_TOKEN_INVALID,
        "Reset token is invalid or has already been used.",
        status.HTTP_404_NOT_FOUND,
    )

    if token_row is None or not verify_refresh_token(raw_token, token_row.token_hash):
        raise invalid
    if token_row.used_at is not None:
        raise invalid

    expires_at = token_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utcnow():
        raise AppError(
            ErrorCode.RESET_TOKEN_EXPIRED,
            "Reset token has expired.",
            status.HTTP_410_GONE,
        )

    user = await db.get(User, token_row.user_id)
    if user is None:
        raise invalid

    user.hashed_password = hash_password(new_password)
    token_row.used_at = utcnow()
    db.add(user)
    db.add(token_row)

    # Invalidate all existing sessions: bulk-revoke every non-revoked
    # refresh token belonging to this user.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await db.commit()

    await audit_service.log_action(
        db,
        actor_user_id=user.id,
        action="user.password_reset_completed",
        resource_type="user",
        resource_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
