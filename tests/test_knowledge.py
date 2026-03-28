"""Knowledge base API endpoint tests."""

from __future__ import annotations


# --- CRUD ---


def test_create_knowledge_entry(client):
    r = client.post(
        "/api/v1/knowledge/",
        json={
            "title": "Lab Safety SOP",
            "category": "sop",
            "content": "Always wear gloves and goggles in the lab.",
            "tags": ["safety", "PPE"],
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Lab Safety SOP"
    assert data["category"] == "sop"
    assert data["tags"] == ["safety", "PPE"]
    assert data["id"] is not None
    assert data["is_deleted"] is False


def test_create_knowledge_entry_default_category(client):
    r = client.post(
        "/api/v1/knowledge/",
        json={
            "title": "General Note",
            "content": "Some general information.",
        },
    )
    assert r.status_code == 201
    assert r.json()["category"] == "general"


def test_create_knowledge_entry_invalid_category(client):
    r = client.post(
        "/api/v1/knowledge/",
        json={
            "title": "Bad",
            "category": "invalid_cat",
            "content": "test",
        },
    )
    assert r.status_code == 422


def test_get_knowledge_entry(client):
    r = client.post(
        "/api/v1/knowledge/",
        json={
            "title": "Chemical Spill Protocol",
            "category": "safety",
            "content": "Evacuate and call EHS.",
        },
    )
    eid = r.json()["id"]
    r = client.get(f"/api/v1/knowledge/{eid}")
    assert r.status_code == 200
    assert r.json()["title"] == "Chemical Spill Protocol"


def test_get_knowledge_entry_404(client):
    r = client.get("/api/v1/knowledge/99999")
    assert r.status_code == 404


def test_update_knowledge_entry(client):
    r = client.post(
        "/api/v1/knowledge/",
        json={"title": "Old Title", "content": "old content"},
    )
    eid = r.json()["id"]
    r = client.patch(
        f"/api/v1/knowledge/{eid}",
        json={"title": "New Title", "content": "updated content"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "New Title"
    assert r.json()["content"] == "updated content"


def test_update_knowledge_entry_partial(client):
    r = client.post(
        "/api/v1/knowledge/",
        json={"title": "Original", "content": "keep me"},
    )
    eid = r.json()["id"]
    r = client.patch(f"/api/v1/knowledge/{eid}", json={"tags": ["updated"]})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Original"
    assert data["content"] == "keep me"
    assert data["tags"] == ["updated"]


def test_soft_delete_knowledge_entry(client):
    r = client.post(
        "/api/v1/knowledge/",
        json={"title": "Delete Me", "content": "bye"},
    )
    eid = r.json()["id"]
    r = client.delete(f"/api/v1/knowledge/{eid}")
    assert r.status_code == 204


def test_deleted_excluded_from_list(client):
    client.post(
        "/api/v1/knowledge/",
        json={"title": "Keep", "content": "stay"},
    )
    r2 = client.post(
        "/api/v1/knowledge/",
        json={"title": "Gone", "content": "bye"},
    )
    client.delete(f"/api/v1/knowledge/{r2.json()['id']}")
    r = client.get("/api/v1/knowledge/")
    titles = [e["title"] for e in r.json()["items"]]
    assert "Keep" in titles
    assert "Gone" not in titles


# --- Filtering ---


def test_filter_by_category(client):
    client.post(
        "/api/v1/knowledge/",
        json={"title": "SOP 1", "category": "sop", "content": "a"},
    )
    client.post(
        "/api/v1/knowledge/",
        json={"title": "Protocol 1", "category": "protocol", "content": "b"},
    )
    client.post(
        "/api/v1/knowledge/",
        json={"title": "SOP 2", "category": "sop", "content": "c"},
    )
    r = client.get("/api/v1/knowledge/?category=sop")
    assert len(r.json()["items"]) == 2


# --- Search ---


def test_search_in_list(client):
    client.post(
        "/api/v1/knowledge/",
        json={
            "title": "Centrifuge Manual",
            "content": "Operating instructions for centrifuge.",
        },
    )
    client.post(
        "/api/v1/knowledge/",
        json={"title": "Microscope Guide", "content": "How to use the microscope."},
    )
    r = client.get("/api/v1/knowledge/?search=centrifuge")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Centrifuge Manual"


def test_dedicated_search_endpoint(client):
    client.post(
        "/api/v1/knowledge/",
        json={
            "title": "PCR Protocol",
            "category": "protocol",
            "content": "Step by step PCR amplification.",
        },
    )
    client.post(
        "/api/v1/knowledge/",
        json={
            "title": "Western Blot",
            "category": "protocol",
            "content": "Protein detection protocol.",
        },
    )
    r = client.get("/api/v1/knowledge/search?q=PCR")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "PCR Protocol"


def test_search_with_category_filter(client):
    client.post(
        "/api/v1/knowledge/",
        json={
            "title": "Safety Protocol A",
            "category": "safety",
            "content": "Fire extinguisher locations.",
        },
    )
    client.post(
        "/api/v1/knowledge/",
        json={
            "title": "Safety Protocol B",
            "category": "safety",
            "content": "Emergency contacts.",
        },
    )
    client.post(
        "/api/v1/knowledge/",
        json={
            "title": "SOP A",
            "category": "sop",
            "content": "Safety procedures for chemicals.",
        },
    )
    r = client.get("/api/v1/knowledge/search?q=Safety&category=safety")
    items = r.json()["items"]
    assert len(items) == 2
    assert all(e["category"] == "safety" for e in items)


def test_search_no_results(client):
    r = client.get("/api/v1/knowledge/search?q=nonexistent_xyz")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["items"] == []


def test_search_content_match(client):
    client.post(
        "/api/v1/knowledge/",
        json={
            "title": "General Info",
            "content": "This document describes autoclave sterilization procedures.",
        },
    )
    r = client.get("/api/v1/knowledge/search?q=autoclave")
    assert len(r.json()["items"]) == 1


# --- Pagination ---


def test_list_pagination(client):
    for i in range(5):
        client.post(
            "/api/v1/knowledge/",
            json={"title": f"Entry {i}", "content": f"Content {i}"},
        )
    r = client.get("/api/v1/knowledge/?page=1&page_size=2")
    data = r.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["pages"] == 3


# --- Source fields ---


def test_source_fields(client):
    r = client.post(
        "/api/v1/knowledge/",
        json={
            "title": "Vendor Manual",
            "content": "Read the manual.",
            "source_type": "url",
            "source_url": "https://example.com/manual.pdf",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["source_type"] == "url"
    assert data["source_url"] == "https://example.com/manual.pdf"
