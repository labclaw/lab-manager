"""Lab invitation model for RBAC onboarding."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class Invitation(AuditMixin, table=True):
    __tablename__ = "invitations"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, index=True)
    name: str = Field(max_length=200)
    role: str = Field(max_length=50)
    token: str = Field(max_length=255, unique=True, index=True)
    invited_by: Optional[int] = Field(default=None, foreign_key="staff.id")
    status: str = Field(default="pending", max_length=20)
    access_expires_at: Optional[datetime] = Field(default=None)
    accepted_at: Optional[datetime] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)
