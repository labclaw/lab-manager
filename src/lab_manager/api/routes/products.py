"""Product CRUD endpoints."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field as PydanticField, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.exceptions import ConflictError
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.order import OrderItem
from lab_manager.models.product import Product
from lab_manager.services.search import index_product_record

router = APIRouter()

_PRODUCT_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "name",
    "catalog_number",
    "category",
    "vendor_id",
}

_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")


def _validate_cas(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    if not _CAS_RE.match(v):
        raise ValueError(
            f"Invalid CAS number format: {v!r}. Expected format: NNNNN-NN-N"
        )
    return v


class ProductCreate(BaseModel):
    catalog_number: str = PydanticField(..., min_length=1, max_length=100)
    name: str = PydanticField(..., min_length=1, max_length=500)
    vendor_id: Optional[int] = None
    category: Optional[str] = PydanticField(default=None, max_length=100)
    cas_number: Optional[str] = PydanticField(default=None, max_length=30)
    storage_temp: Optional[str] = PydanticField(default=None, max_length=50)
    unit: Optional[str] = PydanticField(default=None, max_length=50)
    hazard_info: Optional[str] = PydanticField(default=None, max_length=255)
    extra: dict = {}

    @field_validator("cas_number")
    @classmethod
    def validate_cas(cls, v: str | None) -> str | None:
        return _validate_cas(v)


class ProductUpdate(BaseModel):
    catalog_number: Optional[str] = PydanticField(default=None, max_length=100)
    name: Optional[str] = PydanticField(default=None, max_length=500)
    vendor_id: Optional[int] = None
    category: Optional[str] = PydanticField(default=None, max_length=100)
    cas_number: Optional[str] = PydanticField(default=None, max_length=30)
    storage_temp: Optional[str] = PydanticField(default=None, max_length=50)
    unit: Optional[str] = PydanticField(default=None, max_length=50)
    hazard_info: Optional[str] = PydanticField(default=None, max_length=255)
    extra: Optional[dict] = None

    @field_validator("cas_number")
    @classmethod
    def validate_cas(cls, v: str | None) -> str | None:
        return _validate_cas(v)


class ProductResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    catalog_number: str
    name: str
    vendor_id: Optional[int] = None
    category: Optional[str] = None
    cas_number: Optional[str] = None
    molecular_weight: Optional[float] = None
    molecular_formula: Optional[str] = None
    smiles: Optional[str] = None
    pubchem_cid: Optional[int] = None
    storage_temp: Optional[str] = None
    unit: Optional[str] = None
    hazard_info: Optional[str] = None
    extra: dict = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


@router.get("/")
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    vendor_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    catalog_number: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(Product).options(selectinload(Product.vendor))
    if not include_inactive:
        q = q.where(Product.is_active == True)  # noqa: E712
    if vendor_id is not None:
        q = q.where(Product.vendor_id == vendor_id)
    if category:
        q = q.where(ilike_col(Product.category, category))
    if catalog_number:
        q = q.where(ilike_col(Product.catalog_number, catalog_number))
    if search:
        q = q.where(
            ilike_col(Product.name, search)
            | ilike_col(Product.catalog_number, search)
            | ilike_col(Product.cas_number, search)
        )
    q = apply_sort(q, Product, sort_by, sort_dir, _PRODUCT_SORTABLE)
    return paginate(q, db, page, page_size)


@router.post(
    "/", status_code=201, dependencies=[Depends(require_permission("manage_products"))]
)
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**body.model_dump())
    db.add(product)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        if "uq_product_catalog_vendor" in str(e.orig):
            raise ConflictError(
                f"Product with catalog_number={body.catalog_number!r} already exists for this vendor"
            )
        raise ConflictError("Duplicate or constraint violation")
    db.refresh(product)
    index_product_record(product)
    return product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Product, product_id, "Product")


@router.patch(
    "/{product_id}", dependencies=[Depends(require_permission("manage_products"))]
)
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)):
    product = get_or_404(db, Product, product_id, "Product")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        if "uq_product_catalog_vendor" in str(e.orig):
            raise ConflictError(
                f"catalog_number {body.catalog_number!r} already exists for this vendor"
            )
        raise ConflictError(
            "Constraint violation"
        )  # pragma: no cover — defensive fallback
    db.refresh(product)
    index_product_record(product)
    return product


@router.delete(
    "/{product_id}",
    status_code=204,
    dependencies=[Depends(require_permission("delete_records"))],
)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = get_or_404(db, Product, product_id, "Product")
    try:
        db.delete(product)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            "Cannot delete product: it is referenced by inventory or order items"
        )
    return None


@router.get("/{product_id}/inventory")
def list_product_inventory(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    get_or_404(db, Product, product_id, "Product")
    q = (
        select(InventoryItem)
        .where(InventoryItem.product_id == product_id)
        .order_by(InventoryItem.id)
    )
    return paginate(q, db, page, page_size)


@router.get("/{product_id}/orders")
def list_product_orders(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    get_or_404(db, Product, product_id, "Product")
    q = (
        select(OrderItem)
        .where(OrderItem.product_id == product_id)
        .order_by(OrderItem.id)
    )
    return paginate(q, db, page, page_size)


@router.get(
    "/{product_id}/pubchem",
    dependencies=[Depends(require_permission("view_inventory"))],
)
def get_pubchem_enrichment(product_id: int, db: Session = Depends(get_db)):
    """Fetch or refresh PubChem enrichment data for a product."""
    from lab_manager.services.pubchem import enrich_product

    product = get_or_404(db, Product, product_id, "Product")
    data = enrich_product(product.name, product.catalog_number)
    return {"product_id": product_id, "enrichment": data}


@router.post(
    "/{product_id}/enrich",
    response_model=ProductResponse,
    dependencies=[Depends(require_permission("manage_products"))],
)
def enrich_product_endpoint(product_id: int, db: Session = Depends(get_db)):
    """Enrich a product with PubChem data and persist to database."""
    from lab_manager.services.pubchem import enrich_product

    product = get_or_404(db, Product, product_id, "Product")
    data = enrich_product(product.name, product.catalog_number)

    # Only update fields that are currently empty on the product
    field_map = {
        "cas_number": "cas_number",
        "molecular_weight": "molecular_weight",
        "molecular_formula": "molecular_formula",
        "smiles": "smiles",
        "pubchem_cid": "pubchem_cid",
    }
    for enrich_key, model_field in field_map.items():
        if enrich_key in data and getattr(product, model_field) is None:
            setattr(product, model_field, data[enrich_key])

    db.flush()
    db.refresh(product)
    index_product_record(product)
    return product
