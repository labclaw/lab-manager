"""Equipment / lab device model."""

from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import Column
from sqlmodel import Field, Relationship

from lab_manager.models.base import AuditMixin

if TYPE_CHECKING:
    from lab_manager.models.location import StorageLocation


class EquipmentStatus:
    active = "active"
    maintenance = "maintenance"
    broken = "broken"
    retired = "retired"
    decommissioned = "decommissioned"
    deleted = "deleted"


VALID_EQUIPMENT_STATUSES = (
    EquipmentStatus.active,
    EquipmentStatus.maintenance,
    EquipmentStatus.broken,
    EquipmentStatus.retired,
    EquipmentStatus.decommissioned,
    EquipmentStatus.deleted,
)


class Equipment(AuditMixin, table=True):
    __tablename__ = "equipment"
    __table_args__ = (
        sa.CheckConstraint(
            f"status IN ({','.join(repr(value) for value in VALID_EQUIPMENT_STATUSES)})",
            name="ck_equipment_status",
        ),
        sa.CheckConstraint(
            "estimated_value IS NULL OR estimated_value >= 0",
            name="ck_equipment_estimated_value_nonneg",
        ),
        sa.UniqueConstraint(
            "manufacturer", "serial_number", name="uq_equipment_manufacturer_serial"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=500, index=True)
    manufacturer: Optional[str] = Field(default=None, max_length=255, index=True)
    model: Optional[str] = Field(default=None, max_length=255)
    serial_number: Optional[str] = Field(default=None, max_length=255)
    system_id: Optional[str] = Field(default=None, max_length=100, index=True)
    category: Optional[str] = Field(default=None, max_length=100, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(sa.Text))
    location_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            sa.Integer, sa.ForeignKey("locations.id", ondelete="SET NULL"), index=True
        ),
    )
    room: Optional[str] = Field(default=None, max_length=100)
    estimated_value: Optional[Decimal] = Field(
        default=None, sa_column=Column(sa.Numeric(12, 2))
    )
    status: str = Field(default=EquipmentStatus.active, max_length=30, index=True)
    is_api_controllable: bool = Field(default=False)
    api_interface: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, sa_column=Column(sa.Text))
    photos: list = Field(default_factory=list, sa_column=Column(sa.JSON))
    extracted_data: Optional[dict] = Field(default=None, sa_column=Column(sa.JSON))
    extra: dict = Field(default_factory=dict, sa_column=Column(sa.JSON))

    location: Optional["StorageLocation"] = Relationship(back_populates="equipment")
