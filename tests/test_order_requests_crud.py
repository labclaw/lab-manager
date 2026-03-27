"""CRUD and workflow tests for order_requests endpoint."""

from fastapi.testclient import TestClient


def _create_staff(
    client: TestClient, name: str = "testuser", role: str = "grad_student"
):
    """Helper to create a staff record."""
    r = client.post(
        "/api/v1/staff/", json={"name": name, "role": role, "is_active": True}
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_vendor(client: TestClient, name: str = "TestVendor"):
    """Helper to create a vendor."""
    r = client.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_product(
    client: TestClient,
    vendor_id: int,
    name: str = "TestProduct",
    catalog: str = "CAT-001",
):
    """Helper to create a product."""
    r = client.post(
        "/api/v1/products/",
        json={"name": name, "catalog_number": catalog, "vendor_id": vendor_id},
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestOrderRequestCreate:
    """Tests for POST /api/v1/requests/"""

    def test_create_basic_request(self, client):
        r = client.post(
            "/api/v1/requests/",
            json={
                "description": "Need 50x PBS buffer",
                "quantity": "5",
                "unit": "L",
                "urgency": "normal",
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["status"] == "pending"
        assert data["description"] == "Need 50x PBS buffer"
        assert data["urgency"] == "normal"
        assert data["id"] is not None

    def test_create_urgent_request(self, client):
        r = client.post(
            "/api/v1/requests/",
            json={
                "description": "Urgent reagent",
                "quantity": "1",
                "urgency": "urgent",
            },
        )
        assert r.status_code == 201
        assert r.json()["urgency"] == "urgent"

    def test_create_with_vendor_and_product(self, client):
        vendor = _create_vendor(client)
        product = _create_product(client, vendor["id"])
        r = client.post(
            "/api/v1/requests/",
            json={
                "product_id": product["id"],
                "vendor_id": vendor["id"],
                "description": "Restock antibodies",
                "quantity": "10",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["vendor_id"] == vendor["id"]
        assert data["product_id"] == product["id"]

    def test_create_with_estimated_price(self, client):
        r = client.post(
            "/api/v1/requests/",
            json={
                "description": "Expensive kit",
                "quantity": "1",
                "estimated_price": "500.00",
            },
        )
        assert r.status_code == 201
        assert r.json()["estimated_price"] == "500.0000"

    def test_create_defaults_to_quantity_one(self, client):
        r = client.post(
            "/api/v1/requests/",
            json={"description": "Default qty"},
        )
        assert r.status_code == 201
        assert r.json()["quantity"] == "1.0000"

    def test_create_invalid_quantity_zero(self, client):
        r = client.post(
            "/api/v1/requests/",
            json={"description": "Bad qty", "quantity": "0"},
        )
        assert r.status_code == 422

    def test_create_invalid_quantity_negative(self, client):
        r = client.post(
            "/api/v1/requests/",
            json={"description": "Bad qty", "quantity": "-5"},
        )
        assert r.status_code == 422


class TestOrderRequestList:
    """Tests for GET /api/v1/requests/"""

    def test_list_empty(self, client):
        r = client.get("/api/v1/requests/")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert data["total"] >= 0

    def test_list_after_create(self, client):
        client.post(
            "/api/v1/requests/",
            json={"description": "Item 1", "quantity": "1"},
        )
        client.post(
            "/api/v1/requests/",
            json={"description": "Item 2", "quantity": "2"},
        )
        r = client.get("/api/v1/requests/")
        assert r.status_code == 200
        assert r.json()["total"] >= 2

    def test_list_filter_by_status(self, client):
        client.post(
            "/api/v1/requests/",
            json={"description": "Filtered", "quantity": "1"},
        )
        r = client.get("/api/v1/requests/?status=pending")
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["status"] == "pending"

    def test_list_pagination(self, client):
        for i in range(5):
            client.post(
                "/api/v1/requests/",
                json={"description": f"Page item {i}", "quantity": "1"},
            )
        r = client.get("/api/v1/requests/?page=1&page_size=2")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) <= 2
        assert data["page_size"] == 2


class TestOrderRequestStats:
    """Tests for GET /api/v1/requests/stats"""

    def test_stats_empty(self, client):
        r = client.get("/api/v1/requests/stats")
        assert r.status_code == 200
        data = r.json()
        assert "pending" in data
        assert "total" in data

    def test_stats_after_create(self, client):
        client.post(
            "/api/v1/requests/",
            json={"description": "Stats item", "quantity": "1"},
        )
        r = client.get("/api/v1/requests/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["pending"] >= 1


class TestOrderRequestGet:
    """Tests for GET /api/v1/requests/{id}"""

    def test_get_existing(self, client):
        create_r = client.post(
            "/api/v1/requests/",
            json={"description": "Get me", "quantity": "3"},
        )
        req_id = create_r.json()["id"]
        r = client.get(f"/api/v1/requests/{req_id}")
        assert r.status_code == 200
        assert r.json()["description"] == "Get me"

    def test_get_nonexistent(self, client):
        r = client.get("/api/v1/requests/99999")
        assert r.status_code == 404


class TestOrderRequestCancel:
    """Tests for POST /api/v1/requests/{id}/cancel"""

    def test_cancel_own_request(self, client):
        create_r = client.post(
            "/api/v1/requests/",
            json={"description": "Cancel me", "quantity": "1"},
        )
        req_id = create_r.json()["id"]
        r = client.post(f"/api/v1/requests/{req_id}/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_cancel_nonexistent(self, client):
        r = client.post("/api/v1/requests/99999/cancel")
        assert r.status_code == 404
