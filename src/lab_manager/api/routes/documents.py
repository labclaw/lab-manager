"""Document CRUD endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.document import Document

router = APIRouter()


class DocumentCreate(BaseModel):
    file_path: str
    file_name: str
    document_type: Optional[str] = None
    vendor_name: Optional[str] = None
    ocr_text: Optional[str] = None
    extracted_data: Optional[dict] = None
    extraction_model: Optional[str] = None
    extraction_confidence: Optional[float] = None
    status: str = "pending"
    review_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    order_id: Optional[int] = None


@router.get("/")
def list_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Document).offset(skip).limit(limit).all()


@router.post("/", status_code=201)
def create_document(body: DocumentCreate, db: Session = Depends(get_db)):
    document = Document(**body.model_dump())
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
