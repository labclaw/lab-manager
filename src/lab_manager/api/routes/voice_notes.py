"""Voice note CRUD endpoints — upload, list, transcribe."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, paginate
from lab_manager.models.voice_note import VoiceNote

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/webm",
    "audio/x-m4a",
    "audio/mp4",
}
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB

_VALID_STATUSES = {"pending", "transcribed", "reviewed", "archived"}

_SORTABLE = {"id", "created_at", "updated_at", "status", "staff_id"}


class VoiceNoteUpdate(BaseModel):
    transcript: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {_VALID_STATUSES}")
        return v


@router.post("/", status_code=201)
def create_voice_note(
    file: UploadFile,
    staff_id: int = Query(...),
    duration_seconds: Optional[float] = Query(None),
    tags: Optional[str] = Query(None),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Upload an audio file and create a voice note record."""
    if file.content_type not in _ALLOWED_AUDIO_TYPES:
        return JSONResponse(
            status_code=400,
            content={
                "detail": f"File type '{file.content_type}' not allowed. "
                f"Accepted: {', '.join(sorted(_ALLOWED_AUDIO_TYPES))}"
            },
        )

    content = file.file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={
                "detail": f"File too large ({len(content)} bytes). "
                f"Maximum: {_MAX_UPLOAD_BYTES} bytes (100 MB)."
            },
        )

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    usec = f"{now.microsecond:06d}"
    raw_name = file.filename or "voice_note"
    safe_name = raw_name.replace("/", "_").replace("\\", "_").replace("\x00", "")
    safe_name = re.sub(r"[^\w.\-]", "_", safe_name, flags=re.UNICODE)
    if not safe_name or safe_name.startswith("."):
        safe_name = "voice_note" + safe_name
    saved_name = f"{timestamp}_{usec}_{safe_name}"

    upload_dir = Path(
        getattr(
            request.app.state,
            "upload_dir",
            Path("/tmp/lab-manager-uploads").resolve(),
        )
    )
    voice_dir = upload_dir / "voice_notes"
    voice_dir.mkdir(parents=True, exist_ok=True)
    dest = voice_dir / saved_name
    dest.write_bytes(content)

    logger.info("Uploaded voice note %s (%d bytes)", saved_name, len(content))

    note = VoiceNote(
        staff_id=staff_id,
        audio_file=str(dest),
        duration_seconds=duration_seconds,
        tags=tags,
        status="pending",
    )
    db.add(note)
    db.flush()
    db.refresh(note)
    return note


@router.get("/")
def list_voice_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    staff_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """List voice notes with optional filtering."""
    q = select(VoiceNote)
    if staff_id is not None:
        q = q.where(VoiceNote.staff_id == staff_id)
    if status:
        q = q.where(VoiceNote.status == status)
    q = apply_sort(q, VoiceNote, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.get("/{note_id}")
def get_voice_note(note_id: int, db: Session = Depends(get_db)):
    """Get a single voice note by ID."""
    return get_or_404(db, VoiceNote, note_id, "VoiceNote")


@router.patch("/{note_id}")
def update_voice_note(
    note_id: int, body: VoiceNoteUpdate, db: Session = Depends(get_db)
):
    """Update transcript, tags, or status of a voice note."""
    note = get_or_404(db, VoiceNote, note_id, "VoiceNote")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(note, key, value)
    db.flush()
    db.refresh(note)
    return note


@router.post("/{note_id}/transcribe")
def transcribe_voice_note(note_id: int, db: Session = Depends(get_db)):
    """Trigger transcription of a voice note.

    Placeholder: returns a mock transcript. Real ASR integration comes later.
    """
    note = get_or_404(db, VoiceNote, note_id, "VoiceNote")

    if note.status not in ("pending", "transcribed"):
        return JSONResponse(
            status_code=409,
            content={
                "detail": f"Cannot transcribe voice note in status '{note.status}'"
            },
        )

    # Placeholder transcription — will be replaced with real ASR later
    mock_transcript = (
        f"[Placeholder transcript for voice note {note.id}] "
        f"Duration: {note.duration_seconds or 'unknown'} seconds. "
        "Real ASR integration will be added in a future release."
    )

    note.transcript = mock_transcript
    note.status = "transcribed"
    db.flush()
    db.refresh(note)
    return note
