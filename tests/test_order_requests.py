"""Tests for supply request and approval workflow.

Uses patched get_current_staff to simulate different roles,
matching the RBAC pattern from test_rbac_route_guards.py.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.vendor import Vendor

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("MEILISEARCH_URL", "http://localhost:7700")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password-not-for-production")
os.environ.setdefault("UPLOAD_DIR", "/tmp/lab-manager-test-uploads")

from lab_manager.config import get_settings  # noqa: E402

get_settings.cache_clear()

_ROUTE_MODULE = "lab_manager.api.routes.order_requests"
_AUTH_MODULE = "lab_manager.api.auth"

# ---------------------------------------------------------------------------
# Staff identity helpers
# ---------------------------------------------------------------------------

_STAFF_SEQ = 0


def _next_id() -> int:
    global _STAFF_SEQ
    _STAFF_SEQ += 1
    return _STAFF_SEQ


def _make_staff(role: str, name: str | None = None) -> dict:
    return {
        "id": _next_id(),
        "name": name or f"test_{role}",
        "email": None,
        "role": role,
        "role_level": {"pi": 0, "admin": 1, "postdoc": 2, "grad_student": 3}.get(
            role, 3
        ),
    }


def _patch_staff(staff_dict):
    """Patch get_current_staff in both the route module and the auth module."""
    return (
        patch(f"{_ROUTE_MODULE}.get_current_staff", side_effect=lambda req: staff_dict),
        patch(f"{_AUTH_MODULE}.get_current_staff", side_effect=lambda req: staff_dict),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_seq():
    global _STAFF_SEQ
    _STAFF_SEQ = 0


@pytest.fixture
def _engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(_engine):
    with Session(_engine) as session:
        yield session


@pytest.fixture
def _seed_vendor(db_session):
    v = Vendor(name="TestVendor")
    db_session.add(v)
    db_session.flush()
    db_session.refresh(v)
    return v.id


@pytest.fixture
def _app(db_session):
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def admin_staff():
    return _make_staff("admin", "pi_user")


@pytest.fixture
def student_staff():
    return _make_staff("grad_student", "grad_student")


@pytest.fixture
def admin_client(_app, admin_staff):
    p1, p2 = _patch_staff(admin_staff)
    with p1, p2:
        with TestClient(_app) as c:
            yield c


@pytest.fixture
def student_client(_app, student_staff):
    p1, p2 = _patch_staff(student_staff)
    with p1, p2:
        with TestClient(_app) as c:
            yield c


def _create_request(c, **overrides):
    body = {
        "description": "96-well PCR plates",
        "quantity": "10",
        "unit": "pack",
        "estimated_price": "45.00",
        "justification": "Running qPCR experiment next week",
        "urgency": "normal",
    }
    body.update(overrides)
    return c.post("/api/v1/requests/", json=body)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_request(student_client):
    resp = _create_request(student_client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["description"] == "96-well PCR plates"
    assert data["urgency"] == "normal"
    assert data["requested_by"] is not None


def test_create_urgent_request(student_client):
    resp = _create_request(student_client, urgency="urgent")
    assert resp.status_code == 201
    assert resp.json()["urgency"] == "urgent"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_list_requests_student_sees_own(student_client, admin_client):
    """Students only see their own requests."""
    _create_request(student_client)
    _create_request(student_client)

    resp = student_client.get("/api/v1/requests/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2

    # Admin can see all (including student's 2)
    resp = admin_client.get("/api/v1/requests/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2


def test_list_requests_filter_status(student_client):
    _create_request(student_client)
    resp = student_client.get("/api/v1/requests/?status=pending")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ---------------------------------------------------------------------------
# Get detail
# ---------------------------------------------------------------------------


def test_get_request_detail(student_client):
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = student_client.get(f"/api/v1/requests/{req_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == req_id


def test_get_request_other_student_forbidden(_app, admin_staff, student_staff):
    """A student cannot view a request created by someone else."""
    # Admin creates
    p1a, p2a = _patch_staff(admin_staff)
    with p1a, p2a:
        with TestClient(_app) as c:
            resp = _create_request(c)
            req_id = resp.json()["id"]

    # Student tries to read admin's request
    p1s, p2s = _patch_staff(student_staff)
    with p1s, p2s:
        with TestClient(_app) as c:
            resp = c.get(f"/api/v1/requests/{req_id}")
            assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


def test_approve_creates_order(student_client, admin_client, _seed_vendor):
    resp = _create_request(
        student_client, catalog_number="PCR-96", vendor_id=_seed_vendor
    )
    req_id = resp.json()["id"]

    resp = admin_client.post(
        f"/api/v1/requests/{req_id}/approve",
        json={"note": "Approved for next month's budget"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["order_id"] is not None
    assert data["reviewed_by"] is not None
    assert data["review_note"] == "Approved for next month's budget"
    assert data["reviewed_at"] is not None

    # Verify the order was created
    order_id = data["order_id"]
    order_resp = admin_client.get(f"/api/v1/orders/{order_id}")
    assert order_resp.status_code == 200

    # Verify order item was created
    items_resp = admin_client.get(f"/api/v1/orders/{order_id}/items")
    assert items_resp.status_code == 200
    items = items_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["catalog_number"] == "PCR-96"


def test_approve_not_pending_fails(student_client, admin_client, _seed_vendor):
    resp = _create_request(student_client, vendor_id=_seed_vendor)
    req_id = resp.json()["id"]

    # Approve once
    admin_client.post(f"/api/v1/requests/{req_id}/approve", json={})
    # Try to approve again
    resp = admin_client.post(f"/api/v1/requests/{req_id}/approve", json={})
    assert resp.status_code == 409


def test_approve_by_student_forbidden(student_client, student_staff):
    """Grad student cannot approve (lacks approve_order_requests permission)."""
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = student_client.post(f"/api/v1/requests/{req_id}/approve", json={})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------


def test_reject_request(student_client, admin_client):
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = admin_client.post(
        f"/api/v1/requests/{req_id}/reject",
        json={"note": "Over budget this quarter"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["review_note"] == "Over budget this quarter"


def test_reject_by_student_forbidden(student_client):
    """Grad student cannot reject (lacks approve_order_requests permission)."""
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = student_client.post(f"/api/v1/requests/{req_id}/reject", json={})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


def test_cancel_own_request(student_client):
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = student_client.post(f"/api/v1/requests/{req_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_others_request_forbidden(_app, admin_staff, student_staff):
    """Student cannot cancel admin's request."""
    # Admin creates
    p1a, p2a = _patch_staff(admin_staff)
    with p1a, p2a:
        with TestClient(_app) as c:
            resp = _create_request(c)
            req_id = resp.json()["id"]

    # Student tries to cancel
    p1s, p2s = _patch_staff(student_staff)
    with p1s, p2s:
        with TestClient(_app) as c:
            resp = c.post(f"/api/v1/requests/{req_id}/cancel")
            assert resp.status_code == 403


def test_cancel_non_pending_fails(student_client, admin_client, _seed_vendor):
    resp = _create_request(student_client, vendor_id=_seed_vendor)
    req_id = resp.json()["id"]

    admin_client.post(f"/api/v1/requests/{req_id}/approve", json={})
    resp = student_client.post(f"/api/v1/requests/{req_id}/cancel")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def test_request_stats(student_client, admin_client, _seed_vendor):
    _create_request(student_client)
    _create_request(student_client)

    resp2 = _create_request(student_client, vendor_id=_seed_vendor)
    req_id = resp2.json()["id"]
    admin_client.post(f"/api/v1/requests/{req_id}/approve", json={})

    resp = student_client.get("/api/v1/requests/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending"] == 2
    assert data["approved"] == 1
    assert data["total"] == 3


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


def test_get_nonexistent_request(student_client):
    resp = student_client.get("/api/v1/requests/9999")
    assert resp.status_code == 404


def test_approve_nonexistent_request(admin_client):
    resp = admin_client.post("/api/v1/requests/9999/approve", json={})
    assert resp.status_code == 404
