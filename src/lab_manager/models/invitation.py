"""Lab invitation model for RBAC onboarding."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlmodel import Field, SQLModel


class Invitation(SQLModel, table=True):
    __tablename__ = "invitations"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, index=True)
    name: str = Field(max_length=200)
    role: str = Field(max_length=50)
    token: str = Field(max_length=255, unique=True, index=True)
    invited_by: Optional[int] = Field(default=None, foreign_key="staff.id")
    status: str = Field(default="pending", max_length=20)
    access_expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(__import__("datetime").timezone.utc),
        sa_column_kwargs={"server_default": func.now()},
    )
    accepted_at: Optional[datetime] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)
