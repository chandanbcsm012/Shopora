from __future__ import annotations

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.modules.auth.models import User
from app.shared.error_codes import ErrorCode

# tokenUrl is documentation-only (used by OpenAPI/Swagger's "Authorize"
# button); the actual login route is mounted by the Main Coordinator at
# /api/v1/auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    not_authenticated = AppError(
        ErrorCode.NOT_AUTHENTICATED,
        "Not authenticated.",
        401,
    )

    if not token:
        raise not_authenticated

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise not_authenticated

    user_id = payload.get("sub")
    if user_id is None:
        raise not_authenticated

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise not_authenticated

    return user


def require_role(*roles: str):
    """Gate a route to one or more roles: `require_role("admin")` for a
    single role (backward compatible), or `require_role("admin",
    "super_admin")` to mean "any of these roles passes"."""

    async def _require_role(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            allowed = "', '".join(roles)
            raise AppError(
                ErrorCode.NOT_AUTHORIZED,
                f"Requires role '{allowed}'.",
                403,
            )
        return user

    return _require_role
