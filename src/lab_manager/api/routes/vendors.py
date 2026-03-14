"""Vendor CRUD endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.vendor import Vendor

router = APIRouter()


class VendorCreate(BaseModel):
    name: str
    aliases: list[str] = []
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


@router.get("/")
def list_vendors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Vendor).offset(skip).limit(limit).all()


@router.post("/", status_code=201)
def create_vendor(body: VendorCreate, db: Session = Depends(get_db)):
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor
