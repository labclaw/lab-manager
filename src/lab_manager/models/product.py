"""Product / catalog item model."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, Column
from sqlalchemy import JSON

from lab_manager.models.base import AuditMixin


class Product(AuditMixin, table=True):
    __tablename__ = "products"

    id: Optional[int] = Field(default=None, primary_key=True)
    catalog_number: str = Field(max_length=100, index=True)
    name: str = Field(max_length=500)
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id", index=True)
    category: Optional[str] = Field(default=None, max_length=100, index=True)
    cas_number: Optional[str] = Field(default=None, max_length=30)
    storage_temp: Optional[str] = Field(default=None, max_length=50)
    unit: Optional[str] = Field(default=None, max_length=50)
    hazard_info: Optional[str] = Field(default=None, max_length=255)
    extra: dict = Field(default_factory=dict, sa_column=Column(JSON))
