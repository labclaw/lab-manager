"""Tests for document PATCH status transition validation."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.document import Document


@pytest.fixture
def doc_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def doc_db(doc_engine):
    with Session(doc_engine) as session:
        yield session


@pytest.fixture
def doc_client(doc_db, monkeypatch):
    import os

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db
    from lab_manager.config import get_settings

    os.environ["AUTH_ENABLED"] = "false"
    os.environ["ADMIN_SECRET_KEY"] = "test-key"
    get_settings.cache_clear()

    app = create_app()

    def override_get_db():
        yield doc_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def _insert_doc(doc_db, status="pending"):
    doc = Document(
        file_path="uploads/test.pdf",
        file_name="test.pdf",
        status=status,
    )
    doc_db.add(doc)
    doc_db.flush()
    doc_db.refresh(doc)
    return doc.id


def test_patch_rejects_approved_status(doc_client, doc_db):
    """Cannot set status=approved via PATCH — must use /review."""
    doc_id = _insert_doc(doc_db, status="needs_review")
    resp = doc_client.patch(f"/api/v1/documents/{doc_id}", json={"status": "approved"})
    assert resp.status_code == 422
    assert "/review" in resp.json()["detail"]


def test_patch_rejects_rejected_status(doc_client, doc_db):
    """Cannot set status=rejected via PATCH — must use /review."""
    doc_id = _insert_doc(doc_db, status="needs_review")
    resp = doc_client.patch(f"/api/v1/documents/{doc_id}", json={"status": "rejected"})
    assert resp.status_code == 422


def test_patch_rejects_needs_review_status(doc_client, doc_db):
    """Cannot set status=needs_review via PATCH."""
    doc_id = _insert_doc(doc_db, status="pending")
    resp = doc_client.patch(
        f"/api/v1/documents/{doc_id}", json={"status": "needs_review"}
    )
    assert resp.status_code == 422


def test_patch_rejects_deleted_status(doc_client, doc_db):
    """Cannot set status=deleted via PATCH — must use DELETE."""
    doc_id = _insert_doc(doc_db, status="pending")
    resp = doc_client.patch(f"/api/v1/documents/{doc_id}", json={"status": "deleted"})
    assert resp.status_code == 422
    assert "DELETE" in resp.json()["detail"]


def test_patch_allows_ocr_failed_status(doc_client, doc_db):
    """Setting status=ocr_failed via PATCH is allowed."""
    doc_id = _insert_doc(doc_db, status="processing")
    resp = doc_client.patch(
        f"/api/v1/documents/{doc_id}", json={"status": "ocr_failed"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ocr_failed"


def test_patch_no_status_change_still_works(doc_client, doc_db):
    """PATCH without status field works as before."""
    doc_id = _insert_doc(doc_db, status="pending")
    resp = doc_client.patch(
        f"/api/v1/documents/{doc_id}", json={"review_notes": "updated notes"}
    )
    assert resp.status_code == 200
    assert resp.json()["review_notes"] == "updated notes"
