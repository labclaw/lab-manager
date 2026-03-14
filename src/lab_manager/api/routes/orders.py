"""Order CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.order import Order

router = APIRouter()


@router.get("/")
def list_orders(db: Session = Depends(get_db)):
    return db.query(Order).all()


@router.post("/", status_code=201)
def create_order(order: Order, db: Session = Depends(get_db)):
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
