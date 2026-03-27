"""Electronic Lab Notebook (ELN) models."""

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Column, Table, Text
from sqlmodel import Field, Relationship, SQLModel

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    pass

# Association table for many-to-many relationship between entries and tags.
# Must use SQLModel.metadata so the table is registered with the same metadata
# used by create_all().
eln_entry_tags = Table(
    "eln_entry_tags",
    SQLModel.metadata,
    sa.Column(
        "entry_id",
        sa.Integer,
        sa.ForeignKey("eln_entries.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "tag_id",
        sa.Integer,
        sa.ForeignKey("eln_tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ELNContentType(str, enum.Enum):
    text = "text"
    table = "table"
    mixed = "mixed"


class ELNEntry(AuditMixin, table=True):
    __tablename__ = "eln_entries"
    __table_args__ = (
        sa.CheckConstraint(
            "content_type IN ('text', 'table', 'mixed')",
            name="ck_eln_entries_content_type",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=500, index=True)
    content_type: str = Field(default=ELNContentType.text, max_length=20)
    content: Optional[str] = Field(default=None, sa_column=Column(Text))
    experiment_id: Optional[int] = Field(default=None, index=True)
    project_id: Optional[int] = Field(default=None, index=True)
    tags_json: list = Field(default_factory=list, sa_column=Column(sa.JSON))
    attachments_json: list = Field(default_factory=list, sa_column=Column(sa.JSON))
    is_deleted: bool = Field(default=False, index=True)

    # Relationships
    attachments: List["ELNAttachment"] = Relationship(back_populates="entry")
    tag_objects: List["ELNTag"] = Relationship(
        back_populates="entries",
        sa_relationship_kwargs={"secondary": eln_entry_tags},
    )


class ELNAttachment(AuditMixin, table=True):
    __tablename__ = "eln_attachments"

    id: Optional[int] = Field(default=None, primary_key=True)
    entry_id: int = Field(
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("eln_entries.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    filename: str = Field(max_length=500)
    file_path: str = Field(max_length=1000)
    file_type: Optional[str] = Field(default=None, max_length=100)
    file_size: Optional[int] = Field(default=None)
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"server_default": sa.func.now()},
    )

    entry: Optional["ELNEntry"] = Relationship(back_populates="attachments")


class ELNTag(SQLModel, table=True):
    __tablename__ = "eln_tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True, index=True)
    color: Optional[str] = Field(default=None, max_length=20)

    entries: List["ELNEntry"] = Relationship(
        back_populates="tag_objects",
        sa_relationship_kwargs={"secondary": eln_entry_tags},
    )
