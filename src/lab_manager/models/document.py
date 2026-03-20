"""Scanned document and extraction models."""

import enum
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Column, Text
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.order import Order


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    extracted = "extracted"
    needs_review = "needs_review"
    approved = "approved"
    rejected = "rejected"
    ocr_failed = "ocr_failed"
    deleted = "deleted"


class Document(AuditMixin, table=True):
    __tablename__ = "documents"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending','processing','extracted','needs_review','approved','rejected','ocr_failed','deleted')",
            name="ck_documents_status",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    file_path: str = Field(max_length=1000)
    file_name: str = Field(max_length=255, unique=True)
    document_type: Optional[str] = Field(default=None, max_length=50, index=True)
    vendor_name: Optional[str] = Field(default=None, max_length=255)
    ocr_text: Optional[str] = Field(default=None, sa_column=Column(Text))
    extracted_data: Optional[dict] = Field(default=None, sa_column=Column(sa.JSON))
    extraction_model: Optional[str] = Field(default=None, max_length=100)
    extraction_confidence: Optional[float] = Field(default=None)
    status: str = Field(default="pending", max_length=30, index=True)
    review_notes: Optional[str] = Field(default=None)
    reviewed_by: Optional[str] = Field(default=None, max_length=200)

    orders: List["Order"] = Relationship(back_populates="document")
