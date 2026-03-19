"""Lab staff / user model."""

from __future__ import annotations

from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class Staff(AuditMixin, table=True):
    __tablename__ = "staff"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    email: str | None = Field(default=None, max_length=255, unique=True)
    role: str = Field(default="member", max_length=50)
    is_active: bool = Field(default=True)
    password_hash: str | None = Field(default=None, max_length=255)
