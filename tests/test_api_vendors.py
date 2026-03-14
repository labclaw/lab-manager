"""Test vendor API endpoints."""


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_vendor(client):
    resp = client.post("/api/vendors/", json={"name": "Sigma-Aldrich"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Sigma-Aldrich"


def test_list_vendors(client):
    client.post("/api/vendors/", json={"name": "Sigma"})
    resp = client.get("/api/vendors/")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data
    assert len(data["items"]) >= 1


def test_get_vendor_not_found(client):
    resp = client.get("/api/vendors/999")
    assert resp.status_code == 404
