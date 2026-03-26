"""Role-based access control (RBAC) dependency for FastAPI routes.

Usage in routes:
    @router.post("/", dependencies=[Depends(require_permission("create"))])
    def create_item(...): ...

    @router.delete("/{id}", dependencies=[Depends(require_permission("delete"))])
    def delete_item(...): ...
"""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.config import get_settings
from lab_manager.exceptions import ForbiddenError
from lab_manager.models.staff import ROLE_PERMISSIONS, Staff


def _get_staff_role(request: Request, db: Session = Depends(get_db)) -> str:
    """Resolve the current user's role from request context."""
    settings = get_settings()
    if not settings.auth_enabled:
        # Dev mode: treat all users as admin
        return "admin"

    user = getattr(request.state, "user", "system")
    if user in ("system", "api-client"):
        return "admin"

    staff = db.execute(select(Staff).where(Staff.name == user)).scalar_one_or_none()
    if not staff:
        return "viewer"
    return staff.role


def require_permission(permission: str):
    """Return a FastAPI dependency that checks if the user has a permission."""

    def _check(role: str = Depends(_get_staff_role)):
        allowed = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["viewer"])
        if permission not in allowed:
            raise ForbiddenError(
                f"Role '{role}' does not have '{permission}' permission"
            )

    return _check
