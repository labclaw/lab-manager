"""Protocol CRUD and execution tracking endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.exceptions import BusinessError, ValidationError
from lab_manager.models.protocol import (
    ExecutionStatus,
    Protocol,
    ProtocolExecution,
    ProtocolStatus,
)

router = APIRouter()

_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "title",
    "category",
    "status",
    "estimated_duration_min",
}

_VALID_PROTOCOL_STATUSES = {
    ProtocolStatus.draft,
    ProtocolStatus.published,
    ProtocolStatus.archived,
}

_VALID_EXECUTION_STATUSES = {
    ExecutionStatus.in_progress,
    ExecutionStatus.completed,
    ExecutionStatus.abandoned,
}


# --- Request / Response schemas ---


class ProtocolStep(BaseModel):
    step_num: int = Field(ge=1)
    title: str = Field(max_length=500)
    description: Optional[str] = None
    duration_min: Optional[int] = Field(default=None, ge=0)
    warning: Optional[str] = None


class ProtocolCreate(BaseModel):
    title: str = Field(max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = Field(default=None, max_length=100)
    steps: list[ProtocolStep] = []
    estimated_duration_min: Optional[int] = Field(default=None, ge=0)
    status: str = ProtocolStatus.draft

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _VALID_PROTOCOL_STATUSES:
            raise ValueError(f"status must be one of {_VALID_PROTOCOL_STATUSES}")
        return v


class ProtocolUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = Field(default=None, max_length=100)
    steps: Optional[list[ProtocolStep]] = None
    estimated_duration_min: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_PROTOCOL_STATUSES:
            raise ValueError(f"status must be one of {_VALID_PROTOCOL_STATUSES}")
        return v


class ExecutionAdvance(BaseModel):
    notes: Optional[str] = None


class ExecutionComplete(BaseModel):
    notes: Optional[str] = None


# --- Protocol CRUD ---


@router.get("/")
def list_protocols(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(Protocol)
    if category:
        q = q.where(Protocol.category == category)
    if status:
        q = q.where(Protocol.status == status)
    if search:
        q = q.where(
            ilike_col(Protocol.title, search) | ilike_col(Protocol.description, search)
        )
    q = apply_sort(q, Protocol, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.post("/", status_code=201)
def create_protocol(body: ProtocolCreate, db: Session = Depends(get_db)):
    steps_data = [s.model_dump() for s in body.steps]
    protocol = Protocol(**body.model_dump(exclude={"steps"}), steps=steps_data)
    db.add(protocol)
    db.flush()
    db.refresh(protocol)
    return protocol


@router.get("/{protocol_id}")
def get_protocol(protocol_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Protocol, protocol_id, "Protocol")


@router.patch("/{protocol_id}")
def update_protocol(
    protocol_id: int, body: ProtocolUpdate, db: Session = Depends(get_db)
):
    protocol = get_or_404(db, Protocol, protocol_id, "Protocol")
    update_data = body.model_dump(exclude_unset=True, exclude={"steps"})
    if body.steps is not None:
        update_data["steps"] = [s.model_dump() for s in body.steps]
    for key, value in update_data.items():
        setattr(protocol, key, value)
    db.flush()
    db.refresh(protocol)
    return protocol


# --- Execution endpoints ---


@router.post("/{protocol_id}/start", status_code=201)
def start_execution(protocol_id: int, db: Session = Depends(get_db)):
    protocol = get_or_404(db, Protocol, protocol_id, "Protocol")
    if not protocol.steps:
        raise ValidationError("Cannot start execution for a protocol with no steps")
    execution = ProtocolExecution(
        protocol_id=protocol_id,
        status=ExecutionStatus.in_progress,
        current_step=0,
    )
    db.add(execution)
    db.flush()
    db.refresh(execution)
    return execution


@router.post("/executions/{exec_id}/advance")
def advance_execution(
    exec_id: int,
    body: ExecutionAdvance | None = None,
    db: Session = Depends(get_db),
):
    execution = get_or_404(db, ProtocolExecution, exec_id, "ProtocolExecution")
    if execution.status != ExecutionStatus.in_progress:
        raise BusinessError("Can only advance an in-progress execution")

    protocol = get_or_404(db, Protocol, execution.protocol_id, "Protocol")
    next_step = execution.current_step + 1

    if next_step >= len(protocol.steps):
        raise BusinessError("Already at the last step; use complete instead")

    execution.current_step = next_step
    if body and body.notes:
        execution.notes = body.notes
    db.flush()
    db.refresh(execution)
    return execution


@router.post("/executions/{exec_id}/complete")
def complete_execution(
    exec_id: int,
    body: ExecutionComplete | None = None,
    db: Session = Depends(get_db),
):
    execution = get_or_404(db, ProtocolExecution, exec_id, "ProtocolExecution")
    if execution.status != ExecutionStatus.in_progress:
        raise BusinessError("Can only complete an in-progress execution")

    execution.status = ExecutionStatus.completed
    execution.completed_at = datetime.now(timezone.utc)
    if body and body.notes:
        execution.notes = body.notes
    db.flush()
    db.refresh(execution)
    return execution


@router.get("/executions/")
def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    protocol_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    executed_by: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(ProtocolExecution)
    if protocol_id:
        q = q.where(ProtocolExecution.protocol_id == protocol_id)
    if status:
        q = q.where(ProtocolExecution.status == status)
    if executed_by:
        q = q.where(ProtocolExecution.executed_by == executed_by)
    _exec_sortable = {
        "id",
        "created_at",
        "started_at",
        "completed_at",
        "status",
        "current_step",
    }
    q = apply_sort(q, ProtocolExecution, sort_by, sort_dir, _exec_sortable)
    return paginate(q, db, page, page_size)
