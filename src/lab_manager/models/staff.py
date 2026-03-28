"""Lab staff / user model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class Staff(AuditMixin, table=True):
    __tablename__ = "staff"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    email: Optional[str] = Field(default=None, max_length=255, unique=True)
    role: str = Field(default="grad_student", max_length=50)
    role_level: int = Field(default=3)
    is_active: bool = Field(default=True)
    password_hash: Optional[str] = Field(default=None, max_length=255)
    invited_by: Optional[int] = Field(default=None, foreign_key="staff.id")
    last_login_at: Optional[datetime] = Field(default=None)
    access_expires_at: Optional[datetime] = Field(default=None)
    failed_login_count: int = Field(default=0)
    locked_until: Optional[datetime] = Field(default=None)
    staff_type: str = Field(default="human", max_length=20)
    agent_config: Optional[dict] = Field(default=None, sa_column=sa.Column(sa.JSON))
    avatar_emoji: Optional[str] = Field(default=None, max_length=10)
