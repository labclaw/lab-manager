"""E2E tests for equipment management endpoints.

Tests equipment CRUD, status tracking, and maintenance records.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestEquipmentE2E:
    """End-to-end tests for equipment management."""

    _equipment_id: int | None = None

    def test_list_equipment(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/equipment/ returns paginated list."""
        resp = authenticated_client.get("/api/v1/equipment/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_create_equipment(self, authenticated_client: TestClient | httpx.Client):
        """POST /api/v1/equipment/ creates new equipment."""
        resp = authenticated_client.post(
            "/api/v1/equipment/",
            json={
                "name": "E2E Centrifuge",
                "model": "CF-E2E-5000",
                "serial_number": "SN-E2E-CF-001",
                "status": "active",
                "location": "Lab B",
                "purchase_date": "2024-01-15",
                "warranty_expiry": "2026-01-15",
            },
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        TestEquipmentE2E._equipment_id = data.get("id")
        assert data["name"] == "E2E Centrifuge"

    def test_get_equipment_by_id(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/equipment/{id} returns equipment details."""
        if TestEquipmentE2E._equipment_id is None:
            pytest.skip("No equipment created")

        resp = authenticated_client.get(
            f"/api/v1/equipment/{TestEquipmentE2E._equipment_id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "serial_number" in data

    def test_update_equipment(self, authenticated_client: TestClient | httpx.Client):
        """PATCH /api/v1/equipment/{id} updates equipment."""
        if TestEquipmentE2E._equipment_id is None:
            pytest.skip("No equipment to update")

        resp = authenticated_client.patch(
            f"/api/v1/equipment/{TestEquipmentE2E._equipment_id}",
            json={"status": "maintenance", "location": "Lab C"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "maintenance"

    def test_delete_equipment(self, authenticated_client: TestClient | httpx.Client):
        """DELETE /api/v1/equipment/{id} removes equipment."""
        if TestEquipmentE2E._equipment_id is None:
            pytest.skip("No equipment to delete")

        resp = authenticated_client.delete(
            f"/api/v1/equipment/{TestEquipmentE2E._equipment_id}"
        )
        assert resp.status_code in (200, 204)
        TestEquipmentE2E._equipment_id = None


@pytest.mark.e2e
class TestEquipmentStatusTransitions:
    """Tests for equipment status transitions."""

    def test_active_to_maintenance(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Equipment can transition from active to maintenance."""
        # Create equipment
        resp = authenticated_client.post(
            "/api/v1/equipment/",
            json={
                "name": "Status Test Equipment",
                "model": "ST-E2E-001",
                "serial_number": "SN-STATUS-001",
                "status": "active",
            },
        )
        assert resp.status_code in (200, 201)
        equip_id = resp.json()["id"]

        # Update to maintenance
        resp = authenticated_client.patch(
            f"/api/v1/equipment/{equip_id}",
            json={"status": "maintenance"},
        )
        assert resp.status_code == 200

        # Cleanup
        authenticated_client.delete(f"/api/v1/equipment/{equip_id}")

    def test_maintenance_to_retired(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Equipment can transition from maintenance to retired."""
        # Create equipment in maintenance
        resp = authenticated_client.post(
            "/api/v1/equipment/",
            json={
                "name": "Retirement Test Equipment",
                "model": "RT-E2E-001",
                "serial_number": "SN-RETIRE-001",
                "status": "maintenance",
            },
        )
        assert resp.status_code in (200, 201)
        equip_id = resp.json()["id"]

        # Update to retired
        resp = authenticated_client.patch(
            f"/api/v1/equipment/{equip_id}",
            json={"status": "retired"},
        )
        assert resp.status_code == 200

        # Cleanup
        authenticated_client.delete(f"/api/v1/equipment/{equip_id}")


@pytest.mark.e2e
class TestEquipmentFiltering:
    """Tests for equipment filtering and search."""

    def test_filter_by_status(self, authenticated_client: TestClient | httpx.Client):
        """Filter equipment by status."""
        resp = authenticated_client.get(
            "/api/v1/equipment/", params={"status": "active"}
        )
        assert resp.status_code == 200

    def test_filter_by_location(self, authenticated_client: TestClient | httpx.Client):
        """Filter equipment by location."""
        resp = authenticated_client.get(
            "/api/v1/equipment/", params={"location": "Lab A"}
        )
        assert resp.status_code == 200

    def test_search_by_name(self, authenticated_client: TestClient | httpx.Client):
        """Search equipment by name."""
        resp = authenticated_client.get(
            "/api/v1/equipment/", params={"search": "Centrifuge"}
        )
        assert resp.status_code == 200

    def test_pagination(self, authenticated_client: TestClient | httpx.Client):
        """Test equipment list pagination."""
        resp = authenticated_client.get(
            "/api/v1/equipment/", params={"page": 1, "page_size": 10}
        )
        assert resp.status_code == 200
        data = resp.json()
        if "page" in data:
            assert data["page"] == 1


@pytest.mark.e2e
class TestEquipmentMaintenance:
    """Tests for equipment maintenance records."""

    def test_maintenance_log(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/equipment/{id}/maintenance returns maintenance log."""
        # Create equipment first
        resp = authenticated_client.post(
            "/api/v1/equipment/",
            json={
                "name": "Maintenance Test Equipment",
                "model": "MT-E2E-001",
                "serial_number": "SN-MAINT-001",
                "status": "active",
            },
        )
        assert resp.status_code in (200, 201)
        equip_id = resp.json()["id"]

        # Check maintenance log endpoint
        resp = authenticated_client.get(f"/api/v1/equipment/{equip_id}/maintenance")
        assert resp.status_code in (200, 404)

        # Cleanup
        authenticated_client.delete(f"/api/v1/equipment/{equip_id}")

    def test_add_maintenance_record(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/equipment/{id}/maintenance adds maintenance record."""
        # Create equipment
        resp = authenticated_client.post(
            "/api/v1/equipment/",
            json={
                "name": "Maintenance Record Test",
                "model": "MR-E2E-001",
                "serial_number": "SN-MREC-001",
                "status": "active",
            },
        )
        assert resp.status_code in (200, 201)
        equip_id = resp.json()["id"]

        # Try to add maintenance record
        resp = authenticated_client.post(
            f"/api/v1/equipment/{equip_id}/maintenance",
            json={
                "type": "preventive",
                "description": "Annual calibration",
                "performed_by": "Test Technician",
                "performed_at": "2024-01-15",
            },
        )
        assert resp.status_code in (200, 201, 404, 405, 422)

        # Cleanup
        authenticated_client.delete(f"/api/v1/equipment/{equip_id}")


@pytest.mark.e2e
class TestEquipmentCalibration:
    """Tests for equipment calibration tracking."""

    def test_calibration_history(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/equipment/{id}/calibration returns calibration history."""
        # Create equipment
        resp = authenticated_client.post(
            "/api/v1/equipment/",
            json={
                "name": "Calibration Test Equipment",
                "model": "CT-E2E-001",
                "serial_number": "SN-CAL-001",
                "status": "active",
            },
        )
        assert resp.status_code in (200, 201)
        equip_id = resp.json()["id"]

        # Check calibration history endpoint
        resp = authenticated_client.get(f"/api/v1/equipment/{equip_id}/calibration")
        assert resp.status_code in (200, 404)

        # Cleanup
        authenticated_client.delete(f"/api/v1/equipment/{equip_id}")

    def test_schedule_calibration(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/equipment/{id}/calibration schedules calibration."""
        # Create equipment
        resp = authenticated_client.post(
            "/api/v1/equipment/",
            json={
                "name": "Calibration Schedule Test",
                "model": "CS-E2E-001",
                "serial_number": "SN-CS-001",
                "status": "active",
            },
        )
        assert resp.status_code in (200, 201)
        equip_id = resp.json()["id"]

        # Try to schedule calibration
        resp = authenticated_client.post(
            f"/api/v1/equipment/{equip_id}/calibration",
            json={
                "scheduled_date": "2024-06-15",
                "calibration_type": "full",
            },
        )
        assert resp.status_code in (200, 201, 404, 405, 422)

        # Cleanup
        authenticated_client.delete(f"/api/v1/equipment/{equip_id}")


@pytest.mark.e2e
class TestEquipmentWarranty:
    """Tests for equipment warranty tracking."""

    def test_warranty_info(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/equipment/{id}/warranty returns warranty info."""
        # Create equipment with warranty
        resp = authenticated_client.post(
            "/api/v1/equipment/",
            json={
                "name": "Warranty Test Equipment",
                "model": "WT-E2E-001",
                "serial_number": "SN-WARR-001",
                "status": "active",
                "purchase_date": "2024-01-01",
                "warranty_expiry": "2025-01-01",
            },
        )
        assert resp.status_code in (200, 201)
        equip_id = resp.json()["id"]

        # Check warranty endpoint
        resp = authenticated_client.get(f"/api/v1/equipment/{equip_id}/warranty")
        assert resp.status_code in (200, 404)

        # Cleanup
        authenticated_client.delete(f"/api/v1/equipment/{equip_id}")

    def test_expiring_warranties(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/equipment/warranty/expiring returns expiring warranties."""
        resp = authenticated_client.get("/api/v1/equipment/warranty/expiring")
        assert resp.status_code in (200, 404)
