"""Knowledge base model for SOPs, protocols, safety data, and equipment manuals."""

from __future__ import annotations

import enum
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Column, Text
from sqlmodel import Field

from lab_manager.models.base import AuditMixin


class KnowledgeCategory(str, enum.Enum):
    sop = "sop"
    safety = "safety"
    equipment_manual = "equipment_manual"
    protocol = "protocol"
    troubleshooting = "troubleshooting"
    general = "general"


class KnowledgeEntry(AuditMixin, table=True):
    __tablename__ = "knowledge_entries"
    __table_args__ = (
        sa.CheckConstraint(
            "category IN ('sop','safety','equipment_manual','protocol','troubleshooting','general')",
            name="ck_knowledge_entries_category",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=500, index=True)
    category: str = Field(default="general", max_length=50, index=True)
    content: str = Field(sa_column=Column(Text))
    tags: list = Field(default_factory=list, sa_column=Column(sa.JSON))
    source_type: Optional[str] = Field(default=None, max_length=100)
    source_url: Optional[str] = Field(default=None, max_length=2000)
    is_deleted: bool = Field(default=False, index=True)
