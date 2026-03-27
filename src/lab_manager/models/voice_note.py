"""Voice note model for audio recording and transcription."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class VoiceNote(AuditMixin, table=True):
    __tablename__ = "voice_note"

    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(foreign_key="staff.id", index=True)
    audio_file: Optional[str] = Field(default=None, max_length=500)
    transcript: Optional[str] = Field(default=None)
    duration_seconds: Optional[float] = Field(default=None)
    status: str = Field(default="pending", max_length=20, index=True)
    tags: Optional[str] = Field(default=None, max_length=500)
