"""Vendor CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.exceptions import ConflictError
from lab_manager.models.order import Order
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor

router = APIRouter()

_VENDOR_SORTABLE = {"id", "created_at", "updated_at", "name", "email", "website"}

_Db = Depends(get_db)
_VendPage = Query(1, ge=1)
_VendPageSize = Query(50, ge=1, le=200)
_VendName = Query(None)
_VendSearch = Query(None)
_VendSortBy = Query("id")
_VendSortDir = Query("asc", pattern="^(asc|desc)$")
_VendProdPage = Query(1, ge=1)
_VendProdPageSize = Query(50, ge=1, le=200)
_VendOrdPage = Query(1, ge=1)
_VendOrdPageSize = Query(50, ge=1, le=200)


class VendorCreate(BaseModel):
    name: str
    aliases: list[str] = []
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class VendorUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


@router.get("/")
def list_vendors(
    page: int = _VendPage,
    page_size: int = _VendPageSize,
    name: str | None = _VendName,
    search: str | None = _VendSearch,
    sort_by: str = _VendSortBy,
    sort_dir: str = _VendSortDir,
    db: Session = _Db,
):
    q = db.query(Vendor)
    if name:
        q = q.filter(ilike_col(Vendor.name, name))
    if search:
        q = q.filter(ilike_col(Vendor.name, search) | ilike_col(Vendor.email, search) | ilike_col(Vendor.notes, search))
    q = apply_sort(q, Vendor, sort_by, sort_dir, _VENDOR_SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_vendor(body: VendorCreate, db: Session = _Db):
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = _Db):
    return get_or_404(db, Vendor, vendor_id, "Vendor")


@router.patch("/{vendor_id}")
def update_vendor(vendor_id: int, body: VendorUpdate, db: Session = _Db):
    vendor = get_or_404(db, Vendor, vendor_id, "Vendor")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(vendor, key, value)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(vendor_id: int, db: Session = _Db):
    vendor = get_or_404(db, Vendor, vendor_id, "Vendor")
    try:
        db.delete(vendor)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError("Cannot delete vendor: it is referenced by products or orders") from e
    return None


@router.get("/{vendor_id}/products")
def list_vendor_products(
    vendor_id: int,
    page: int = _VendProdPage,
    page_size: int = _VendProdPageSize,
    db: Session = _Db,
):
    get_or_404(db, Vendor, vendor_id, "Vendor")
    q = db.query(Product).filter(Product.vendor_id == vendor_id).order_by(Product.id)
    return paginate(q, page, page_size)


@router.get("/{vendor_id}/orders")
def list_vendor_orders(
    vendor_id: int,
    page: int = _VendOrdPage,
    page_size: int = _VendOrdPageSize,
    db: Session = _Db,
):
    get_or_404(db, Vendor, vendor_id, "Vendor")
    q = db.query(Order).filter(Order.vendor_id == vendor_id).order_by(Order.id)
    return paginate(q, page, page_size)
