"""Integration tests for the order receiving workflow.

Tests the full lifecycle: create order -> add items -> status transitions.
Uses the standard conftest client fixture (SQLite DB with TestClient).
"""

import pytest


@pytest.fixture()
def vendor(client):
    """Create a test vendor."""
    r = client.post("/api/v1/vendors/", json={"name": "Receiving Test Vendor"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_order(client, vendor_id, po_number):
    """Helper to create an order and return the order dict."""
    r = client.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor_id,
            "po_number": po_number,
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["order"]


class TestCreateOrder:
    """Creating purchase orders."""

    def test_create_order_basic(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-001")
        assert order["status"] == "pending"
        assert order["po_number"] == "PO-RCV-001"
        assert "id" in order

    def test_create_order_must_be_pending(self, client, vendor):
        r = client.post(
            "/api/v1/orders/",
            json={
                "vendor_id": vendor["id"],
                "po_number": "PO-RCV-NOTE-001",
                "status": "received",
            },
        )
        assert r.status_code == 422

    def test_create_order_with_po_number(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-NOTE-002")
        assert order["po_number"] == "PO-RCV-NOTE-002"


class TestOrderItems:
    """Adding and managing order items."""

    def test_add_single_item(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-ITEM-001")
        ri = client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": "CAT-RCV-001",
                "description": "Ethanol 200 Proof 500mL",
                "quantity": 10,
                "unit": "EA",
            },
        )
        assert ri.status_code in (200, 201), ri.text
        item = ri.json()
        assert item["catalog_number"] == "CAT-RCV-001"
        assert float(item["quantity"]) == 10
        # Verify items count
        r_items = client.get(f"/api/v1/orders/{order['id']}/items")
        assert r_items.status_code == 200
        assert r_items.json()["total"] == 1

    def test_add_multiple_items(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-ITEM-002")
        items_data = [
            {
                "catalog_number": "CAT-RCV-A",
                "description": "NaCl",
                "quantity": 5,
                "unit": "KG",
            },
            {
                "catalog_number": "CAT-RCV-B",
                "description": "HCl",
                "quantity": 2,
                "unit": "L",
            },
            {
                "catalog_number": "CAT-RCV-C",
                "description": "Slides",
                "quantity": 100,
                "unit": "EA",
            },
        ]
        for item_json in items_data:
            ri = client.post(
                f"/api/v1/orders/{order['id']}/items",
                json=item_json,
            )
            assert ri.status_code in (200, 201), ri.text
        r_items = client.get(f"/api/v1/orders/{order['id']}/items")
        assert r_items.json()["total"] == 3
        catalogs = [i["catalog_number"] for i in r_items.json()["items"]]
        assert set(catalogs) == {"CAT-RCV-A", "CAT-RCV-B", "CAT-RCV-C"}

    def test_update_item_quantity(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-ITEM-003")
        ri = client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": "CAT-UPD",
                "description": "Original",
                "quantity": 5,
                "unit": "EA",
            },
        )
        assert ri.status_code in (200, 201), ri.text
        item = ri.json()
        rup = client.patch(
            f"/api/v1/orders/{order['id']}/items/{item['id']}",
            json={"quantity": 50},
        )
        assert rup.status_code == 200, rup.text
        assert float(rup.json()["quantity"]) == 50

    def test_delete_item(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-ITEM-DEL")
        ri = client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": "CAT-DEL",
                "description": "Delete me",
                "quantity": 1,
                "unit": "EA",
            },
        )
        assert ri.status_code in (200, 201)
        item = ri.json()
        rdel = client.delete(f"/api/v1/orders/{order['id']}/items/{item['id']}")
        assert rdel.status_code in (200, 204)
        r_items = client.get(f"/api/v1/orders/{order['id']}/items")
        assert r_items.json()["total"] == 0


class TestOrderStatusTransitions:
    """Order status lifecycle: pending -> shipped -> received."""

    def test_pending_to_shipped(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-STS-001")
        rup = client.patch(
            f"/api/v1/orders/{order['id']}",
            json={"status": "shipped"},
        )
        assert rup.status_code == 200, rup.text
        assert rup.json()["status"] == "shipped"

    def test_pending_to_cancelled(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-STS-002")
        rup = client.patch(
            f"/api/v1/orders/{order['id']}",
            json={"status": "cancelled"},
        )
        assert rup.status_code == 200, rup.text
        assert rup.json()["status"] == "cancelled"

    def test_shipped_to_received(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-STS-003")
        # pending -> shipped
        client.patch(f"/api/v1/orders/{order['id']}", json={"status": "shipped"})
        # shipped -> received
        rup = client.patch(
            f"/api/v1/orders/{order['id']}",
            json={"status": "received"},
        )
        assert rup.status_code == 200, rup.text
        assert rup.json()["status"] == "received"

    def test_pending_to_received_rejected(self, client, vendor):
        """Cannot go directly from pending to received."""
        order = _create_order(client, vendor["id"], "PO-RCV-STS-004")
        rup = client.patch(
            f"/api/v1/orders/{order['id']}",
            json={"status": "received"},
        )
        assert rup.status_code == 422

    def test_invalid_status_rejected(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-STS-005")
        rup = client.patch(
            f"/api/v1/orders/{order['id']}",
            json={"status": "ordered"},
        )
        assert rup.status_code == 422


class TestDeleteOrder:
    """Soft-deleting orders."""

    def test_delete_pending_order(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-DEL-001")
        rdel = client.delete(f"/api/v1/orders/{order['id']}")
        assert rdel.status_code == 204
        # Soft-delete: order still exists but status = deleted
        rget = client.get(f"/api/v1/orders/{order['id']}")
        assert rget.status_code == 200
        assert rget.json()["status"] == "deleted"

    def test_delete_order_with_items(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-DEL-002")
        client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": "CAT-DEL",
                "description": "Delete test",
                "quantity": 1,
                "unit": "EA",
            },
        )
        rdel = client.delete(f"/api/v1/orders/{order['id']}")
        assert rdel.status_code == 204


class TestListAndFilterOrders:
    """Listing and filtering orders."""

    def test_list_all_orders(self, client, vendor):
        for i in range(3):
            _create_order(client, vendor["id"], f"PO-RCV-LIST-{i:03d}")
        r = client.get("/api/v1/orders/")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 3

    def test_list_by_status(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-FILT-001")
        # Update to shipped
        client.patch(f"/api/v1/orders/{order['id']}", json={"status": "shipped"})
        # Filter by shipped
        rlist = client.get("/api/v1/orders/?status=shipped")
        assert rlist.status_code == 200
        for item in rlist.json()["items"]:
            assert item["status"] == "shipped"

    def test_search_by_po_number(self, client, vendor):
        _create_order(client, vendor["id"], "PO-RCV-UNIQUE-XYZ-999")
        r = client.get("/api/v1/orders/?search=RCV-UNIQUE-XYZ")
        assert r.status_code == 200
        po_numbers = [o["po_number"] for o in r.json()["items"]]
        assert "PO-RCV-UNIQUE-XYZ-999" in po_numbers

    def test_pagination(self, client, vendor):
        for i in range(5):
            _create_order(client, vendor["id"], f"PO-RCV-PAGE-{i:03d}")
        r = client.get("/api/v1/orders/?page_size=2")
        assert r.status_code == 200
        data = r.json()
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2


class TestOrderDetail:
    """Getting order detail with nested data."""

    def test_get_detail(self, client, vendor):
        order = _create_order(client, vendor["id"], "PO-RCV-DETAIL-001")
        client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": "CAT-DET-A",
                "description": "Item A",
                "quantity": 10,
                "unit": "EA",
            },
        )
        client.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": "CAT-DET-B",
                "description": "Item B",
                "quantity": 5,
                "unit": "L",
            },
        )
        rdet = client.get(f"/api/v1/orders/{order['id']}")
        assert rdet.status_code == 200
        detail = rdet.json()
        assert detail["po_number"] == "PO-RCV-DETAIL-001"
        assert detail["vendor_id"] == vendor["id"]
        # Verify items
        ritems = client.get(f"/api/v1/orders/{order['id']}/items")
        assert ritems.status_code == 200
        items = ritems.json()["items"]
        assert len(items) == 2
        catalogs = {i["catalog_number"] for i in items}
        assert catalogs == {"CAT-DET-A", "CAT-DET-B"}
