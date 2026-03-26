"""Lab staff / user model."""

from __future__ import annotations

import enum
from typing import Optional

from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class StaffRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    member = "member"
    viewer = "viewer"


# Permission hierarchy: admin > manager > member > viewer.
# Each level includes all permissions of lower levels.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"read"},
    "member": {"read", "create", "update"},
    "manager": {"read", "create", "update", "delete", "review", "import"},
    "admin": {"read", "create", "update", "delete", "review", "import", "admin"},
}


class Staff(AuditMixin, table=True):
    __tablename__ = "staff"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    email: Optional[str] = Field(default=None, max_length=255, unique=True)
    role: str = Field(default="member", max_length=50)
    is_active: bool = Field(default=True)
    password_hash: Optional[str] = Field(default=None, max_length=255)

    @property
    def permissions(self) -> set[str]:
        return ROLE_PERMISSIONS.get(self.role, ROLE_PERMISSIONS["viewer"])
