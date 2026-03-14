"""Storage location model."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class StorageLocation(AuditMixin, table=True):
    __tablename__ = "locations"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    room: Optional[str] = Field(default=None, max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[int] = Field(default=None)
    description: Optional[str] = Field(default=None)
