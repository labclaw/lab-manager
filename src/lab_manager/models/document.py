"""Scanned document and extraction models."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, Column
from sqlalchemy import JSON, Text

from lab_manager.models.base import AuditMixin


class Document(AuditMixin, table=True):
    __tablename__ = "documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_path: str = Field(max_length=1000)
    file_name: str = Field(max_length=255)
    document_type: Optional[str] = Field(default=None, max_length=50, index=True)
    vendor_name: Optional[str] = Field(default=None, max_length=255)
    ocr_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    extracted_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    extraction_model: Optional[str] = Field(default=None, max_length=100)
    extraction_confidence: Optional[float] = Field(default=None)
    status: str = Field(default="pending", max_length=30, index=True)
    review_notes: Optional[str] = Field(default=None)
    reviewed_by: Optional[str] = Field(default=None, max_length=200)
    order_id: Optional[int] = Field(default=None, foreign_key="orders.id")
