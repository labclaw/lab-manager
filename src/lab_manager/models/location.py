"""Storage location model."""

from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.equipment import Equipment
    from lab_manager.models.inventory import InventoryItem


class StorageLocation(AuditMixin, table=True):
    __tablename__ = "locations"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    room: Optional[str] = Field(default=None, max_length=100)
    building: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[int] = Field(default=None)
    description: Optional[str] = Field(default=None)
    parent_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer,
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
            index=True,
        ),
    )
    level: str = Field(default="room", max_length=50)
    path: Optional[str] = Field(default=None, max_length=1000)

    inventory_items: List["InventoryItem"] = Relationship(back_populates="location")
    equipment: List["Equipment"] = Relationship(back_populates="location")
    children: List["StorageLocation"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"foreign_keys": "[StorageLocation.parent_id]"},
    )
    parent: Optional["StorageLocation"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "[StorageLocation.id]",
            "foreign_keys": "[StorageLocation.parent_id]",
        },
    )
