"""Supply request and approval endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, paginate
from lab_manager.exceptions import ConflictError, ForbiddenError
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.order_request import OrderRequest, RequestStatus
from lab_manager.models.staff import Staff

router = APIRouter()

_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "status",
    "urgency",
    "estimated_price",
    "quantity",
}

_VALID_STATUSES = {s.value for s in RequestStatus}
_MAX_QUANTITY = 1_000_000


# --- Schemas ---


class OrderRequestCreate(BaseModel):
    product_id: Optional[int] = None
    vendor_id: Optional[int] = None
    catalog_number: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    quantity: Decimal = Field(
        default=Decimal("1"), gt=0, le=Decimal(str(_MAX_QUANTITY))
    )
    unit: Optional[str] = Field(default=None, max_length=50)
    estimated_price: Optional[Decimal] = Field(default=None, ge=0)
    justification: Optional[str] = Field(default=None, max_length=2000)
    urgency: str = "normal"


class ReviewBody(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)


class OrderRequestResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    requested_by: int
    product_id: Optional[int] = None
    vendor_id: Optional[int] = None
    catalog_number: Optional[str] = None
    description: Optional[str] = None
    quantity: Decimal
    unit: Optional[str] = None
    estimated_price: Optional[Decimal] = None
    justification: Optional[str] = None
    urgency: str
    status: str
    reviewed_by: Optional[int] = None
    review_note: Optional[str] = None
    order_id: Optional[int] = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    reviewed_at: datetime | None = None


# --- Helpers ---


def _get_current_staff(request: Request, db: Session) -> Staff:
    """Resolve the current user from request.state.user to a Staff record."""
    user_name = getattr(request.state, "user", "system")
    staff = db.scalars(select(Staff).where(Staff.name == user_name)).first()
    if not staff:
        # In dev mode (auth_enabled=false), auto-create a staff record
        staff = Staff(name=user_name, role="admin", is_active=True)
        db.add(staff)
        db.flush()
    return staff


def _is_admin_or_pi(staff: Staff) -> bool:
    return staff.role in ("admin", "pi")


# --- Endpoints ---


@router.get("/stats")
def request_stats(
    request: Request,
    db: Session = Depends(get_db),
):
    """Count requests by status."""
    staff = _get_current_staff(request, db)
    q = select(OrderRequest.status, func.count(OrderRequest.id))

    if not _is_admin_or_pi(staff):
        q = q.where(OrderRequest.requested_by == staff.id)

    rows = db.execute(q.group_by(OrderRequest.status)).all()
    counts = {s.value: 0 for s in RequestStatus}
    for status_val, cnt in rows:
        counts[status_val] = cnt
    counts["total"] = sum(counts.values())
    return counts


@router.get("/")
def list_requests(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """List requests. Students see own; PI/admin see all."""
    staff = _get_current_staff(request, db)
    q = select(OrderRequest)

    if not _is_admin_or_pi(staff):
        q = q.where(OrderRequest.requested_by == staff.id)

    if status and status in _VALID_STATUSES:
        q = q.where(OrderRequest.status == status)
    if urgency and urgency in ("normal", "urgent"):
        q = q.where(OrderRequest.urgency == urgency)

    q = apply_sort(q, OrderRequest, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.post("/", status_code=201)
def create_request(
    body: OrderRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Create a supply request (any authenticated user)."""
    staff = _get_current_staff(request, db)

    if body.urgency not in ("normal", "urgent"):
        body.urgency = "normal"

    req = OrderRequest(
        **body.model_dump(),
        requested_by=staff.id,
        status="pending",
    )
    db.add(req)
    db.flush()
    db.refresh(req)
    return req


@router.get("/{request_id}")
def get_request(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get request detail. Students can only see own requests."""
    staff = _get_current_staff(request, db)
    req = get_or_404(db, OrderRequest, request_id, "OrderRequest")

    if not _is_admin_or_pi(staff) and req.requested_by != staff.id:
        raise ForbiddenError("You can only view your own requests")

    return req


@router.post("/{request_id}/approve")
def approve_request(
    request_id: int,
    body: ReviewBody,
    request: Request,
    db: Session = Depends(get_db),
):
    """Approve a request. Creates an Order + OrderItem automatically. PI/admin only."""
    staff = _get_current_staff(request, db)

    if not _is_admin_or_pi(staff):
        raise ForbiddenError("Only PI or admin can approve requests")

    req = get_or_404(db, OrderRequest, request_id, "OrderRequest")

    if req.status != "pending":
        raise ConflictError(f"Cannot approve request in '{req.status}' status")

    # Create the Order
    order = Order(
        vendor_id=req.vendor_id,
        status="pending",
    )
    db.add(order)
    db.flush()

    # Create the OrderItem
    item = OrderItem(
        order_id=order.id,
        catalog_number=req.catalog_number,
        description=req.description,
        quantity=req.quantity,
        unit=req.unit,
        unit_price=req.estimated_price,
        product_id=req.product_id,
    )
    db.add(item)
    db.flush()

    # Update request
    now = datetime.now(timezone.utc)
    req.status = "approved"
    req.reviewed_by = staff.id
    req.review_note = body.note
    req.order_id = order.id
    req.reviewed_at = now
    db.flush()
    db.refresh(req)

    return req


@router.post("/{request_id}/reject")
def reject_request(
    request_id: int,
    body: ReviewBody,
    request: Request,
    db: Session = Depends(get_db),
):
    """Reject a request with optional note. PI/admin only."""
    staff = _get_current_staff(request, db)

    if not _is_admin_or_pi(staff):
        raise ForbiddenError("Only PI or admin can reject requests")

    req = get_or_404(db, OrderRequest, request_id, "OrderRequest")

    if req.status != "pending":
        raise ConflictError(f"Cannot reject request in '{req.status}' status")

    now = datetime.now(timezone.utc)
    req.status = "rejected"
    req.reviewed_by = staff.id
    req.review_note = body.note
    req.reviewed_at = now
    db.flush()
    db.refresh(req)

    return req


@router.post("/{request_id}/cancel")
def cancel_request(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Cancel own pending request."""
    staff = _get_current_staff(request, db)
    req = get_or_404(db, OrderRequest, request_id, "OrderRequest")

    if req.requested_by != staff.id:
        raise ForbiddenError("You can only cancel your own requests")

    if req.status != "pending":
        raise ConflictError(f"Cannot cancel request in '{req.status}' status")

    req.status = "cancelled"
    db.flush()
    db.refresh(req)

    return req
