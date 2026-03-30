"""RBAC permission guards for order request endpoints.

Verifies:
- visitor/undergrad cannot create, view, list, cancel requests (403)
- grad_student can create/view/list/cancel own but cannot approve/reject (403)
- admin/pi can approve and reject requests
- owner-scoping: user can only cancel their own request
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("MEILISEARCH_URL", "http://localhost:7700")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password-not-for-production")
os.environ.setdefault("UPLOAD_DIR", "/tmp/lab-manager-test-uploads")

from lab_manager.config import get_settings  # noqa: E402

get_settings.cache_clear()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STAFF_COUNTER = 0

_ROUTE_MODULE = "lab_manager.api.routes.order_requests"
_AUTH_MODULE = "lab_manager.api.auth"


def _staff(role: str) -> dict:
    global _STAFF_COUNTER
    _STAFF_COUNTER += 1
    return {
        "id": _STAFF_COUNTER,
        "name": f"test_{role}_{_STAFF_COUNTER}",
        "email": None,
        "role": role,
        "role_level": {
            "pi": 0,
            "admin": 1,
            "postdoc": 2,
            "grad_student": 3,
            "undergrad": 4,
            "visitor": 4,
        }.get(role, 4),
    }


def _patch_staff(staff_dict):
    """Patch get_current_staff in both auth module and route module."""
    return (
        patch(f"{_ROUTE_MODULE}.get_current_staff", side_effect=lambda req: staff_dict),
        patch(f"{_AUTH_MODULE}.get_current_staff", side_effect=lambda req: staff_dict),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_counter():
    global _STAFF_COUNTER
    _STAFF_COUNTER = 0


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
def _session(_engine):
    with Session(_engine) as session:
        yield session


@pytest.fixture
def _app(_session):
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield _session

    app.dependency_overrides[get_db] = override_get_db
    return app


def _client_for(app, staff_dict):
    """Create a TestClient with get_current_staff patched to return staff_dict."""
    p1, p2 = _patch_staff(staff_dict)
    with p1, p2:
        with TestClient(app) as c:
            yield c


@pytest.fixture
def visitor_client(_app):
    yield from _client_for(_app, _staff("visitor"))


@pytest.fixture
def undergrad_client(_app):
    yield from _client_for(_app, _staff("undergrad"))


@pytest.fixture
def grad_client(_app):
    yield from _client_for(_app, _staff("grad_student"))


@pytest.fixture
def admin_client(_app):
    yield from _client_for(_app, _staff("admin"))


@pytest.fixture
def pi_client(_app):
    yield from _client_for(_app, _staff("pi"))


# Seed helpers


def _seed_vendor(session: Session) -> int:
    from lab_manager.models.vendor import Vendor

    v = Vendor(name="TestVendor")
    session.add(v)
    session.flush()
    session.refresh(v)
    return v.id


def _create_request(client, **overrides):
    body = {
        "description": "96-well PCR plates",
        "quantity": "10",
        "unit": "pack",
        "estimated_price": "45.00",
        "justification": "Running qPCR experiment next week",
        "urgency": "normal",
    }
    body.update(overrides)
    return client.post("/api/v1/requests/", json=body)


# ---------------------------------------------------------------------------
# visitor / undergrad: no request_order permission
# ---------------------------------------------------------------------------


class TestVisitorDenied:
    def test_cannot_create(self, visitor_client):
        resp = _create_request(visitor_client)
        assert resp.status_code == 403

    def test_cannot_list(self, visitor_client):
        resp = visitor_client.get("/api/v1/requests/")
        assert resp.status_code == 403

    def test_cannot_get_stats(self, visitor_client):
        resp = visitor_client.get("/api/v1/requests/stats")
        assert resp.status_code == 403

    def test_cannot_get_detail(self, visitor_client):
        resp = visitor_client.get("/api/v1/requests/1")
        assert resp.status_code == 403

    def test_cannot_cancel(self, visitor_client):
        resp = visitor_client.post("/api/v1/requests/1/cancel")
        assert resp.status_code == 403

    def test_cannot_approve(self, visitor_client):
        resp = visitor_client.post("/api/v1/requests/1/approve", json={})
        assert resp.status_code == 403

    def test_cannot_reject(self, visitor_client):
        resp = visitor_client.post("/api/v1/requests/1/reject", json={})
        assert resp.status_code == 403


class TestUndergradDenied:
    def test_cannot_create(self, undergrad_client):
        resp = _create_request(undergrad_client)
        assert resp.status_code == 403

    def test_cannot_list(self, undergrad_client):
        resp = undergrad_client.get("/api/v1/requests/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# grad_student: has request_order but NOT approve_order_requests
# ---------------------------------------------------------------------------


class TestGradStudentCanRequest:
    def test_can_create(self, grad_client):
        resp = _create_request(grad_client)
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_can_list_own(self, grad_client):
        resp = grad_client.get("/api/v1/requests/")
        assert resp.status_code == 200

    def test_can_get_stats(self, grad_client):
        resp = grad_client.get("/api/v1/requests/stats")
        assert resp.status_code == 200

    def test_can_get_own_detail(self, grad_client):
        create_resp = _create_request(grad_client)
        req_id = create_resp.json()["id"]
        resp = grad_client.get(f"/api/v1/requests/{req_id}")
        assert resp.status_code == 200

    def test_can_cancel_own(self, grad_client):
        create_resp = _create_request(grad_client)
        req_id = create_resp.json()["id"]
        resp = grad_client.post(f"/api/v1/requests/{req_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


class TestGradStudentCannotApprove:
    def test_cannot_approve(self, grad_client):
        resp = grad_client.post("/api/v1/requests/1/approve", json={})
        assert resp.status_code == 403

    def test_cannot_reject(self, grad_client):
        resp = grad_client.post("/api/v1/requests/1/reject", json={})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# admin / pi: has approve_order_requests
# ---------------------------------------------------------------------------


class TestAdminCanApprove:
    def test_can_approve(self, admin_client, _session):
        vid = _seed_vendor(_session)
        create_resp = _create_request(admin_client, vendor_id=vid)
        req_id = create_resp.json()["id"]
        resp = admin_client.post(
            f"/api/v1/requests/{req_id}/approve",
            json={"note": "Approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["order_id"] is not None

    def test_can_reject(self, admin_client):
        create_resp = _create_request(admin_client)
        req_id = create_resp.json()["id"]
        resp = admin_client.post(
            f"/api/v1/requests/{req_id}/reject",
            json={"note": "Rejected"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"


class TestPiCanApprove:
    def test_can_approve(self, pi_client, _session):
        vid = _seed_vendor(_session)
        create_resp = _create_request(pi_client, vendor_id=vid)
        req_id = create_resp.json()["id"]
        resp = pi_client.post(
            f"/api/v1/requests/{req_id}/approve",
            json={"note": "Approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Owner-scoping: cancel only own request
# ---------------------------------------------------------------------------


class TestOwnerScoping:
    def test_cancel_own_request(self, grad_client):
        create_resp = _create_request(grad_client)
        req_id = create_resp.json()["id"]
        resp = grad_client.post(f"/api/v1/requests/{req_id}/cancel")
        assert resp.status_code == 200

    def test_cannot_cancel_others_request(self, _app, _session):
        """grad_student A creates, grad_student B cannot cancel it."""
        staff_a = _staff("grad_student")
        staff_b = _staff("grad_student")

        # A creates
        p1a, p2a = _patch_staff(staff_a)
        with p1a, p2a:
            with TestClient(_app) as c:
                create_resp = _create_request(c)
                req_id = create_resp.json()["id"]

        # B tries to cancel A's request
        p1b, p2b = _patch_staff(staff_b)
        with p1b, p2b:
            with TestClient(_app) as c:
                resp = c.post(f"/api/v1/requests/{req_id}/cancel")
                assert resp.status_code == 403

    def test_admin_sees_all_requests(self, admin_client, _app, _session):
        """Admin list should see requests from other users."""
        staff_other = _staff("grad_student")
        p1, p2 = _patch_staff(staff_other)
        with p1, p2:
            with TestClient(_app) as c:
                _create_request(c)

        resp = admin_client.get("/api/v1/requests/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
