"""Storage location model."""

from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.inventory import InventoryItem


class StorageLocation(AuditMixin, table=True):
    __tablename__ = "locations"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    room: str | None = Field(default=None, max_length=100)
    building: str | None = Field(default=None, max_length=100)
    temperature: int | None = Field(default=None)
    description: str | None = Field(default=None)

    inventory_items: list["InventoryItem"] = Relationship(back_populates="location")
