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
    assert len(resp.json()) >= 1


def test_get_vendor_not_found(client):
    resp = client.get("/api/vendors/999")
    assert resp.status_code == 404
