"""Role-Based Access Control (RBAC) core.

Defines the 7 lab roles, their permission sets, and FastAPI dependency
helpers for route-level authorization.  Phase A/B only -- no routes are
guarded yet (that is Phase C).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Roles & levels (lower = more privileged)
# ---------------------------------------------------------------------------

ROLES: tuple[str, ...] = (
    "pi",
    "admin",
    "postdoc",
    "grad_student",
    "tech",
    "undergrad",
    "visitor",
)

ROLE_LEVELS: dict[str, int] = {
    "pi": 0,
    "admin": 1,
    "postdoc": 2,
    "grad_student": 3,
    "tech": 3,
    "undergrad": 4,
    "visitor": 4,
}

# ---------------------------------------------------------------------------
# All permissions known to the system
# ---------------------------------------------------------------------------

ALL_PERMISSIONS: frozenset[str] = frozenset(
    {
        "view_inventory",
        "view_documents",
        "view_equipment",
        "view_orders",
        "view_analytics",
        "upload_documents",
        "create_orders",
        "request_order",
        "receive_shipments",
        "log_consumption",
        "log_equipment_usage",
        "review_documents",
        "approve_orders",
        "approve_order_requests",
        "manage_products",
        "manage_vendors",
        "manage_users",
        "manage_settings",
        "export_data",
        "delete_records",
        "view_audit_log",
        "ask_ai",
        "manage_alerts",
        "acknowledge_alerts",
    }
)

# ---------------------------------------------------------------------------
# Per-role permission sets
# ---------------------------------------------------------------------------

_VIEW_PERMS: frozenset[str] = frozenset(
    {
        "view_inventory",
        "view_documents",
        "view_equipment",
        "view_orders",
        "view_analytics",
    }
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "pi": ALL_PERMISSIONS,
    "admin": ALL_PERMISSIONS - {"delete_records"},
    "postdoc": frozenset(
        _VIEW_PERMS
        | {
            "upload_documents",
            "create_orders",
            "request_order",
            "receive_shipments",
            "log_consumption",
            "log_equipment_usage",
            "review_documents",
            "manage_products",
            "manage_vendors",
            "export_data",
            "ask_ai",
            "manage_alerts",
            "acknowledge_alerts",
        }
    ),
    "grad_student": frozenset(
        _VIEW_PERMS
        | {
            "upload_documents",
            "request_order",
            "receive_shipments",
            "log_consumption",
            "log_equipment_usage",
            "ask_ai",
            "acknowledge_alerts",
        }
    ),
    "tech": frozenset(
        _VIEW_PERMS
        | {
            "upload_documents",
            "receive_shipments",
            "log_consumption",
            "log_equipment_usage",
            "ask_ai",
            "manage_alerts",
            "acknowledge_alerts",
        }
    ),
    "undergrad": frozenset({"view_inventory", "view_documents", "view_equipment"}),
    "visitor": frozenset({"view_inventory", "view_documents", "view_equipment"}),
}


@lru_cache(maxsize=16)
def get_permissions(role: str) -> frozenset[str]:
    """Return the permission set for *role*, or empty frozenset if unknown."""
    return ROLE_PERMISSIONS.get(role, frozenset())


# ---------------------------------------------------------------------------
# FastAPI dependency helpers
# ---------------------------------------------------------------------------


def get_current_staff(request: Request) -> dict[str, Any]:
    """Extract the authenticated staff dict from ``request.state.staff``.

    Raises 401 if the staff dict is missing or has no ``id``.
    """
    staff: dict[str, Any] | None = getattr(request.state, "staff", None)
    if not staff or staff.get("id") is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return staff


def require_permission(*perms: str):
    """Return a FastAPI ``Depends`` callable that checks permissions.

    Usage::

        @router.get("/orders", dependencies=[Depends(require_permission("view_orders"))])
        def list_orders(...): ...

    Raises 403 if the current staff lacks *any* of the requested permissions.
    """

    def _checker(request: Request) -> dict[str, Any]:
        staff = get_current_staff(request)
        role = staff.get("role", "visitor")
        staff_perms = get_permissions(role)
        missing = set(perms) - staff_perms
        if missing:
            logger.warning(
                "Permission denied: staff_id=%s role=%s missing=%s",
                staff.get("id"),
                role,
                sorted(missing),
            )
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions: {', '.join(sorted(missing))}",
            )
        return staff

    return _checker
