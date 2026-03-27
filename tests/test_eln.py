"""Tests for ELN (Electronic Lab Notebook) endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def sample_entry(client: TestClient):
    """Create a sample ELN entry and return its data."""
    resp = client.post(
        "/api/v1/eln/",
        json={
            "title": "Test Entry",
            "content_type": "text",
            "content": "This is a test notebook entry.",
            "tags": ["biology", "PCR"],
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def sample_tag(client: TestClient):
    """Create a sample tag."""
    resp = client.post(
        "/api/v1/eln/tags/", json={"name": "chemistry", "color": "#ff0000"}
    )
    assert resp.status_code == 201
    return resp.json()


class TestEntryCRUD:
    """CRUD operations for ELN entries."""

    def test_create_entry(self, client: TestClient):
        resp = client.post(
            "/api/v1/eln/",
            json={
                "title": "My First Entry",
                "content_type": "text",
                "content": "Hello world",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My First Entry"
        assert data["content_type"] == "text"
        assert data["content"] == "Hello world"
        assert data["is_deleted"] is False
        assert data["id"] is not None

    def test_create_entry_with_tags_json(self, client: TestClient):
        resp = client.post(
            "/api/v1/eln/",
            json={
                "title": "Tagged Entry",
                "content_type": "mixed",
                "tags": ["protein", "western-blot"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tags_json"] == ["protein", "western-blot"]

    def test_create_entry_invalid_content_type(self, client: TestClient):
        resp = client.post(
            "/api/v1/eln/",
            json={"title": "Bad", "content_type": "video"},
        )
        assert resp.status_code == 422

    def test_list_entries(self, client: TestClient):
        # Create multiple entries
        for i in range(3):
            client.post(
                "/api/v1/eln/",
                json={"title": f"Entry {i}", "content": f"Content {i}"},
            )
        resp = client.get("/api/v1/eln/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_get_entry(self, client: TestClient, sample_entry):
        entry_id = sample_entry["id"]
        resp = client.get(f"/api/v1/eln/{entry_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Entry"
        assert "attachments" in data
        assert "tag_objects" in data

    def test_get_entry_not_found(self, client: TestClient):
        resp = client.get("/api/v1/eln/99999")
        assert resp.status_code == 404

    def test_update_entry(self, client: TestClient, sample_entry):
        entry_id = sample_entry["id"]
        resp = client.patch(
            f"/api/v1/eln/{entry_id}",
            json={"title": "Updated Title", "content": "Updated content"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["content"] == "Updated content"

    def test_update_entry_tags(self, client: TestClient, sample_entry):
        entry_id = sample_entry["id"]
        resp = client.patch(
            f"/api/v1/eln/{entry_id}",
            json={"tags": ["new-tag-1", "new-tag-2"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tags_json"] == ["new-tag-1", "new-tag-2"]

    def test_soft_delete_entry(self, client: TestClient, sample_entry):
        entry_id = sample_entry["id"]
        resp = client.delete(f"/api/v1/eln/{entry_id}")
        assert resp.status_code == 204

        # Should not appear in list
        resp = client.get("/api/v1/eln/")
        data = resp.json()
        assert data["total"] == 0

        # Should not be fetchable directly
        resp = client.get(f"/api/v1/eln/{entry_id}")
        assert resp.status_code == 404


class TestFiltering:
    """Filter entries by various criteria."""

    def test_filter_by_experiment_id(self, client: TestClient):
        client.post(
            "/api/v1/eln/",
            json={"title": "Exp 1", "experiment_id": 42},
        )
        client.post(
            "/api/v1/eln/",
            json={"title": "Exp 2", "experiment_id": 99},
        )
        resp = client.get("/api/v1/eln/", params={"experiment_id": 42})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["experiment_id"] == 42

    def test_filter_by_project_id(self, client: TestClient):
        client.post(
            "/api/v1/eln/",
            json={"title": "Proj A", "project_id": 10},
        )
        client.post(
            "/api/v1/eln/",
            json={"title": "Proj B", "project_id": 20},
        )
        resp = client.get("/api/v1/eln/", params={"project_id": 10})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["project_id"] == 10

    def test_filter_by_content_type(self, client: TestClient):
        client.post(
            "/api/v1/eln/",
            json={"title": "Text Entry", "content_type": "text"},
        )
        client.post(
            "/api/v1/eln/",
            json={"title": "Table Entry", "content_type": "table"},
        )
        resp = client.get("/api/v1/eln/", params={"content_type": "table"})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["content_type"] == "table"


class TestSearch:
    """Full-text search across entries."""

    def test_search_by_title(self, client: TestClient):
        client.post(
            "/api/v1/eln/",
            json={"title": "Western Blot Protocol", "content": "Step by step"},
        )
        client.post(
            "/api/v1/eln/",
            json={"title": "PCR Setup", "content": "Primer design"},
        )
        resp = client.post("/api/v1/eln/search", json={"query": "Western"})
        data = resp.json()
        assert data["total"] == 1
        assert "Western" in data["items"][0]["title"]

    def test_search_by_content(self, client: TestClient):
        client.post(
            "/api/v1/eln/",
            json={"title": "Notes", "content": "Sodium dodecyl sulfate buffer prep"},
        )
        resp = client.post("/api/v1/eln/search", json={"query": "buffer"})
        data = resp.json()
        assert data["total"] == 1

    def test_search_no_results(self, client: TestClient):
        client.post(
            "/api/v1/eln/",
            json={"title": "Hello", "content": "World"},
        )
        resp = client.post("/api/v1/eln/search", json={"query": "nonexistent"})
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestAttachments:
    """Attachment handling."""

    def test_add_attachment(self, client: TestClient, sample_entry):
        entry_id = sample_entry["id"]
        resp = client.post(
            f"/api/v1/eln/{entry_id}/attachments",
            json={
                "filename": "gel_image.png",
                "file_path": "/uploads/gel_image.png",
                "file_type": "image/png",
                "file_size": 1024,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "gel_image.png"
        assert data["entry_id"] == entry_id

        # Verify attachments_json updated on the entry
        entry_resp = client.get(f"/api/v1/eln/{entry_id}")
        entry_data = entry_resp.json()
        assert len(entry_data["attachments_json"]) == 1
        assert entry_data["attachments_json"][0]["filename"] == "gel_image.png"

    def test_add_attachment_nonexistent_entry(self, client: TestClient):
        resp = client.post(
            "/api/v1/eln/99999/attachments",
            json={
                "filename": "test.txt",
                "file_path": "/uploads/test.txt",
            },
        )
        assert resp.status_code == 404


class TestTags:
    """Tag management."""

    def test_create_tag(self, client: TestClient):
        resp = client.post(
            "/api/v1/eln/tags/",
            json={"name": "biology", "color": "#00ff00"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "biology"
        assert data["color"] == "#00ff00"

    def test_list_tags(self, client: TestClient):
        client.post("/api/v1/eln/tags/", json={"name": "tag_a"})
        client.post("/api/v1/eln/tags/", json={"name": "tag_b"})
        resp = client.get("/api/v1/eln/tags/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    def test_create_duplicate_tag_fails(self, client: TestClient):
        client.post("/api/v1/eln/tags/", json={"name": "unique_tag"})
        resp = client.post("/api/v1/eln/tags/", json={"name": "unique_tag"})
        assert resp.status_code in (400, 409, 422)

    def test_entry_with_tag_ids(self, client: TestClient):
        # Create tags first
        tag1 = client.post("/api/v1/eln/tags/", json={"name": "pcr"}).json()
        tag2 = client.post("/api/v1/eln/tags/", json={"name": "dna"}).json()

        # Create entry with tag_ids
        resp = client.post(
            "/api/v1/eln/",
            json={
                "title": "Tagged Entry",
                "tag_ids": [tag1["id"], tag2["id"]],
            },
        )
        assert resp.status_code == 201
        data = resp.json()

        # Verify via GET (which eager-loads tag_objects)
        entry = client.get(f"/api/v1/eln/{data['id']}").json()
        tag_names = {t["name"] for t in entry["tag_objects"]}
        assert tag_names == {"pcr", "dna"}
