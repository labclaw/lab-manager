"""Test vendor API endpoints."""


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_vendor(client):
    resp = client.post("/api/v1/vendors/", json={"name": "Sigma-Aldrich"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Sigma-Aldrich"


def test_list_vendors(client):
    client.post("/api/v1/vendors/", json={"name": "Sigma"})
    resp = client.get("/api/v1/vendors/")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data
    assert len(data["items"]) >= 1


def test_get_vendor_not_found(client):
    resp = client.get("/api/v1/vendors/999")
    assert resp.status_code == 404


def test_create_vendor_empty_name_rejected(client):
    """Empty vendor name should be rejected by validation."""
    resp = client.post("/api/v1/vendors/", json={"name": ""})
    assert resp.status_code == 422


def test_update_vendor_empty_name_rejected(client):
    """Updating vendor name to empty string should be rejected."""
    created = client.post("/api/v1/vendors/", json={"name": "TestVendor"})
    vendor_id = created.json()["id"]
    resp = client.patch(f"/api/v1/vendors/{vendor_id}", json={"name": ""})
    assert resp.status_code == 422
