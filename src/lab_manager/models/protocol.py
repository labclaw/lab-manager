"""Protocol and ProtocolExecution models."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    pass


class ProtocolStatus:
    draft = "draft"
    published = "published"
    archived = "archived"


VALID_PROTOCOL_STATUSES = (
    ProtocolStatus.draft,
    ProtocolStatus.published,
    ProtocolStatus.archived,
)


class ExecutionStatus:
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


VALID_EXECUTION_STATUSES = (
    ExecutionStatus.in_progress,
    ExecutionStatus.completed,
    ExecutionStatus.abandoned,
)


class Protocol(AuditMixin, table=True):
    __tablename__ = "protocol"
    __table_args__ = (
        sa.CheckConstraint(
            f"status IN ({','.join(repr(v) for v in VALID_PROTOCOL_STATUSES)})",
            name="ck_protocol_status",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=500, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(sa.Text))
    category: Optional[str] = Field(default=None, max_length=100, index=True)
    steps: list = Field(default_factory=list, sa_column=Column(sa.JSON))
    estimated_duration_min: Optional[int] = Field(default=None)
    status: str = Field(default=ProtocolStatus.draft, max_length=30, index=True)

    executions: list["ProtocolExecution"] = Relationship(back_populates="protocol")


class ProtocolExecution(AuditMixin, table=True):
    __tablename__ = "protocol_execution"
    __table_args__ = (
        sa.CheckConstraint(
            f"status IN ({','.join(repr(v) for v in VALID_EXECUTION_STATUSES)})",
            name="ck_protocol_execution_status",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    protocol_id: int = Field(
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("protocol.id", ondelete="CASCADE"),
            index=True,
        )
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    completed_at: Optional[datetime] = Field(default=None)
    status: str = Field(default=ExecutionStatus.in_progress, max_length=30, index=True)
    current_step: int = Field(default=0)
    notes: Optional[str] = Field(default=None, sa_column=Column(sa.Text))
    executed_by: Optional[str] = Field(default=None, max_length=100)

    protocol: Optional["Protocol"] = Relationship(back_populates="executions")
