"""Equipment API endpoint tests — pytest (SQLite)."""

from __future__ import annotations


# --- CRUD ---


def test_create_equipment(client):
    r = client.post(
        "/api/v1/equipment/",
        json={
            "name": "Eppendorf 5702R",
            "category": "centrifuge",
            "manufacturer": "Eppendorf",
            "serial_number": "SN-12345",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Eppendorf 5702R"
    assert data["manufacturer"] == "Eppendorf"
    assert data["status"] == "active"
    assert data["id"] is not None


def test_get_equipment(client):
    r = client.post(
        "/api/v1/equipment/",
        json={"name": "Scope", "category": "microscope"},
    )
    eid = r.json()["id"]
    r = client.get(f"/api/v1/equipment/{eid}")
    assert r.status_code == 200
    assert r.json()["name"] == "Scope"


def test_get_equipment_404(client):
    r = client.get("/api/v1/equipment/99999")
    assert r.status_code == 404


def test_update_equipment(client):
    r = client.post(
        "/api/v1/equipment/",
        json={"name": "Old Name", "category": "general"},
    )
    eid = r.json()["id"]
    r = client.patch(f"/api/v1/equipment/{eid}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_soft_delete_equipment(client):
    r = client.post(
        "/api/v1/equipment/",
        json={"name": "Delete Me", "category": "general"},
    )
    eid = r.json()["id"]
    r = client.delete(f"/api/v1/equipment/{eid}")
    assert r.status_code == 204


def test_deleted_excluded_from_list(client):
    client.post("/api/v1/equipment/", json={"name": "Keep", "category": "a"})
    r2 = client.post("/api/v1/equipment/", json={"name": "Gone", "category": "b"})
    client.delete(f"/api/v1/equipment/{r2.json()['id']}")
    r = client.get("/api/v1/equipment/")
    names = [e["name"] for e in r.json()["items"]]
    assert "Keep" in names
    assert "Gone" not in names


# --- Pagination ---


def test_list_pagination(client):
    for i in range(5):
        client.post("/api/v1/equipment/", json={"name": f"D{i}", "category": "x"})
    r = client.get("/api/v1/equipment/?page=1&page_size=2")
    data = r.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["pages"] == 3


# --- Filtering ---


def test_filter_by_category(client):
    client.post("/api/v1/equipment/", json={"name": "A", "category": "pcr"})
    client.post("/api/v1/equipment/", json={"name": "B", "category": "centrifuge"})
    client.post("/api/v1/equipment/", json={"name": "C", "category": "pcr"})
    r = client.get("/api/v1/equipment/?category=pcr")
    assert len(r.json()["items"]) == 2


def test_filter_by_status(client):
    client.post("/api/v1/equipment/", json={"name": "A", "category": "x"})
    r2 = client.post("/api/v1/equipment/", json={"name": "B", "category": "x"})
    client.patch(f"/api/v1/equipment/{r2.json()['id']}", json={"status": "broken"})
    r = client.get("/api/v1/equipment/?status=broken")
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["name"] == "B"


def test_filter_by_manufacturer(client):
    client.post(
        "/api/v1/equipment/",
        json={"name": "A", "category": "x", "manufacturer": "Bruker"},
    )
    client.post(
        "/api/v1/equipment/",
        json={"name": "B", "category": "x", "manufacturer": "Olympus"},
    )
    r = client.get("/api/v1/equipment/?manufacturer=Bruker")
    assert len(r.json()["items"]) == 1


def test_search(client):
    client.post(
        "/api/v1/equipment/",
        json={"name": "Bruker Two-Photon", "manufacturer": "Bruker"},
    )
    client.post(
        "/api/v1/equipment/",
        json={"name": "Olympus BX", "manufacturer": "Olympus"},
    )
    r = client.get("/api/v1/equipment/?search=Bruker")
    assert len(r.json()["items"]) == 1


# --- Sorting ---


def test_sort_by_name(client):
    client.post("/api/v1/equipment/", json={"name": "Zebra", "category": "x"})
    client.post("/api/v1/equipment/", json={"name": "Alpha", "category": "x"})
    r = client.get("/api/v1/equipment/?sort_by=name&sort_dir=asc")
    names = [e["name"] for e in r.json()["items"]]
    assert names == sorted(names)


# --- Photos & Extracted Data ---


def test_photos_json(client):
    r = client.post(
        "/api/v1/equipment/",
        json={
            "name": "Laser",
            "category": "laser",
            "photos": ["/img/a.jpg", "/img/b.jpg"],
        },
    )
    assert r.status_code == 201
    assert len(r.json()["photos"]) == 2


def test_update_photos(client):
    r = client.post(
        "/api/v1/equipment/",
        json={"name": "Laser", "category": "laser"},
    )
    eid = r.json()["id"]
    r = client.patch(
        f"/api/v1/equipment/{eid}",
        json={"photos": ["/img/new.jpg"]},
    )
    assert r.json()["photos"] == ["/img/new.jpg"]


def test_extracted_data_traceability(client):
    extracted = {
        "source_model": "gemini-3.1-flash-preview",
        "extraction_timestamp": "2026-03-17T09:00:00Z",
        "source_photo": "/data/devices/IMG_3488.jpg",
        "raw_fields": {"system_id": "#5010"},
        "confidence": 0.95,
    }
    r = client.post(
        "/api/v1/equipment/",
        json={
            "name": "Bruker System",
            "category": "two-photon",
            "extracted_data": extracted,
        },
    )
    assert r.status_code == 201
    data = r.json()["extracted_data"]
    assert data["source_model"] == "gemini-3.1-flash-preview"
    assert data["source_photo"] == "/data/devices/IMG_3488.jpg"
    assert data["extraction_timestamp"] is not None
