"""Electronic Lab Notebook (ELN) CRUD endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.models.eln import ELNAttachment, ELNContentType, ELNEntry, ELNTag

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_CONTENT_TYPES = {ct.value for ct in ELNContentType}
_SORTABLE = {"id", "title", "content_type", "created_at", "updated_at"}


# --- Pydantic schemas ---


class EntryCreate(BaseModel):
    title: str
    content_type: str = ELNContentType.text
    content: Optional[str] = None
    experiment_id: Optional[int] = None
    project_id: Optional[int] = None
    tags: list[str] = []
    tag_ids: list[int] = []

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in _VALID_CONTENT_TYPES:
            raise ValueError(f"content_type must be one of {_VALID_CONTENT_TYPES}")
        return v


class EntryUpdate(BaseModel):
    title: Optional[str] = None
    content_type: Optional[str] = None
    content: Optional[str] = None
    experiment_id: Optional[int] = None
    project_id: Optional[int] = None
    tags: Optional[list[str]] = None
    tag_ids: Optional[list[int]] = None

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_CONTENT_TYPES:
            raise ValueError(f"content_type must be one of {_VALID_CONTENT_TYPES}")
        return v


class AttachmentCreate(BaseModel):
    filename: str
    file_path: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None


class TagCreate(BaseModel):
    name: str
    color: Optional[str] = None


class SearchQuery(BaseModel):
    query: str


# --- Routes ---


def _entry_detail(entry: ELNEntry) -> dict:
    """Serialize entry with eager-loaded relationships."""
    return {
        "id": entry.id,
        "title": entry.title,
        "content_type": entry.content_type,
        "content": entry.content,
        "experiment_id": entry.experiment_id,
        "project_id": entry.project_id,
        "tags_json": entry.tags_json,
        "attachments_json": entry.attachments_json,
        "is_deleted": entry.is_deleted,
        "created_by": entry.created_by,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
        "attachments": [
            {
                "id": a.id,
                "entry_id": a.entry_id,
                "filename": a.filename,
                "file_path": a.file_path,
                "file_type": a.file_type,
                "file_size": a.file_size,
                "uploaded_at": a.uploaded_at,
            }
            for a in entry.attachments
        ],
        "tag_objects": [
            {"id": t.id, "name": t.name, "color": t.color} for t in entry.tag_objects
        ],
    }


@router.get("/tags/")
def list_tags(db: Session = Depends(get_db)):
    """List all tags."""
    tags = db.scalars(select(ELNTag).order_by(ELNTag.name)).all()
    return tags


@router.post("/tags/", status_code=201)
def create_tag(body: TagCreate, db: Session = Depends(get_db)):
    """Create a new tag."""
    from sqlalchemy.exc import IntegrityError

    tag = ELNTag(**body.model_dump())
    db.add(tag)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail=f"Tag '{body.name}' already exists")
    db.refresh(tag)
    return tag


@router.post(
    "/search",
)
def search_entries(body: SearchQuery, db: Session = Depends(get_db)):
    """Full-text search across entry titles and content."""
    pattern = f"%{body.query}%"
    q = (
        select(ELNEntry)
        .where(
            ELNEntry.is_deleted == False,  # noqa: E712
            or_(
                ilike_col(ELNEntry.title, body.query),
                ELNEntry.content.ilike(pattern),
            ),
        )
        .options(selectinload(ELNEntry.attachments), selectinload(ELNEntry.tag_objects))
        .order_by(ELNEntry.created_at.desc())
    )
    results = db.scalars(q).all()
    return {"items": results, "total": len(results)}


@router.post("/", status_code=201)
def create_entry(body: EntryCreate, db: Session = Depends(get_db)):
    """Create a new ELN entry."""
    data = body.model_dump(exclude={"tags", "tag_ids"})
    entry = ELNEntry(**data, tags_json=body.tags)
    db.add(entry)
    db.flush()

    # Attach tag objects by ID
    if body.tag_ids:
        tags = db.scalars(select(ELNTag).where(ELNTag.id.in_(body.tag_ids))).all()
        entry.tag_objects = list(tags)

    db.flush()
    db.refresh(entry)
    return entry


@router.get("/")
def list_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    experiment_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    content_type: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """List entries with filters and pagination."""
    q = select(ELNEntry).where(ELNEntry.is_deleted == False)  # noqa: E712

    if tag:
        q = q.join(ELNEntry.tag_objects).where(ELNTag.name == tag)
    if experiment_id is not None:
        q = q.where(ELNEntry.experiment_id == experiment_id)
    if project_id is not None:
        q = q.where(ELNEntry.project_id == project_id)
    if content_type:
        q = q.where(ELNEntry.content_type == content_type)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            or_(
                ilike_col(ELNEntry.title, search),
                ELNEntry.content.ilike(pattern),
            )
        )

    q = apply_sort(q, ELNEntry, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.get("/{entry_id}")
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    """Get a single entry with attachments and tags."""
    entry = db.scalars(
        select(ELNEntry)
        .where(ELNEntry.id == entry_id, ELNEntry.is_deleted == False)  # noqa: E712
        .options(selectinload(ELNEntry.attachments), selectinload(ELNEntry.tag_objects))
    ).first()
    if not entry:
        from lab_manager.exceptions import NotFoundError

        raise NotFoundError("ELNEntry", entry_id)
    return _entry_detail(entry)


@router.patch("/{entry_id}")
def update_entry(entry_id: int, body: EntryUpdate, db: Session = Depends(get_db)):
    """Update an entry."""
    entry = get_or_404(db, ELNEntry, entry_id, "ELNEntry")
    updates = body.model_dump(exclude_unset=True, exclude={"tags", "tag_ids"})

    if "tags" in body.model_dump(exclude_unset=True):
        updates["tags_json"] = body.tags

    for key, value in updates.items():
        setattr(entry, key, value)

    if body.tag_ids is not None:
        tags = db.scalars(select(ELNTag).where(ELNTag.id.in_(body.tag_ids))).all()
        entry.tag_objects = list(tags)

    db.flush()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    """Soft delete an entry."""
    entry = get_or_404(db, ELNEntry, entry_id, "ELNEntry")
    entry.is_deleted = True
    db.flush()
    return None


@router.post("/{entry_id}/attachments", status_code=201)
def add_attachment(
    entry_id: int, body: AttachmentCreate, db: Session = Depends(get_db)
):
    """Add attachment metadata to an entry."""
    entry = get_or_404(db, ELNEntry, entry_id, "ELNEntry")
    attachment = ELNAttachment(entry_id=entry_id, **body.model_dump())
    db.add(attachment)
    db.flush()

    # Update attachments_json on the entry
    current = list(entry.attachments_json or [])
    current.append(
        {
            "id": attachment.id,
            "filename": attachment.filename,
            "file_type": attachment.file_type,
            "file_size": attachment.file_size,
        }
    )
    entry.attachments_json = current
    db.flush()
    db.refresh(attachment)
    return attachment
