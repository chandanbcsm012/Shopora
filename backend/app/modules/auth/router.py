from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user, require_role
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    AcceptInvitationRequest,
    BootstrapRequest,
    BootstrapStatus,
    ForgotPasswordRequest,
    InvitationOut,
    InvitationPreview,
    InviteUserRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    UserCreate,
    UserOut,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.modules.email.service import send_email
from app.modules.email.templates import invitation_email, password_reset_email
from app.shared.base_model import utcnow
from app.shared.pagination import Page, PageParams

# `router` is mounted by the Main Coordinator at /api/v1/auth (register,
# login, refresh, logout, me, bootstrap-status, bootstrap, invitations,
# accept-invitation, forgot-password, reset-password).
router = APIRouter()

# `admin_router` holds the /users* admin endpoints, which are NOT under
# /auth per docs/CONTRACTS.md (`GET /api/v1/users`, not
# `GET /api/v1/auth/users`). The Main Coordinator should mount this at
# plain /api/v1 (same prefix style as catalog/orders), not /api/v1/auth.
admin_router = APIRouter()

# Resolved once at import time so tests can override this exact dependency
# callable via app.dependency_overrides[require_user_manager] = ...
# User-management endpoints (invite, list, role/status changes) require
# admin OR super_admin per docs/CONTRACTS.md's role hierarchy section --
# `manager` cannot access user-management endpoints at all.
require_user_manager = require_role("admin", "super_admin")


def _client_info(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    return await service.register_user(db, data)


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user = await service.authenticate_user(db, data.email, data.password)
    return await service.issue_token_pair(db, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await service.rotate_refresh_token(db, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)) -> None:
    await service.revoke_refresh_token(db, data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


# ---------------------------------------------------------------------------
# Admin panel: bootstrap (public, but self-limiting). Stays on `router` so
# it's reachable at /api/v1/auth/bootstrap-status and /api/v1/auth/bootstrap.
# ---------------------------------------------------------------------------


@router.get("/bootstrap-status", response_model=BootstrapStatus)
async def bootstrap_status(db: AsyncSession = Depends(get_db)) -> BootstrapStatus:
    return BootstrapStatus(admin_exists=await service.admin_exists(db))


@router.post("/bootstrap", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def bootstrap(data: BootstrapRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    return await service.bootstrap_admin(db, data)


# ---------------------------------------------------------------------------
# Invitation / password reset: public endpoints. Stay on `router` so
# they're reachable under /api/v1/auth.
# ---------------------------------------------------------------------------


@router.get("/invitations/{token}", response_model=InvitationPreview)
async def get_invitation(token: str, db: AsyncSession = Depends(get_db)) -> InvitationPreview:
    return await service.get_invitation_preview(db, token)


@router.post(
    "/accept-invitation", response_model=TokenPair, status_code=status.HTTP_201_CREATED
)
async def accept_invitation(
    data: AcceptInvitationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    ip_address, user_agent = _client_info(request)
    return await service.accept_invitation(
        db, data.token, data.password, ip_address=ip_address, user_agent=user_agent
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> None:
    ip_address, user_agent = _client_info(request)
    result = await service.request_password_reset(
        db, data.email, ip_address=ip_address, user_agent=user_agent
    )
    # Always 202 regardless of outcome -- no user enumeration, no
    # rate-limit-state leakage. Only schedule the email when there's
    # actually something to send.
    if result is not None:
        user, raw_token = result
        reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"
        expires_at = utcnow() + timedelta(minutes=settings.password_reset_token_expire_minutes)
        background_tasks.add_task(
            send_email,
            user.email,
            "Reset your password",
            password_reset_email(user.full_name, reset_url, expires_at),
        )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    ip_address, user_agent = _client_info(request)
    await service.reset_password(
        db, data.token, data.new_password, ip_address=ip_address, user_agent=user_agent
    )


# ---------------------------------------------------------------------------
# Admin panel: user management. Lives on `admin_router`, which the Main
# Coordinator should mount at plain /api/v1 (paths already include /users).
# ---------------------------------------------------------------------------


@admin_router.get("/users", response_model=Page[UserOut])
async def list_users(
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_user_manager),
) -> Page[UserOut]:
    params = PageParams(page=page, page_size=page_size)
    items, total = await service.list_users(db, params, q=q)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@admin_router.post("/users/invite", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def invite_user(
    payload: InviteUserRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_user_manager),
) -> InvitationOut:
    ip_address, user_agent = _client_info(request)
    invitation, raw_token = await service.invite_user(
        db,
        actor=admin,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        notes=payload.notes,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    accept_url = f"{settings.frontend_url}/accept-invitation?token={raw_token}"
    background_tasks.add_task(
        send_email,
        invitation.email,
        "You've been invited",
        invitation_email(invitation.full_name, invitation.role, accept_url, invitation.expires_at),
    )

    return InvitationOut.model_validate(invitation)


@admin_router.patch("/users/{user_id}/role", response_model=UserOut)
async def patch_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_user_manager),
) -> User:
    ip_address, user_agent = _client_info(request)
    return await service.update_user_role(
        db, admin, user_id, payload.role, ip_address=ip_address, user_agent=user_agent
    )


@admin_router.patch("/users/{user_id}/status", response_model=UserOut)
async def patch_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_user_manager),
) -> User:
    ip_address, user_agent = _client_info(request)
    return await service.update_user_status(
        db, admin, user_id, payload.is_active, ip_address=ip_address, user_agent=user_agent
    )
