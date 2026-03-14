"""Order CRUD endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.order import Order

router = APIRouter()


class OrderCreate(BaseModel):
    po_number: Optional[str] = None
    vendor_id: Optional[int] = None
    order_date: Optional[date] = None
    ship_date: Optional[date] = None
    received_date: Optional[date] = None
    received_by: Optional[str] = None
    status: str = "pending"
    delivery_number: Optional[str] = None
    invoice_number: Optional[str] = None
    document_id: Optional[int] = None
    extra: dict = {}


@router.get("/")
def list_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Order).offset(skip).limit(limit).all()


@router.post("/", status_code=201)
def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    order = Order(**body.model_dump())
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
