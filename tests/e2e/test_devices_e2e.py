"""E2E tests for device management endpoints.

Tests device heartbeat, listing, retrieval, update, and offline marking.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


@pytest.mark.e2e
class TestDevicesE2E:
    """End-to-end tests for device management."""

    _device_db_id: int | None = None
    _device_uuid: str = str(uuid4())

    @classmethod
    def _ensure_device(
        cls,
        authenticated_client: TestClient | httpx.Client,
    ) -> int:
        """Send a heartbeat to register a device, return DB id."""
        if cls._device_db_id is not None:
            existing = authenticated_client.get(f"/api/v1/devices/{cls._device_db_id}")
            if existing.status_code == 200:
                return cls._device_db_id

        resp = authenticated_client.post(
            "/api/v1/devices/heartbeat",
            json={
                "device_id": cls._device_uuid,
                "hostname": f"e2e-host-{uuid4().hex[:8]}",
                "ip_address": "192.168.1.100",
                "tailscale_ip": "100.64.0.1",
                "platform": "linux",
                "os_version": "Ubuntu 22.04",
                "tailscale_online": True,
                "tailscale_exit_node": False,
                "metrics": {
                    "cpu_percent": 23.5,
                    "memory_percent": 45.2,
                    "memory_total_mb": 16384.0,
                    "disk_percent": 60.1,
                    "disk_total_gb": 500.0,
                },
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        cls._device_db_id = data["id"]
        return cls._device_db_id

    def test_heartbeat_registers_device(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/devices/heartbeat registers or updates a device."""
        resp = authenticated_client.post(
            "/api/v1/devices/heartbeat",
            json={
                "device_id": str(uuid4()),
                "hostname": "e2e-heartbeat-test",
                "ip_address": "10.0.0.1",
                "platform": "linux",
                "os_version": "Debian 12",
                "tailscale_online": True,
                "tailscale_exit_node": False,
                "metrics": {
                    "cpu_percent": 10.0,
                    "memory_percent": 30.0,
                    "memory_total_mb": 8192.0,
                    "disk_percent": 50.0,
                    "disk_total_gb": 256.0,
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["hostname"] == "e2e-heartbeat-test"

    def test_heartbeat_minimal(self, authenticated_client: TestClient | httpx.Client):
        """POST heartbeat with only required fields."""
        resp = authenticated_client.post(
            "/api/v1/devices/heartbeat",
            json={
                "device_id": str(uuid4()),
                "hostname": "e2e-minimal",
            },
        )
        assert resp.status_code == 200

    def test_heartbeat_updates_existing(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Sending heartbeat twice for same device_id updates it."""
        device_id = str(uuid4())
        # First heartbeat
        resp1 = authenticated_client.post(
            "/api/v1/devices/heartbeat",
            json={
                "device_id": device_id,
                "hostname": "e2e-update-test",
                "platform": "linux",
            },
        )
        assert resp1.status_code == 200
        first_id = resp1.json()["id"]

        # Second heartbeat — same device_id, updated metrics
        resp2 = authenticated_client.post(
            "/api/v1/devices/heartbeat",
            json={
                "device_id": device_id,
                "hostname": "e2e-update-test-updated",
                "platform": "linux",
                "metrics": {
                    "cpu_percent": 99.0,
                    "memory_percent": 88.0,
                    "memory_total_mb": 32768.0,
                    "disk_percent": 95.0,
                    "disk_total_gb": 1000.0,
                },
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["id"] == first_id
        assert resp2.json()["hostname"] == "e2e-update-test-updated"

    def test_list_devices(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/devices/ returns paginated list."""
        resp = authenticated_client.get("/api/v1/devices/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_list_devices_with_search(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/devices/?search= filters results."""
        resp = authenticated_client.get("/api/v1/devices/", params={"search": "e2e"})
        assert resp.status_code == 200

    def test_list_devices_pagination(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/devices/ supports pagination params."""
        resp = authenticated_client.get(
            "/api/v1/devices/", params={"page": 1, "page_size": 10}
        )
        assert resp.status_code == 200
        data = resp.json()
        if "page" in data:
            assert data["page"] == 1

    def test_get_device_by_id(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/devices/{id} returns device details."""
        device_id = TestDevicesE2E._ensure_device(authenticated_client)
        resp = authenticated_client.get(f"/api/v1/devices/{device_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "hostname" in data

    def test_get_device_not_found(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/devices/999999 returns 404."""
        resp = authenticated_client.get("/api/v1/devices/999999")
        assert resp.status_code == 404

    def test_update_device(self, authenticated_client: TestClient | httpx.Client):
        """PATCH /api/v1/devices/{id} updates device notes."""
        device_id = TestDevicesE2E._ensure_device(authenticated_client)
        resp = authenticated_client.patch(
            f"/api/v1/devices/{device_id}",
            json={"notes": "E2E updated notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("notes") == "E2E updated notes"

    def test_update_device_with_extra(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH /api/v1/devices/{id} with extra dict."""
        device_id = TestDevicesE2E._ensure_device(authenticated_client)
        resp = authenticated_client.patch(
            f"/api/v1/devices/{device_id}",
            json={"extra": {"rack_position": "A3", "floor": 2}},
        )
        assert resp.status_code == 200

    def test_mark_device_offline(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/devices/{id}/offline marks device as offline."""
        device_id = TestDevicesE2E._ensure_device(authenticated_client)
        resp = authenticated_client.post(f"/api/v1/devices/{device_id}/offline")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "offline"


@pytest.mark.e2e
class TestDevicesFiltering:
    """Tests for device filtering and sorting."""

    def test_filter_by_status(self, authenticated_client: TestClient | httpx.Client):
        """Filter devices by status."""
        resp = authenticated_client.get("/api/v1/devices/", params={"status": "online"})
        assert resp.status_code == 200

    def test_sort_by_hostname(self, authenticated_client: TestClient | httpx.Client):
        """Sort devices by hostname."""
        resp = authenticated_client.get(
            "/api/v1/devices/",
            params={"sort_by": "hostname", "sort_dir": "asc"},
        )
        assert resp.status_code == 200
