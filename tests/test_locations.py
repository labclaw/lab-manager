"""Storage location API tests with hierarchy support."""

from __future__ import annotations


def test_create_location(client):
    r = client.post(
        "/api/v1/locations/",
        json={"name": "Room 101", "building": "Main", "level": "room"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Room 101"
    assert data["level"] == "room"
    assert data["path"] == "Room 101"
    assert data["parent_id"] is None


def test_create_child_location(client):
    r1 = client.post(
        "/api/v1/locations/",
        json={"name": "Cold Room", "level": "room"},
    )
    parent_id = r1.json()["id"]

    r2 = client.post(
        "/api/v1/locations/",
        json={"name": "Freezer A", "level": "freezer", "parent_id": parent_id},
    )
    assert r2.status_code == 201
    data = r2.json()
    assert data["parent_id"] == parent_id
    assert data["path"] == "Cold Room > Freezer A"


def test_deep_hierarchy(client):
    r1 = client.post("/api/v1/locations/", json={"name": "Building A", "level": "building"})
    r2 = client.post(
        "/api/v1/locations/",
        json={"name": "Room 1", "level": "room", "parent_id": r1.json()["id"]},
    )
    r3 = client.post(
        "/api/v1/locations/",
        json={"name": "Shelf 3", "level": "shelf", "parent_id": r2.json()["id"]},
    )
    r4 = client.post(
        "/api/v1/locations/",
        json={"name": "Box 7", "level": "box", "parent_id": r3.json()["id"]},
    )
    assert r4.json()["path"] == "Building A > Room 1 > Shelf 3 > Box 7"


def test_get_location(client):
    r = client.post("/api/v1/locations/", json={"name": "Lab 1"})
    lid = r.json()["id"]
    r = client.get(f"/api/v1/locations/{lid}")
    assert r.status_code == 200
    assert r.json()["name"] == "Lab 1"


def test_get_location_404(client):
    r = client.get("/api/v1/locations/99999")
    assert r.status_code == 404


def test_update_location(client):
    r = client.post("/api/v1/locations/", json={"name": "Old Name"})
    lid = r.json()["id"]
    r = client.patch(f"/api/v1/locations/{lid}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_delete_reparents_children(client):
    r1 = client.post("/api/v1/locations/", json={"name": "Root"})
    r2 = client.post(
        "/api/v1/locations/",
        json={"name": "Middle", "parent_id": r1.json()["id"]},
    )
    r3 = client.post(
        "/api/v1/locations/",
        json={"name": "Leaf", "parent_id": r2.json()["id"]},
    )
    # Delete middle — leaf should be reparented to root
    r = client.delete(f"/api/v1/locations/{r2.json()['id']}")
    assert r.status_code == 200
    assert r.json()["children_reparented"] == 1

    leaf = client.get(f"/api/v1/locations/{r3.json()['id']}").json()
    assert leaf["parent_id"] == r1.json()["id"]


def test_list_locations(client):
    client.post("/api/v1/locations/", json={"name": "A", "level": "room"})
    client.post("/api/v1/locations/", json={"name": "B", "level": "freezer"})
    r = client.get("/api/v1/locations/")
    assert r.json()["total"] >= 2


def test_filter_by_level(client):
    client.post("/api/v1/locations/", json={"name": "R1", "level": "room"})
    client.post("/api/v1/locations/", json={"name": "F1", "level": "freezer"})
    r = client.get("/api/v1/locations/?level=freezer")
    items = r.json()["items"]
    assert all(i["level"] == "freezer" for i in items)


def test_location_tree(client):
    r1 = client.post("/api/v1/locations/", json={"name": "Root"})
    client.post(
        "/api/v1/locations/",
        json={"name": "Child", "parent_id": r1.json()["id"]},
    )
    r = client.get("/api/v1/locations/tree")
    assert r.status_code == 200
    tree = r.json()["tree"]
    assert len(tree) >= 1
    root = next(n for n in tree if n["name"] == "Root")
    assert len(root["children"]) == 1
    assert root["children"][0]["name"] == "Child"


def test_get_children(client):
    r1 = client.post("/api/v1/locations/", json={"name": "Parent"})
    pid = r1.json()["id"]
    client.post("/api/v1/locations/", json={"name": "C1", "parent_id": pid})
    client.post("/api/v1/locations/", json={"name": "C2", "parent_id": pid})
    r = client.get(f"/api/v1/locations/{pid}/children")
    assert r.json()["total"] == 2


def test_invalid_parent_404(client):
    r = client.post(
        "/api/v1/locations/",
        json={"name": "Orphan", "parent_id": 99999},
    )
    assert r.status_code == 404
