"""Storage location CRUD with hierarchical tree support."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.models.location import StorageLocation

router = APIRouter()

_SORTABLE = {"id", "name", "room", "building", "level", "created_at", "updated_at"}


# ── Schemas ─────────────────────────────────────────────────────────


class LocationCreate(BaseModel):
    name: str = Field(max_length=200)
    room: Optional[str] = Field(default=None, max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[int] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: str = Field(default="room", max_length=50)


class LocationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    room: Optional[str] = Field(default=None, max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[int] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: Optional[str] = Field(default=None, max_length=50)


# ── Helpers ─────────────────────────────────────────────────────────


def _build_path(db: Session, loc: StorageLocation) -> str:
    """Build the materialized path for a location from its ancestors."""
    parts = [loc.name]
    parent_id = loc.parent_id
    seen: set[int] = set()
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        parent = db.get(StorageLocation, parent_id)
        if not parent:
            break
        parts.append(parent.name)
        parent_id = parent.parent_id
    parts.reverse()
    return " > ".join(parts)


def _update_descendant_paths(db: Session, loc: StorageLocation) -> None:
    """Recursively update paths for all descendants after a rename/move."""
    children = db.execute(
        select(StorageLocation).where(StorageLocation.parent_id == loc.id)
    ).scalars().all()
    for child in children:
        child.path = _build_path(db, child)
        _update_descendant_paths(db, child)


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/tree")
def location_tree(db: Session = Depends(get_db)):
    """Return all locations as a nested tree structure."""
    all_locs = db.execute(select(StorageLocation)).scalars().all()
    children_map: dict[int | None, list] = {}
    for loc in all_locs:
        children_map.setdefault(loc.parent_id, []).append(loc)

    def _build_node(loc: StorageLocation) -> dict:
        node = {
            "id": loc.id,
            "name": loc.name,
            "level": loc.level,
            "path": loc.path,
            "room": loc.room,
            "building": loc.building,
            "temperature": loc.temperature,
            "children": [],
        }
        for child in children_map.get(loc.id, []):
            node["children"].append(_build_node(child))
        return node

    roots = children_map.get(None, [])
    return {"tree": [_build_node(r) for r in roots]}


@router.get("/")
def list_locations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    parent_id: Optional[int] = Query(None),
    level: Optional[str] = Query(None),
    building: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(StorageLocation)
    if parent_id is not None:
        q = q.where(StorageLocation.parent_id == parent_id)
    if level:
        q = q.where(StorageLocation.level == level)
    if building:
        q = q.where(ilike_col(StorageLocation.building, building))
    if search:
        q = q.where(
            ilike_col(StorageLocation.name, search)
            | ilike_col(StorageLocation.room, search)
        )
    q = apply_sort(q, StorageLocation, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.post("/", status_code=201)
def create_location(body: LocationCreate, db: Session = Depends(get_db)):
    if body.parent_id is not None:
        get_or_404(db, StorageLocation, body.parent_id, "Parent location")
    loc = StorageLocation(**body.model_dump())
    db.add(loc)
    db.flush()
    loc.path = _build_path(db, loc)
    db.flush()
    db.refresh(loc)
    return loc


@router.get("/{location_id}")
def get_location(location_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, StorageLocation, location_id, "StorageLocation")


@router.patch("/{location_id}")
def update_location(
    location_id: int,
    body: LocationUpdate,
    db: Session = Depends(get_db),
):
    loc = get_or_404(db, StorageLocation, location_id, "StorageLocation")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(loc, key, value)
    loc.path = _build_path(db, loc)
    _update_descendant_paths(db, loc)
    db.flush()
    db.refresh(loc)
    return loc


@router.delete("/{location_id}")
def delete_location(location_id: int, db: Session = Depends(get_db)):
    loc = get_or_404(db, StorageLocation, location_id, "StorageLocation")
    # Reparent children to this location's parent
    children = (
        db.execute(
            select(StorageLocation).where(StorageLocation.parent_id == location_id)
        )
        .scalars()
        .all()
    )
    for child in children:
        child.parent_id = loc.parent_id
        child.path = _build_path(db, child)
        _update_descendant_paths(db, child)
    db.delete(loc)
    db.flush()
    return {"ok": True, "children_reparented": len(children)}


@router.get("/{location_id}/children")
def get_children(location_id: int, db: Session = Depends(get_db)):
    """Get direct children of a location."""
    get_or_404(db, StorageLocation, location_id, "StorageLocation")
    children = (
        db.execute(
            select(StorageLocation).where(StorageLocation.parent_id == location_id)
        )
        .scalars()
        .all()
    )
    return {"items": children, "total": len(children)}
