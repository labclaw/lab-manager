"""Device API endpoint tests — heartbeat, list, detail, offline."""

from __future__ import annotations

import uuid


def _heartbeat_payload(**overrides):
    """Build a default heartbeat payload with optional overrides."""
    base = {
        "device_id": str(uuid.uuid4()),
        "hostname": "shen-6604b-c1",
        "ip_address": "192.168.1.100",
        "tailscale_ip": "100.105.226.46",
        "platform": "windows",
        "os_version": "10",
        "tailscale_online": True,
        "tailscale_exit_node": False,
        "metrics": {
            "cpu_percent": 45.2,
            "memory_percent": 62.1,
            "memory_total_mb": 32768,
            "disk_percent": 73.5,
            "disk_total_gb": 512,
        },
    }
    base.update(overrides)
    return base


# --- Heartbeat: Create ---


def test_heartbeat_creates_device(client):
    payload = _heartbeat_payload()
    r = client.post("/api/v1/devices/heartbeat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["device_id"] == payload["device_id"]
    assert data["hostname"] == "shen-6604b-c1"
    assert data["status"] == "online"
    assert data["tailscale_online"] is True
    assert data["cpu_percent"] == 45.2
    assert data["memory_percent"] == 62.1
    assert data["id"] is not None


# --- Heartbeat: Update (upsert) ---


def test_heartbeat_updates_existing_device(client):
    payload = _heartbeat_payload()
    r1 = client.post("/api/v1/devices/heartbeat", json=payload)
    assert r1.status_code == 200
    device_id = r1.json()["id"]

    # Send second heartbeat with updated metrics
    payload["hostname"] = "shen-6604b-c1-updated"
    payload["metrics"]["cpu_percent"] = 88.0
    r2 = client.post("/api/v1/devices/heartbeat", json=payload)
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == device_id
    assert data["hostname"] == "shen-6604b-c1-updated"
    assert data["cpu_percent"] == 88.0
    assert data["status"] == "online"


def test_heartbeat_without_metrics(client):
    payload = _heartbeat_payload()
    del payload["metrics"]
    r = client.post("/api/v1/devices/heartbeat", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["cpu_percent"] is None
    assert data["memory_percent"] is None


# --- List ---


def test_list_devices(client):
    for i in range(3):
        client.post(
            "/api/v1/devices/heartbeat",
            json=_heartbeat_payload(
                device_id=str(uuid.uuid4()),
                hostname=f"host-{i}",
            ),
        )
    r = client.get("/api/v1/devices/")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_list_devices_filter_by_status(client):
    # Create two devices
    client.post(
        "/api/v1/devices/heartbeat",
        json=_heartbeat_payload(device_id=str(uuid.uuid4()), hostname="online-host"),
    )
    r2 = client.post(
        "/api/v1/devices/heartbeat",
        json=_heartbeat_payload(device_id=str(uuid.uuid4()), hostname="offline-host"),
    )
    # Mark second as offline
    client.post(f"/api/v1/devices/{r2.json()['id']}/offline")

    r = client.get("/api/v1/devices/?status=online")
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["hostname"] == "online-host"

    r = client.get("/api/v1/devices/?status=offline")
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["hostname"] == "offline-host"


def test_list_devices_search(client):
    client.post(
        "/api/v1/devices/heartbeat",
        json=_heartbeat_payload(
            device_id=str(uuid.uuid4()), hostname="shen-workstation"
        ),
    )
    client.post(
        "/api/v1/devices/heartbeat",
        json=_heartbeat_payload(device_id=str(uuid.uuid4()), hostname="feng-laptop"),
    )
    r = client.get("/api/v1/devices/?search=shen")
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["hostname"] == "shen-workstation"


# --- Detail ---


def test_get_device(client):
    r = client.post(
        "/api/v1/devices/heartbeat",
        json=_heartbeat_payload(device_id="test-uuid-001", hostname="detail-host"),
    )
    did = r.json()["id"]
    r = client.get(f"/api/v1/devices/{did}")
    assert r.status_code == 200
    assert r.json()["device_id"] == "test-uuid-001"
    assert r.json()["hostname"] == "detail-host"


def test_get_device_404(client):
    r = client.get("/api/v1/devices/99999")
    assert r.status_code == 404


# --- Update metadata ---


def test_update_device_notes(client):
    r = client.post(
        "/api/v1/devices/heartbeat",
        json=_heartbeat_payload(device_id=str(uuid.uuid4()), hostname="note-host"),
    )
    did = r.json()["id"]
    r = client.patch(
        f"/api/v1/devices/{did}",
        json={"notes": "Main workstation in room 604B"},
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "Main workstation in room 604B"


def test_update_device_extra(client):
    r = client.post(
        "/api/v1/devices/heartbeat",
        json=_heartbeat_payload(device_id=str(uuid.uuid4()), hostname="extra-host"),
    )
    did = r.json()["id"]
    r = client.patch(
        f"/api/v1/devices/{did}",
        json={"extra": {"gpu": "RTX 5090", "cuda_version": "12.8"}},
    )
    assert r.status_code == 200
    assert r.json()["extra"]["gpu"] == "RTX 5090"


# --- Offline ---


def test_mark_offline(client):
    r = client.post(
        "/api/v1/devices/heartbeat",
        json=_heartbeat_payload(device_id=str(uuid.uuid4()), hostname="off-host"),
    )
    did = r.json()["id"]
    assert r.json()["status"] == "online"

    r = client.post(f"/api/v1/devices/{did}/offline")
    assert r.status_code == 200
    assert r.json()["status"] == "offline"


def test_mark_offline_404(client):
    r = client.post("/api/v1/devices/99999/offline")
    assert r.status_code == 404


# --- Pagination ---


def test_list_pagination(client):
    for i in range(5):
        client.post(
            "/api/v1/devices/heartbeat",
            json=_heartbeat_payload(
                device_id=str(uuid.uuid4()), hostname=f"pag-host-{i}"
            ),
        )
    r = client.get("/api/v1/devices/?page=1&page_size=2")
    data = r.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5
