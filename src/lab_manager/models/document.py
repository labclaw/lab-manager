"""Scanned document and extraction models."""

import enum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Column, Text
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.order import Order


class DocumentStatus(enum.StrEnum):
    pending = "pending"
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
            "status IN ('pending','extracted','needs_review','approved','rejected','ocr_failed','deleted')",
            name="ck_documents_status",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    file_path: str = Field(max_length=1000)
    file_name: str = Field(max_length=255, unique=True)
    document_type: str | None = Field(default=None, max_length=50, index=True)
    vendor_name: str | None = Field(default=None, max_length=255)
    ocr_text: str | None = Field(default=None, sa_column=Column(Text))
    extracted_data: dict | None = Field(default=None, sa_column=Column(sa.JSON))
    extraction_model: str | None = Field(default=None, max_length=100)
    extraction_confidence: float | None = Field(default=None)
    status: str = Field(default="pending", max_length=30, index=True)
    review_notes: str | None = Field(default=None)
    reviewed_by: str | None = Field(default=None, max_length=200)

    orders: list["Order"] = Relationship(back_populates="document")
