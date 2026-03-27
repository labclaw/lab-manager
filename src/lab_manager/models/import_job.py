"""Bulk import job tracking models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, Text, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy import JSON
from sqlmodel import Field, Relationship, SQLModel

from lab_manager.models.base import AuditMixin


class ImportType(str, enum.Enum):
    """Type of entity being imported."""

    products = "products"
    vendors = "vendors"
    inventory = "inventory"


class ImportStatus(str, enum.Enum):
    """Status of an import job."""

    uploading = "uploading"  # File being received
    validating = "validating"  # Parsing and validating CSV
    preview = "preview"  # Ready for user review
    importing = "importing"  # Batch insert in progress
    completed = "completed"  # All rows processed
    failed = "failed"  # Fatal error during import
    cancelled = "cancelled"  # User cancelled


class ImportJob(AuditMixin, table=True):
    """Tracks the state of a bulk import operation."""

    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("ix_import_jobs_status", "status"),
        Index("ix_import_jobs_created_at", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    import_type: ImportType = Field(
        sa_column=Column(SQLEnum(ImportType), nullable=False)
    )
    status: ImportStatus = Field(
        default=ImportStatus.uploading,
        sa_column=Column(SQLEnum(ImportStatus), nullable=False, index=True),
    )

    # File metadata
    original_filename: str = Field(max_length=255)
    file_size_bytes: int = Field()
    file_hash: str = Field(max_length=64)  # SHA-256 for dedup

    # Progress tracking
    total_rows: Optional[int] = Field(default=None)
    valid_rows: Optional[int] = Field(default=None)
    imported_rows: Optional[int] = Field(default=0)
    failed_rows: Optional[int] = Field(default=0)

    # Import options (JSON)
    options: dict = Field(
        default_factory=dict, sa_column=Column(_JSONB().with_variant(JSON, "sqlite"))
    )

    # Preview data (first N rows for user review)
    preview_data: Optional[List[dict]] = Field(
        default=None, sa_column=Column(_JSONB().with_variant(JSON, "sqlite"))
    )

    # Timing
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # Owner (staff who initiated the import)
    created_by_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("staff.id", ondelete="SET NULL")),
    )

    # Relationships
    errors: List["ImportError"] = Relationship(back_populates="job")


class ImportError(SQLModel, table=True):
    """Individual row-level errors from an import job."""

    __tablename__ = "import_errors"
    __table_args__ = (
        Index("ix_import_errors_job_id", "job_id"),
        Index("ix_import_errors_job_row", "job_id", "row_number"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    row_number: int = Field()  # 1-indexed row in CSV
    field: Optional[str] = Field(
        default=None, max_length=100
    )  # Column name or None for row-level
    error_type: str = Field(
        max_length=50
    )  # "validation", "duplicate", "not_found", "system"
    message: str = Field(max_length=500)
    raw_data: Optional[str] = Field(
        default=None, sa_column=Column(Text)
    )  # JSON of row data

    # Relationships
    job: ImportJob = Relationship(back_populates="errors")
