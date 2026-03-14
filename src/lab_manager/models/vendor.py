"""Vendor / supplier model."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, Column
from sqlalchemy import JSON

from lab_manager.models.base import AuditMixin


class Vendor(AuditMixin, table=True):
    __tablename__ = "vendors"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True, unique=True)
    aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    website: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None)
