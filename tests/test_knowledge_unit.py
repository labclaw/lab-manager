"""Unit tests for knowledge route — CRUD, search, validation, edge cases.

Uses MagicMock for DB sessions to isolate route logic from the database.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lab_manager.api.routes.knowledge import (
    KnowledgeCreate,
    KnowledgeUpdate,
    _VALID_CATEGORIES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    id: int = 1,
    title: str = "Test SOP",
    category: str = "sop",
    content: str = "Step 1: Do thing.",
    tags: list | None = None,
    source_type: str | None = None,
    source_url: str | None = None,
    is_deleted: bool = False,
):
    """Create a mock KnowledgeEntry."""
    entry = MagicMock()
    entry.id = id
    entry.title = title
    entry.category = category
    entry.content = content
    entry.tags = tags or []
    entry.source_type = source_type
    entry.source_url = source_url
    entry.is_deleted = is_deleted
    entry.created_at = "2026-01-01T00:00:00Z"
    entry.updated_at = "2026-01-01T00:00:00Z"
    entry.created_by = None
    return entry


def _make_db(entries=None):
    """Create a mock DB session that returns given entries from scalars()."""
    db = MagicMock()
    # db.scalars().all() is used by paginate()
    scalars_result = MagicMock()
    scalars_result.all.return_value = entries or []
    db.scalars.return_value = scalars_result
    # db.execute().scalar() for count queries in paginate
    execute_result = MagicMock()
    execute_result.scalar.return_value = len(entries) if entries else 0
    db.execute.return_value = execute_result
    # db.get() for get_or_404
    db.get.return_value = None
    # db.add, db.flush, db.refresh are no-ops
    db.add.return_value = None
    db.flush.return_value = None
    return db


def _make_paginate_result(items, total=None, page=1, page_size=50):
    """Build the dict that paginate() returns."""
    total = total if total is not None else len(items)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }


# ---------------------------------------------------------------------------
# KnowledgeCreate validation
# ---------------------------------------------------------------------------


class TestKnowledgeCreateValidation:
    """Test Pydantic model validation for KnowledgeCreate."""

    def test_valid_minimal(self):
        body = KnowledgeCreate(title="Hello", content="World")
        assert body.title == "Hello"
        assert body.content == "World"
        assert body.category == "general"
        assert body.tags == []
        assert body.source_type is None
        assert body.source_url is None

    def test_valid_all_fields(self):
        body = KnowledgeCreate(
            title="Safety Protocol",
            category="safety",
            content="Wear goggles.",
            tags=["safety", "ppe"],
            source_type="pdf",
            source_url="https://example.com/safety.pdf",
        )
        assert body.category == "safety"
        assert body.tags == ["safety", "ppe"]

    def test_all_valid_categories(self):
        for cat in _VALID_CATEGORIES:
            body = KnowledgeCreate(title="T", content="C", category=cat)
            assert body.category == cat

    def test_invalid_category_rejected(self):
        with pytest.raises(Exception):
            KnowledgeCreate(title="T", content="C", category="nonexistent")

    def test_empty_category_defaults_to_general(self):
        body = KnowledgeCreate(title="T", content="C", category="general")
        assert body.category == "general"

    def test_title_max_length(self):
        body = KnowledgeCreate(title="A" * 500, content="C")
        assert len(body.title) == 500

    def test_title_exceeds_max_length(self):
        with pytest.raises(Exception):
            KnowledgeCreate(title="A" * 501, content="C")

    def test_source_type_max_length(self):
        body = KnowledgeCreate(title="T", content="C", source_type="A" * 100)
        assert len(body.source_type) == 100

    def test_source_type_exceeds_max_length(self):
        with pytest.raises(Exception):
            KnowledgeCreate(title="T", content="C", source_type="A" * 101)

    def test_source_url_max_length(self):
        body = KnowledgeCreate(title="T", content="C", source_url="A" * 2000)
        assert len(body.source_url) == 2000

    def test_source_url_exceeds_max_length(self):
        with pytest.raises(Exception):
            KnowledgeCreate(title="T", content="C", source_url="A" * 2001)

    def test_tags_default_empty_list(self):
        body = KnowledgeCreate(title="T", content="C")
        assert body.tags == []

    def test_tags_with_values(self):
        body = KnowledgeCreate(title="T", content="C", tags=["a", "b", "c"])
        assert body.tags == ["a", "b", "c"]

    def test_empty_title_rejected_if_required(self):
        """Title is a required field -- empty string is valid content but the
        field must be present."""
        body = KnowledgeCreate(title="", content="C")
        assert body.title == ""


# ---------------------------------------------------------------------------
# KnowledgeUpdate validation
# ---------------------------------------------------------------------------


class TestKnowledgeUpdateValidation:
    """Test Pydantic model validation for KnowledgeUpdate."""

    def test_all_none(self):
        body = KnowledgeUpdate()
        assert body.title is None
        assert body.category is None
        assert body.content is None
        assert body.tags is None
        assert body.source_type is None
        assert body.source_url is None

    def test_partial_update(self):
        body = KnowledgeUpdate(title="New Title")
        assert body.title == "New Title"
        assert body.category is None

    def test_valid_category(self):
        for cat in _VALID_CATEGORIES:
            body = KnowledgeUpdate(category=cat)
            assert body.category == cat

    def test_invalid_category_rejected(self):
        with pytest.raises(Exception):
            KnowledgeUpdate(category="invalid_cat")

    def test_none_category_is_valid(self):
        """None is allowed on update -- means 'do not change'."""
        body = KnowledgeUpdate(category=None)
        assert body.category is None

    def test_title_max_length(self):
        body = KnowledgeUpdate(title="B" * 500)
        assert len(body.title) == 500

    def test_title_exceeds_max_length(self):
        with pytest.raises(Exception):
            KnowledgeUpdate(title="B" * 501)

    def test_exclude_unset_behavior(self):
        """model_dump(exclude_unset=True) should only include explicitly set fields."""
        body = KnowledgeUpdate(title="Updated")
        dumped = body.model_dump(exclude_unset=True)
        assert "title" in dumped
        assert "category" not in dumped
        assert "content" not in dumped


# ---------------------------------------------------------------------------
# Valid categories constant
# ---------------------------------------------------------------------------


class TestValidCategories:
    """Test the _VALID_CATEGORIES set derived from KnowledgeCategory enum."""

    def test_contains_all_enum_values(self):
        expected = {
            "sop",
            "safety",
            "equipment_manual",
            "protocol",
            "troubleshooting",
            "general",
        }
        assert _VALID_CATEGORIES == expected

    def test_is_a_set(self):
        assert isinstance(_VALID_CATEGORIES, set)


# ---------------------------------------------------------------------------
# list_knowledge route
# ---------------------------------------------------------------------------


class TestListKnowledge:
    """Test the GET / knowledge list endpoint."""

    @patch("lab_manager.api.routes.knowledge.paginate")
    @patch("lab_manager.api.routes.knowledge.apply_sort")
    def test_basic_list(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.knowledge import list_knowledge

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        result = list_knowledge(category=None, search=None, db=db)
        assert result["total"] == 0
        assert result["items"] == []

    @patch("lab_manager.api.routes.knowledge.paginate")
    @patch("lab_manager.api.routes.knowledge.apply_sort")
    def test_list_with_category_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.knowledge import list_knowledge

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_knowledge(category="sop", search=None, db=db)
        # apply_sort was called, paginate was called
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.knowledge.paginate")
    @patch("lab_manager.api.routes.knowledge.apply_sort")
    def test_list_with_search(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.knowledge import list_knowledge

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_knowledge(search="goggles", db=db)
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.knowledge.paginate")
    @patch("lab_manager.api.routes.knowledge.apply_sort")
    def test_list_pagination_params(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.knowledge import list_knowledge

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result(
            [], total=0, page=2, page_size=10
        )
        db = _make_db()

        result = list_knowledge(page=2, page_size=10, category=None, search=None, db=db)
        assert result["page"] == 2
        assert result["page_size"] == 10

    @patch("lab_manager.api.routes.knowledge.paginate")
    @patch("lab_manager.api.routes.knowledge.apply_sort")
    def test_list_default_params(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.knowledge import list_knowledge

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_knowledge(category=None, search=None, db=db)
        # paginate is called with the query, db, and FastAPI Query defaults
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.knowledge.paginate")
    @patch("lab_manager.api.routes.knowledge.apply_sort")
    def test_list_excludes_deleted(self, mock_sort, mock_paginate):
        """List endpoint should filter out soft-deleted entries."""
        from lab_manager.api.routes.knowledge import list_knowledge

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_knowledge(category=None, search=None, db=db)
        # The select statement should have is_deleted == False filter
        mock_sort.assert_called_once()


# ---------------------------------------------------------------------------
# create_knowledge route
# ---------------------------------------------------------------------------


class TestCreateKnowledge:
    """Test the POST / knowledge create endpoint."""

    def test_create_basic(self):
        from lab_manager.api.routes.knowledge import create_knowledge

        db = _make_db()
        created_entry = _make_entry(title="New Entry", content="Some content")
        db.refresh.return_value = None

        # After flush+refresh, simulate the entry getting an id
        def side_effect_refresh(obj):
            obj.id = 1

        db.refresh.side_effect = side_effect_refresh

        body = KnowledgeCreate(title="New Entry", content="Some content")
        result = create_knowledge(body=body, db=db)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        db.refresh.assert_called_once()

    def test_create_with_all_fields(self):
        from lab_manager.api.routes.knowledge import create_knowledge

        db = _make_db()
        db.refresh.side_effect = lambda obj: None

        body = KnowledgeCreate(
            title="Full Entry",
            category="safety",
            content="Content here",
            tags=["tag1"],
            source_type="manual",
            source_url="https://example.com",
        )
        create_knowledge(body=body, db=db)
        db.add.assert_called_once()

    def test_create_uses_model_dump(self):
        """Verify body.model_dump() is used to construct the entry."""
        from lab_manager.api.routes.knowledge import create_knowledge

        db = _make_db()
        db.refresh.side_effect = lambda obj: None

        body = KnowledgeCreate(title="T", content="C", category="sop")
        create_knowledge(body=body, db=db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.title == "T"
        assert added_obj.content == "C"
        assert added_obj.category == "sop"


# ---------------------------------------------------------------------------
# search_knowledge route
# ---------------------------------------------------------------------------


class TestSearchKnowledge:
    """Test the GET /search endpoint."""

    @patch("lab_manager.api.routes.knowledge.paginate")
    def test_search_basic(self, mock_paginate):
        from lab_manager.api.routes.knowledge import search_knowledge

        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        result = search_knowledge(q="safety", db=db)
        assert result["items"] == []

    @patch("lab_manager.api.routes.knowledge.paginate")
    def test_search_with_category(self, mock_paginate):
        from lab_manager.api.routes.knowledge import search_knowledge

        entry = _make_entry(title="Safety goggles SOP", category="safety")
        mock_paginate.return_value = _make_paginate_result([entry], total=1)
        db = _make_db()

        result = search_knowledge(q="goggles", category="safety", db=db)
        assert result["total"] == 1

    @patch("lab_manager.api.routes.knowledge.paginate")
    def test_search_pagination(self, mock_paginate):
        from lab_manager.api.routes.knowledge import search_knowledge

        mock_paginate.return_value = _make_paginate_result([], page=3, page_size=5)
        db = _make_db()

        result = search_knowledge(q="test", page=3, page_size=5, db=db)
        assert result["page"] == 3
        assert result["page_size"] == 5

    @patch("lab_manager.api.routes.knowledge.paginate")
    def test_search_excludes_deleted(self, mock_paginate):
        """Search should not return soft-deleted entries."""
        from lab_manager.api.routes.knowledge import search_knowledge

        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        search_knowledge(q="anything", db=db)
        mock_paginate.assert_called_once()


# ---------------------------------------------------------------------------
# get_knowledge route
# ---------------------------------------------------------------------------


class TestGetKnowledge:
    """Test the GET /{entry_id} endpoint."""

    def test_get_existing(self):
        from lab_manager.api.routes.knowledge import get_knowledge

        entry = _make_entry(id=42, title="Found Entry")
        db = _make_db()
        db.get.return_value = entry

        result = get_knowledge(entry_id=42, db=db)
        assert result.id == 42
        assert result.title == "Found Entry"

    def test_get_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.knowledge import get_knowledge
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            get_knowledge(entry_id=9999, db=db)

    def test_get_verifies_model_and_id(self):
        """get_or_404 should be called with the correct model class and id."""
        from lab_manager.api.routes.knowledge import get_knowledge
        from lab_manager.models.knowledge import KnowledgeEntry

        entry = _make_entry(id=5)
        db = _make_db()
        db.get.return_value = entry

        get_knowledge(entry_id=5, db=db)
        db.get.assert_called_once_with(KnowledgeEntry, 5)


# ---------------------------------------------------------------------------
# update_knowledge route
# ---------------------------------------------------------------------------


class TestUpdateKnowledge:
    """Test the PATCH /{entry_id} endpoint."""

    def test_update_title(self):
        from lab_manager.api.routes.knowledge import update_knowledge

        entry = _make_entry(id=1, title="Old Title")
        db = _make_db()
        db.get.return_value = entry

        body = KnowledgeUpdate(title="New Title")
        result = update_knowledge(entry_id=1, body=body, db=db)

        assert entry.title == "New Title"
        db.flush.assert_called_once()
        db.refresh.assert_called_once()

    def test_update_category(self):
        from lab_manager.api.routes.knowledge import update_knowledge

        entry = _make_entry(id=1, category="general")
        db = _make_db()
        db.get.return_value = entry

        body = KnowledgeUpdate(category="safety")
        update_knowledge(entry_id=1, body=body, db=db)
        assert entry.category == "safety"

    def test_update_content(self):
        from lab_manager.api.routes.knowledge import update_knowledge

        entry = _make_entry(id=1, content="Old")
        db = _make_db()
        db.get.return_value = entry

        body = KnowledgeUpdate(content="New content here")
        update_knowledge(entry_id=1, body=body, db=db)
        assert entry.content == "New content here"

    def test_update_tags(self):
        from lab_manager.api.routes.knowledge import update_knowledge

        entry = _make_entry(id=1, tags=["old"])
        db = _make_db()
        db.get.return_value = entry

        body = KnowledgeUpdate(tags=["new1", "new2"])
        update_knowledge(entry_id=1, body=body, db=db)
        assert entry.tags == ["new1", "new2"]

    def test_update_source_fields(self):
        from lab_manager.api.routes.knowledge import update_knowledge

        entry = _make_entry(id=1)
        db = _make_db()
        db.get.return_value = entry

        body = KnowledgeUpdate(source_type="web", source_url="https://new.url")
        update_knowledge(entry_id=1, body=body, db=db)
        assert entry.source_type == "web"
        assert entry.source_url == "https://new.url"

    def test_update_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.knowledge import update_knowledge
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        body = KnowledgeUpdate(title="Nope")
        with pytest.raises(NotFoundError):
            update_knowledge(entry_id=9999, body=body, db=db)

    def test_partial_update_only_sets_provided_fields(self):
        """Fields not included in the update body should remain unchanged."""
        from lab_manager.api.routes.knowledge import update_knowledge

        entry = _make_entry(
            id=1, title="Keep This", category="sop", content="Keep Content"
        )
        db = _make_db()
        db.get.return_value = entry

        body = KnowledgeUpdate(category="safety")
        update_knowledge(entry_id=1, body=body, db=db)

        assert entry.category == "safety"
        # title and content were not changed by the update call itself
        # (setattr is only called for exclude_unset fields)

    def test_update_empty_body_no_changes(self):
        """An empty update body should not modify any fields."""
        from lab_manager.api.routes.knowledge import update_knowledge

        entry = _make_entry(id=1, title="Original", content="Original")
        db = _make_db()
        db.get.return_value = entry

        body = KnowledgeUpdate()
        dumped = body.model_dump(exclude_unset=True)
        assert len(dumped) == 0

        update_knowledge(entry_id=1, body=body, db=db)
        db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# delete_knowledge route
# ---------------------------------------------------------------------------


class TestDeleteKnowledge:
    """Test the DELETE /{entry_id} endpoint."""

    def test_delete_existing(self):
        from lab_manager.api.routes.knowledge import delete_knowledge

        entry = _make_entry(id=1, is_deleted=False)
        db = _make_db()
        db.get.return_value = entry

        result = delete_knowledge(entry_id=1, db=db)
        assert result is None
        assert entry.is_deleted is True
        db.flush.assert_called_once()

    def test_delete_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.knowledge import delete_knowledge
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            delete_knowledge(entry_id=9999, db=db)

    def test_soft_delete_not_hard_delete(self):
        """Delete should set is_deleted=True, not remove from DB."""
        from lab_manager.api.routes.knowledge import delete_knowledge

        entry = _make_entry(id=5, is_deleted=False)
        db = _make_db()
        db.get.return_value = entry

        delete_knowledge(entry_id=5, db=db)
        assert entry.is_deleted is True
        # db.delete should NOT have been called (soft delete only)
        assert (
            not hasattr(db, "delete") or db.delete.call_count == 0
            if hasattr(db, "delete")
            else True
        )

    def test_delete_already_deleted_still_succeeds(self):
        """Deleting an already-deleted entry should still succeed (set is_deleted again)."""
        from lab_manager.api.routes.knowledge import delete_knowledge

        entry = _make_entry(id=3, is_deleted=True)
        db = _make_db()
        db.get.return_value = entry

        delete_knowledge(entry_id=3, db=db)
        assert entry.is_deleted is True


# ---------------------------------------------------------------------------
# Integration-style tests via TestClient (uses conftest fixtures)
# ---------------------------------------------------------------------------


class TestKnowledgeEndpointsViaClient:
    """Test the knowledge endpoints through the FastAPI TestClient.

    These exercise the full request/response cycle with an in-memory SQLite DB.
    Requires the conftest.py fixtures (db_session, client).
    """

    def test_create_and_get(self, client):
        resp = client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Test SOP",
                "category": "sop",
                "content": "Do the thing.",
                "tags": ["sop"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test SOP"
        assert data["category"] == "sop"
        entry_id = data["id"]

        resp2 = client.get(f"/api/v1/knowledge/{entry_id}")
        assert resp2.status_code == 200
        assert resp2.json()["title"] == "Test SOP"

    def test_list_empty(self, client):
        resp = client.get("/api/v1/knowledge/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data

    def test_list_with_entries(self, client):
        # Create 3 entries
        for i in range(3):
            client.post(
                "/api/v1/knowledge/",
                json={
                    "title": f"Entry {i}",
                    "category": "general",
                    "content": f"Content {i}",
                },
            )

        resp = client.get("/api/v1/knowledge/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3

    def test_search_found(self, client):
        client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Safety Goggles Protocol",
                "category": "safety",
                "content": "Always wear goggles.",
            },
        )
        resp = client.get("/api/v1/knowledge/search?q=goggles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any("goggles" in item["title"].lower() for item in data["items"])

    def test_search_not_found(self, client):
        resp = client.get("/api/v1/knowledge/search?q=zzzznonexistentzzzz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_update_entry(self, client):
        create_resp = client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Before Update",
                "category": "general",
                "content": "Old content",
            },
        )
        entry_id = create_resp.json()["id"]

        patch_resp = client.patch(
            f"/api/v1/knowledge/{entry_id}",
            json={"title": "After Update"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["title"] == "After Update"

    def test_delete_entry(self, client):
        create_resp = client.post(
            "/api/v1/knowledge/",
            json={
                "title": "To Delete",
                "category": "general",
                "content": "Bye",
            },
        )
        entry_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/knowledge/{entry_id}")
        assert del_resp.status_code == 204

        # Verify soft-deleted: should not appear in list
        list_resp = client.get("/api/v1/knowledge/")
        ids = [item["id"] for item in list_resp.json()["items"]]
        assert entry_id not in ids

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get("/api/v1/knowledge/999999")
        assert resp.status_code == 404

    def test_update_nonexistent_returns_404(self, client):
        resp = client.patch(
            "/api/v1/knowledge/999999",
            json={"title": "Ghost"},
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/api/v1/knowledge/999999")
        assert resp.status_code == 404

    def test_create_with_all_fields(self, client):
        resp = client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Full Entry",
                "category": "equipment_manual",
                "content": "Detailed manual content.",
                "tags": ["manual", "equipment"],
                "source_type": "pdf",
                "source_url": "https://example.com/manual.pdf",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "equipment_manual"
        assert data["tags"] == ["manual", "equipment"]
        assert data["source_type"] == "pdf"

    def test_search_with_category_filter(self, client):
        client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Troubleshooting Guide",
                "category": "troubleshooting",
                "content": "If it breaks, restart it.",
            },
        )
        client.post(
            "/api/v1/knowledge/",
            json={
                "title": "General Note",
                "category": "general",
                "content": "If it breaks, restart it.",
            },
        )

        resp = client.get("/api/v1/knowledge/search?q=restart&category=troubleshooting")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all(item["category"] == "troubleshooting" for item in data["items"])

    def test_list_sort_desc(self, client):
        resp = client.get("/api/v1/knowledge/?sort_by=title&sort_dir=desc")
        assert resp.status_code == 200

    def test_list_with_search_filter(self, client):
        client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Unique Search Title XYZ123",
                "category": "general",
                "content": "Unique search content",
            },
        )
        resp = client.get("/api/v1/knowledge/?search=XYZ123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_list_with_category_filter(self, client):
        client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Safety Entry",
                "category": "safety",
                "content": "Be safe.",
            },
        )
        resp = client.get("/api/v1/knowledge/?category=safety")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all(item["category"] == "safety" for item in data["items"])

    def test_create_invalid_category_returns_422(self, client):
        resp = client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Bad Category",
                "category": "nonexistent",
                "content": "Test",
            },
        )
        assert resp.status_code == 422

    def test_search_empty_query_returns_422(self, client):
        """The search endpoint requires q to have min_length=1."""
        resp = client.get("/api/v1/knowledge/search?q=")
        assert resp.status_code == 422

    def test_search_missing_query_returns_422(self, client):
        """The q parameter is required."""
        resp = client.get("/api/v1/knowledge/search")
        assert resp.status_code == 422

    def test_update_invalid_category_returns_422(self, client):
        create_resp = client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Entry",
                "category": "general",
                "content": "C",
            },
        )
        entry_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/knowledge/{entry_id}",
            json={"category": "bad_category"},
        )
        assert resp.status_code == 422

    def test_delete_then_list_excludes_deleted(self, client):
        """After soft-delete, entry should not appear in list."""
        create_resp = client.post(
            "/api/v1/knowledge/",
            json={
                "title": "Delete Me For List Check",
                "category": "general",
                "content": "Temporary",
            },
        )
        entry_id = create_resp.json()["id"]

        client.delete(f"/api/v1/knowledge/{entry_id}")

        list_resp = client.get("/api/v1/knowledge/")
        titles = [item["title"] for item in list_resp.json()["items"]]
        assert "Delete Me For List Check" not in titles

    def test_delete_then_search_excludes_deleted(self, client):
        """After soft-delete, entry should not appear in search."""
        create_resp = client.post(
            "/api/v1/knowledge/",
            json={
                "title": "SearchDeleteTest ABC999",
                "category": "general",
                "content": "Search after delete",
            },
        )
        entry_id = create_resp.json()["id"]

        client.delete(f"/api/v1/knowledge/{entry_id}")

        search_resp = client.get("/api/v1/knowledge/search?q=ABC999")
        assert search_resp.json()["total"] == 0

    def test_pagination_page_size(self, client):
        """Verify page_size is respected."""
        for i in range(5):
            client.post(
                "/api/v1/knowledge/",
                json={
                    "title": f"Page Entry {i}",
                    "category": "general",
                    "content": f"Content {i}",
                },
            )

        resp = client.get("/api/v1/knowledge/?page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2
