"""Tests for PO# duplicate detection (TODO-14).

Covers:
- find_duplicate_po: duplicate found (same vendor)
- find_duplicate_po: no duplicate (unique PO)
- find_duplicate_po: same PO, different vendor → not a duplicate
- find_duplicate_po: duplicate cancelled/deleted orders are ignored
- find_duplicate_po: empty / None PO number is a no-op
- find_duplicate_po: exclude_order_id skips self (for PATCH flows)
- API POST /orders/: duplicate triggers _duplicate_warning in response
- API POST /orders/: no duplicate → clean response, no warning key
- API POST /orders/: different vendor, same PO → no warning
"""

import pytest

from lab_manager.models.order import Order
from lab_manager.services.orders import build_duplicate_warning, find_duplicate_po


# ---------------------------------------------------------------------------
# Service-layer unit tests (use db_session directly)
# ---------------------------------------------------------------------------


def _make_order(db, *, po_number, vendor_id=None, status="pending"):
    o = Order(po_number=po_number, vendor_id=vendor_id, status=status)
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


class TestFindDuplicatePo:
    def test_duplicate_found_same_vendor(self, db_session):
        """Same PO + same vendor → duplicate returned."""
        existing = _make_order(db_session, po_number="PO-100", vendor_id=1)
        dupes = find_duplicate_po("PO-100", 1, db_session)
        assert len(dupes) == 1
        assert dupes[0].id == existing.id

    def test_no_duplicate_unique_po(self, db_session):
        """Different PO number → no duplicate."""
        _make_order(db_session, po_number="PO-200", vendor_id=1)
        dupes = find_duplicate_po("PO-999", 1, db_session)
        assert dupes == []

    def test_different_vendor_same_po_not_duplicate(self, db_session):
        """Same PO number but different vendor → not a duplicate."""
        _make_order(db_session, po_number="PO-300", vendor_id=10)
        # vendor_id=20 is a different vendor — should not match
        dupes = find_duplicate_po("PO-300", 20, db_session)
        assert dupes == []

    def test_cancelled_orders_ignored(self, db_session):
        """Cancelled orders must not trigger a duplicate warning."""
        _make_order(db_session, po_number="PO-400", vendor_id=1, status="cancelled")
        dupes = find_duplicate_po("PO-400", 1, db_session)
        assert dupes == []

    def test_deleted_orders_ignored(self, db_session):
        """Soft-deleted orders must not trigger a duplicate warning."""
        _make_order(db_session, po_number="PO-500", vendor_id=1, status="deleted")
        dupes = find_duplicate_po("PO-500", 1, db_session)
        assert dupes == []

    def test_empty_po_number_returns_empty(self, db_session):
        """Empty / whitespace PO number → always returns []."""
        _make_order(db_session, po_number="", vendor_id=1)
        for bad_po in ("", "   ", None):
            dupes = find_duplicate_po(bad_po, 1, db_session)
            assert dupes == [], f"Expected [] for po_number={bad_po!r}"

    def test_exclude_order_id_skips_self(self, db_session):
        """When updating an existing order, its own ID must not count as a duplicate."""
        order = _make_order(db_session, po_number="PO-600", vendor_id=1)
        dupes = find_duplicate_po("PO-600", 1, db_session, exclude_order_id=order.id)
        assert dupes == []

    def test_vendor_id_none_matches_any_vendor(self, db_session):
        """When vendor_id is None, match on PO number alone (vendor-agnostic check)."""
        existing = _make_order(db_session, po_number="PO-700", vendor_id=5)
        dupes = find_duplicate_po("PO-700", None, db_session)
        assert len(dupes) == 1
        assert dupes[0].id == existing.id


class TestBuildDuplicateWarning:
    def test_warning_structure(self, db_session):
        """build_duplicate_warning returns expected keys."""
        o1 = _make_order(db_session, po_number="PO-800", vendor_id=1)
        o2 = _make_order(db_session, po_number="PO-800", vendor_id=1)
        warning = build_duplicate_warning([o1, o2])
        assert warning["warning"] == "duplicate_po_number"
        assert set(warning["duplicate_order_ids"]) == {o1.id, o2.id}
        assert "message" in warning


# ---------------------------------------------------------------------------
# API integration tests (use the TestClient via the `client` fixture)
# ---------------------------------------------------------------------------


class TestCreateOrderDuplicateApi:
    def test_no_duplicate_clean_response(self, client):
        """Creating an order with a unique PO returns the order without warning."""
        resp = client.post(
            "/api/orders/",
            json={"po_number": "UNIQUE-001", "status": "pending"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert (
            data.get("po_number") == "UNIQUE-001"
            or data.get("order", {}).get("po_number") == "UNIQUE-001"
        )
        assert "_duplicate_warning" not in data

    def test_duplicate_triggers_warning_same_vendor(self, client):
        """Creating a second order with the same PO+vendor returns a warning."""
        vendor_resp = client.post("/api/vendors/", json={"name": "DupVendor"})
        vid = vendor_resp.json()["id"]

        # First order — unique
        r1 = client.post(
            "/api/orders/",
            json={"po_number": "DUP-001", "vendor_id": vid, "status": "pending"},
        )
        assert r1.status_code == 201
        assert "_duplicate_warning" not in r1.json()

        # Second order — duplicate
        r2 = client.post(
            "/api/orders/",
            json={"po_number": "DUP-001", "vendor_id": vid, "status": "pending"},
        )
        assert r2.status_code == 201  # still 201 — duplicates warn, not block
        data = r2.json()
        assert "_duplicate_warning" in data
        warning = data["_duplicate_warning"]
        assert warning["warning"] == "duplicate_po_number"
        assert len(warning["duplicate_order_ids"]) >= 1

    def test_different_vendor_same_po_no_warning(self, client):
        """Same PO# for a different vendor must not trigger a warning."""
        v1 = client.post("/api/vendors/", json={"name": "VendorA"}).json()["id"]
        v2 = client.post("/api/vendors/", json={"name": "VendorB"}).json()["id"]

        client.post(
            "/api/orders/",
            json={"po_number": "SHARED-001", "vendor_id": v1, "status": "pending"},
        )
        resp = client.post(
            "/api/orders/",
            json={"po_number": "SHARED-001", "vendor_id": v2, "status": "pending"},
        )
        assert resp.status_code == 201
        assert "_duplicate_warning" not in resp.json()

    def test_no_po_number_no_warning(self, client):
        """Order without a PO# must never produce a warning."""
        resp = client.post("/api/orders/", json={"status": "pending"})
        assert resp.status_code == 201
        assert "_duplicate_warning" not in resp.json()

    @pytest.mark.parametrize("cancelled_status", ["cancelled", "deleted"])
    def test_cancelled_or_deleted_does_not_trigger_warning(
        self, client, cancelled_status
    ):
        """A cancelled/deleted order with the same PO must not trigger a warning."""
        vendor_resp = client.post(
            "/api/vendors/", json={"name": f"V-{cancelled_status}"}
        )
        vid = vendor_resp.json()["id"]

        # First order — then soft-cancel / delete it
        r1 = client.post(
            "/api/orders/",
            json={
                "po_number": f"INACT-{cancelled_status}",
                "vendor_id": vid,
                "status": cancelled_status,
            },
        )
        assert r1.status_code == 201

        # Second order with same PO — the previous inactive one should be ignored
        r2 = client.post(
            "/api/orders/",
            json={
                "po_number": f"INACT-{cancelled_status}",
                "vendor_id": vid,
                "status": "pending",
            },
        )
        assert r2.status_code == 201
        assert "_duplicate_warning" not in r2.json()
