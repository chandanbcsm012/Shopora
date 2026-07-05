"""Cross-cutting FastAPI dependencies that don't belong to one module.

Auth-specific dependencies (`get_current_user`, `require_role`) live in
`app.modules.auth.dependencies` since `auth` owns the User model — import
them from there, do not duplicate them here.
"""

from app.core.db import get_db

__all__ = ["get_db"]
