"""Device management endpoints — heartbeat, status, CRUD."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, paginate
from lab_manager.models.device import Device, DeviceStatus

router = APIRouter()

_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "hostname",
    "status",
    "last_heartbeat_at",
}


# --- Schemas ---


class HeartbeatMetrics(BaseModel):
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_total_mb: Optional[float] = None
    disk_percent: Optional[float] = None
    disk_total_gb: Optional[float] = None


class HeartbeatPayload(BaseModel):
    device_id: str = Field(max_length=100)
    hostname: str = Field(max_length=255)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    tailscale_ip: Optional[str] = Field(default=None, max_length=45)
    platform: Optional[str] = Field(default=None, max_length=50)
    os_version: Optional[str] = Field(default=None, max_length=100)
    tailscale_online: bool = False
    tailscale_exit_node: bool = False
    metrics: Optional[HeartbeatMetrics] = None


class DeviceUpdate(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=5000)
    extra: Optional[dict] = None


# --- Endpoints ---


@router.post(
    "/heartbeat",
    status_code=200,
    dependencies=[Depends(require_permission("manage_devices"))],
)
def heartbeat(body: HeartbeatPayload, db: Session = Depends(get_db)):
    """Receive heartbeat from device daemon. Upsert device record."""
    now = datetime.now(timezone.utc)
    device = db.scalars(
        select(Device).where(Device.device_id == body.device_id)
    ).first()

    if device is None:
        device = Device(
            device_id=body.device_id,
            hostname=body.hostname,
            ip_address=body.ip_address,
            tailscale_ip=body.tailscale_ip,
            platform=body.platform,
            os_version=body.os_version,
            status=DeviceStatus.online,
            tailscale_online=body.tailscale_online,
            tailscale_exit_node=body.tailscale_exit_node,
            last_heartbeat_at=now,
        )
        if body.metrics:
            device.cpu_percent = body.metrics.cpu_percent
            device.memory_percent = body.metrics.memory_percent
            device.memory_total_mb = body.metrics.memory_total_mb
            device.disk_percent = body.metrics.disk_percent
            device.disk_total_gb = body.metrics.disk_total_gb
        db.add(device)
        db.flush()
        db.refresh(device)
        return device

    # Update existing device
    device.hostname = body.hostname
    device.ip_address = body.ip_address
    device.tailscale_ip = body.tailscale_ip
    device.platform = body.platform
    device.os_version = body.os_version
    device.tailscale_online = body.tailscale_online
    device.tailscale_exit_node = body.tailscale_exit_node
    device.status = DeviceStatus.online
    device.last_heartbeat_at = now
    if body.metrics:
        device.cpu_percent = body.metrics.cpu_percent
        device.memory_percent = body.metrics.memory_percent
        device.memory_total_mb = body.metrics.memory_total_mb
        device.disk_percent = body.metrics.disk_percent
        device.disk_total_gb = body.metrics.disk_total_gb
    db.flush()
    db.refresh(device)
    return device


@router.get("/", dependencies=[Depends(require_permission("view_equipment"))])
def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("last_heartbeat_at"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    from lab_manager.api.pagination import ilike_col

    q = select(Device)
    if status:
        q = q.where(Device.status == status)
    if search:
        q = q.where(
            ilike_col(Device.hostname, search)
            | ilike_col(Device.device_id, search)
            | ilike_col(Device.ip_address, search)
            | ilike_col(Device.tailscale_ip, search)
        )
    q = apply_sort(q, Device, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.get(
    "/{device_id}", dependencies=[Depends(require_permission("view_equipment"))]
)
def get_device(device_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Device, device_id, "Device")


@router.patch(
    "/{device_id}", dependencies=[Depends(require_permission("manage_devices"))]
)
def update_device(device_id: int, body: DeviceUpdate, db: Session = Depends(get_db)):
    device = get_or_404(db, Device, device_id, "Device")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    db.flush()
    db.refresh(device)
    return device


@router.post(
    "/{device_id}/offline",
    status_code=200,
    dependencies=[Depends(require_permission("manage_devices"))],
)
def mark_offline(device_id: int, db: Session = Depends(get_db)):
    device = get_or_404(db, Device, device_id, "Device")
    device.status = DeviceStatus.offline
    db.flush()
    db.refresh(device)
    return device
