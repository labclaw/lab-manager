"""Inventory CRUD endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.inventory import InventoryItem

router = APIRouter()


class InventoryItemCreate(BaseModel):
    product_id: Optional[int] = None
    location_id: Optional[int] = None
    lot_number: Optional[str] = None
    quantity_on_hand: float = 0
    unit: Optional[str] = None
    expiry_date: Optional[date] = None
    opened_date: Optional[date] = None
    status: str = "available"
    notes: Optional[str] = None
    received_by: Optional[str] = None
    order_item_id: Optional[int] = None


@router.get("/")
def list_inventory(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(InventoryItem).offset(skip).limit(limit).all()


@router.post("/", status_code=201)
def create_inventory_item(body: InventoryItemCreate, db: Session = Depends(get_db)):
    item = InventoryItem(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}")
def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item
