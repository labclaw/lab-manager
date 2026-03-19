"""Storage location model."""

from typing import TYPE_CHECKING, List, Optional

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

    inventory_items: List["InventoryItem"] = Relationship(back_populates="location")
    equipment: List["Equipment"] = Relationship(back_populates="location")
