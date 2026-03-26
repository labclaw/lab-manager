"""Tests for supply request and approval workflow."""

import pytest
from lab_manager.models.staff import Staff
from lab_manager.models.vendor import Vendor


@pytest.fixture
def _seed_staff(db_session):
    """Create staff members for testing: admin (PI) and student (member)."""
    admin = Staff(name="pi_user", email="pi@lab.edu", role="pi", is_active=True)
    student = Staff(
        name="grad_student", email="student@lab.edu", role="member", is_active=True
    )
    vendor = Vendor(name="TestVendor")
    db_session.add_all([admin, student, vendor])
    db_session.flush()
    return {"admin": admin, "student": student, "vendor": vendor}


@pytest.fixture
def admin_client(client, _seed_staff):
    """Client that sends requests as PI user."""
    client.headers["X-User"] = "pi_user"
    return client


@pytest.fixture
def student_client(client, _seed_staff):
    """Client that sends requests as grad student."""
    client.headers["X-User"] = "grad_student"
    return client


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
    return c.post("/api/v1/requests", json=body)


# --- Test: Create request ---


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


# --- Test: List requests ---


def test_list_requests_student_sees_own(student_client, admin_client):
    """Students only see their own requests."""
    _create_request(student_client)
    _create_request(student_client)

    resp = student_client.get("/api/v1/requests")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2

    # Admin can see all
    resp = admin_client.get("/api/v1/requests")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 2


def test_list_requests_filter_status(student_client):
    _create_request(student_client)
    resp = student_client.get("/api/v1/requests?status=pending")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# --- Test: Get request detail ---


def test_get_request_detail(student_client):
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = student_client.get(f"/api/v1/requests/{req_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == req_id


def test_get_request_other_student_forbidden(client, _seed_staff):
    """A student cannot view a request created by someone else."""
    # Create as PI
    client.headers["X-User"] = "pi_user"
    resp = _create_request(client)
    req_id = resp.json()["id"]

    # Try to read as student
    client.headers["X-User"] = "grad_student"
    resp = client.get(f"/api/v1/requests/{req_id}")
    assert resp.status_code == 403


# --- Test: Approve creates Order ---


def test_approve_creates_order(student_client, admin_client, _seed_staff):
    vendor_id = _seed_staff["vendor"].id
    resp = _create_request(student_client, catalog_number="PCR-96", vendor_id=vendor_id)
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


def test_approve_not_pending_fails(student_client, admin_client, _seed_staff):
    vendor_id = _seed_staff["vendor"].id
    resp = _create_request(student_client, vendor_id=vendor_id)
    req_id = resp.json()["id"]

    # Approve once
    admin_client.post(f"/api/v1/requests/{req_id}/approve", json={})
    # Try to approve again
    resp = admin_client.post(f"/api/v1/requests/{req_id}/approve", json={})
    assert resp.status_code == 409


def test_approve_by_student_forbidden(student_client):
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = student_client.post(f"/api/v1/requests/{req_id}/approve", json={})
    assert resp.status_code == 403


# --- Test: Reject ---


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
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = student_client.post(f"/api/v1/requests/{req_id}/reject", json={})
    assert resp.status_code == 403


# --- Test: Cancel ---


def test_cancel_own_request(student_client):
    resp = _create_request(student_client)
    req_id = resp.json()["id"]

    resp = student_client.post(f"/api/v1/requests/{req_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_others_request_forbidden(client, _seed_staff):
    """Student cannot cancel admin's request."""
    client.headers["X-User"] = "pi_user"
    resp = _create_request(client)
    req_id = resp.json()["id"]

    client.headers["X-User"] = "grad_student"
    resp = client.post(f"/api/v1/requests/{req_id}/cancel")
    assert resp.status_code == 403


def test_cancel_non_pending_fails(student_client, admin_client, _seed_staff):
    vendor_id = _seed_staff["vendor"].id
    resp = _create_request(student_client, vendor_id=vendor_id)
    req_id = resp.json()["id"]

    admin_client.post(f"/api/v1/requests/{req_id}/approve", json={})
    resp = student_client.post(f"/api/v1/requests/{req_id}/cancel")
    assert resp.status_code == 409


# --- Test: Stats ---


def test_request_stats(student_client, admin_client, _seed_staff):
    vendor_id = _seed_staff["vendor"].id
    _create_request(student_client)
    _create_request(student_client)

    resp2 = _create_request(student_client, vendor_id=vendor_id)
    req_id = resp2.json()["id"]
    admin_client.post(f"/api/v1/requests/{req_id}/approve", json={})

    resp = student_client.get("/api/v1/requests/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pending"] == 2
    assert data["approved"] == 1
    assert data["total"] == 3


# --- Test: Not found ---


def test_get_nonexistent_request(student_client):
    resp = student_client.get("/api/v1/requests/9999")
    assert resp.status_code == 404


def test_approve_nonexistent_request(admin_client):
    resp = admin_client.post("/api/v1/requests/9999/approve", json={})
    assert resp.status_code == 404
