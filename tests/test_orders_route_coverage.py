"""Tests for api/routes/orders.py -- cover status transitions, item CRUD,
list filters, create guards, update guards, delete, receive."""

import os
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from lab_manager.api.routes.orders import (
    OrderCreate,
    OrderItemCreate,
    OrderItemUpdate,
    OrderUpdate,
    _ensure_order_mutable,
    _get_order_item_or_raise,
    _validate_status_transition,
)
from lab_manager.exceptions import NotFoundError, ValidationError
from lab_manager.models.order import Order, OrderItem, OrderStatus


# ---- Unit tests: _validate_status_transition ----


class TestValidateStatusTransition:
    """Cover all valid and invalid status transitions."""

    def test_pending_to_shipped(self):
        _validate_status_transition("pending", "shipped")

    def test_pending_to_cancelled(self):
        _validate_status_transition("pending", "cancelled")

    def test_pending_to_deleted(self):
        _validate_status_transition("pending", "deleted")

    def test_shipped_to_received(self):
        _validate_status_transition("shipped", "received")

    def test_shipped_to_cancelled(self):
        _validate_status_transition("shipped", "cancelled")

    def test_shipped_to_deleted(self):
        _validate_status_transition("shipped", "deleted")

    def test_received_to_deleted(self):
        _validate_status_transition("received", "deleted")

    def test_invalid_transition_pending_to_received(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("pending", "received")

    def test_invalid_transition_shipped_to_pending(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("shipped", "pending")

    def test_invalid_transition_received_to_pending(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("received", "pending")

    def test_invalid_transition_cancelled_to_any(self):
        """cancelled is a terminal status -- no transitions defined."""
        with pytest.raises(ValidationError, match="terminal status"):
            _validate_status_transition("cancelled", "pending")

    def test_invalid_transition_deleted_to_any(self):
        """deleted is a terminal status -- no transitions defined."""
        with pytest.raises(ValidationError, match="terminal status"):
            _validate_status_transition("deleted", "pending")

    def test_invalid_transition_unknown_status(self):
        with pytest.raises(ValidationError, match="Invalid status transition"):
            _validate_status_transition("unknown_status", "pending")


# ---- Unit tests: _get_order_item_or_raise ----


class TestGetOrderItemOrRaise:
    def test_item_found(self, db_session):
        order = Order(status="pending")
        db_session.add(order)
        db_session.flush()
        item = OrderItem(order_id=order.id, catalog_number="CAT-001", quantity=1)
        db_session.add(item)
        db_session.flush()
        result = _get_order_item_or_raise(db_session, order.id, item.id)
        assert result.id == item.id

    def test_item_not_found(self, db_session):
        order = Order(status="pending")
        db_session.add(order)
        db_session.flush()
        with pytest.raises(NotFoundError, match="Order item"):
            _get_order_item_or_raise(db_session, order.id, 99999)

    def test_item_wrong_order(self, db_session):
        order1 = Order(status="pending")
        order2 = Order(status="pending")
        db_session.add_all([order1, order2])
        db_session.flush()
        item = OrderItem(order_id=order1.id, catalog_number="CAT-002", quantity=1)
        db_session.add(item)
        db_session.flush()
        # Item belongs to order1, querying with order2 should not find it
        with pytest.raises(NotFoundError):
            _get_order_item_or_raise(db_session, order2.id, item.id)


# ---- Unit tests: _ensure_order_mutable ----


class TestEnsureOrderMutable:
    def test_pending_is_mutable(self):
        order = Order(status="pending")
        _ensure_order_mutable(order)  # should not raise

    def test_shipped_is_mutable(self):
        order = Order(status="shipped")
        _ensure_order_mutable(order)  # should not raise

    def test_received_is_immutable(self):
        order = Order(status="received")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)

    def test_cancelled_is_immutable(self):
        order = Order(status="cancelled")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)

    def test_deleted_is_immutable(self):
        order = Order(status="deleted")
        with pytest.raises(ValidationError, match="Cannot modify items"):
            _ensure_order_mutable(order)


# ---- Unit tests: Pydantic schemas ----


class TestOrderCreateSchema:
    def test_default_status_is_pending(self):
        body = OrderCreate()
        assert body.status == "pending"

    def test_valid_statuses(self):
        for s in OrderStatus:
            body = OrderCreate(status=s.value)
            assert body.status == s.value

    def test_invalid_status_raises(self):
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            OrderCreate(status="invalid")

    def test_extra_defaults_to_empty_dict(self):
        body = OrderCreate()
        assert body.extra == {}


class TestOrderUpdateSchema:
    def test_all_none(self):
        body = OrderUpdate()
        assert body.status is None
        assert body.po_number is None
        assert body.extra is None

    def test_valid_status(self):
        body = OrderUpdate(status="shipped")
        assert body.status == "shipped"

    def test_invalid_status_raises(self):
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            OrderUpdate(status="not_a_status")


class TestOrderItemCreateSchema:
    def test_defaults(self):
        body = OrderItemCreate()
        assert body.quantity == Decimal("1")
        assert body.extra == {}

    def test_custom_quantity(self):
        body = OrderItemCreate(quantity=Decimal("5.5"))
        assert body.quantity == Decimal("5.5")

    def test_zero_quantity_rejected(self):
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            OrderItemCreate(quantity=Decimal("0"))


class TestOrderItemUpdateSchema:
    def test_all_none(self):
        body = OrderItemUpdate()
        assert body.quantity is None
        assert body.catalog_number is None


# ---- Fixture for API integration tests ----


@pytest.fixture()
def orders_client(db_session):
    os.environ["AUTH_ENABLED"] = "false"
    from lab_manager.config import get_settings

    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _create_order_via_api(client, **overrides):
    """Helper to create a pending order via the API."""
    body = {"status": "pending"}
    body.update(overrides)
    return client.post("/api/v1/orders/", json=body)


def _seed_order(db_session, status="pending", **kwargs):
    """Create an Order directly in the DB."""
    order = Order(status=status, **kwargs)
    db_session.add(order)
    db_session.flush()
    return order


def _seed_order_item(db_session, order_id, **kwargs):
    """Create an OrderItem directly in the DB."""
    item = OrderItem(order_id=order_id, **kwargs)
    db_session.add(item)
    db_session.flush()
    return item


# ---- list_orders endpoint ----


class TestListOrders:
    def test_list_empty(self, orders_client):
        resp = orders_client.get("/api/v1/orders/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_returns_orders(self, orders_client, db_session):
        _seed_order(db_session, po_number="PO-001")
        _seed_order(db_session, po_number="PO-002")
        resp = orders_client.get("/api/v1/orders/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_filter_by_status(self, orders_client, db_session):
        _seed_order(db_session, status="pending", po_number="P1")
        _seed_order(db_session, status="shipped", po_number="P2")
        resp = orders_client.get("/api/v1/orders/?status=shipped")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["status"] == "shipped" for i in items)

    def test_filter_status_group_active(self, orders_client, db_session):
        _seed_order(db_session, status="pending", po_number="A1")
        _seed_order(db_session, status="shipped", po_number="A2")
        _seed_order(db_session, status="received", po_number="A3")
        _seed_order(db_session, status="cancelled", po_number="A4")
        resp = orders_client.get("/api/v1/orders/?status_group=active")
        assert resp.status_code == 200
        items = resp.json()["items"]
        statuses = {i["status"] for i in items}
        assert "received" not in statuses
        assert "cancelled" not in statuses
        assert "deleted" not in statuses

    def test_filter_status_group_past(self, orders_client, db_session):
        _seed_order(db_session, status="pending", po_number="B1")
        _seed_order(db_session, status="received", po_number="B2")
        _seed_order(db_session, status="cancelled", po_number="B3")
        resp = orders_client.get("/api/v1/orders/?status_group=past")
        assert resp.status_code == 200
        items = resp.json()["items"]
        statuses = {i["status"] for i in items}
        assert statuses <= {"received", "cancelled"}

    def test_filter_status_group_drafts(self, orders_client, db_session):
        # "draft" is not a valid OrderStatus value in the CHECK constraint,
        # so we test that the drafts filter simply returns empty when no
        # draft-status orders exist (drafts is a hypothetical status_group).
        _seed_order(db_session, status="pending", po_number="C1")
        resp = orders_client.get("/api/v1/orders/?status_group=drafts")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 0  # no orders with status == "draft"

    def test_filter_by_vendor_id(self, orders_client, db_session):
        from lab_manager.models.vendor import Vendor

        v1 = Vendor(name="Vendor1")
        v2 = Vendor(name="Vendor2")
        db_session.add_all([v1, v2])
        db_session.flush()
        _seed_order(db_session, vendor_id=v1.id, po_number="V1")
        _seed_order(db_session, vendor_id=v2.id, po_number="V2")
        resp = orders_client.get(f"/api/v1/orders/?vendor_id={v1.id}")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["vendor_id"] == v1.id for i in items)

    def test_filter_by_po_number(self, orders_client, db_session):
        _seed_order(db_session, po_number="PO-FILTER-1")
        _seed_order(db_session, po_number="PO-FILTER-2")
        _seed_order(db_session, po_number="OTHER-PO")
        resp = orders_client.get("/api/v1/orders/?po_number=FILTER")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2

    def test_filter_by_date_from(self, orders_client, db_session):
        _seed_order(db_session, order_date=date(2026, 1, 15), po_number="DF1")
        _seed_order(db_session, order_date=date(2026, 3, 15), po_number="DF2")
        resp = orders_client.get("/api/v1/orders/?date_from=2026-03-01")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["po_number"] == "DF2"

    def test_filter_by_date_to(self, orders_client, db_session):
        _seed_order(db_session, order_date=date(2026, 1, 15), po_number="DT1")
        _seed_order(db_session, order_date=date(2026, 3, 15), po_number="DT2")
        resp = orders_client.get("/api/v1/orders/?date_to=2026-02-01")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["po_number"] == "DT1"

    def test_filter_by_received_by(self, orders_client, db_session):
        _seed_order(db_session, received_by="Alice", po_number="RB1")
        _seed_order(db_session, received_by="Bob", po_number="RB2")
        resp = orders_client.get("/api/v1/orders/?received_by=Alice")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1

    def test_sort_by_po_number_desc(self, orders_client, db_session):
        _seed_order(db_session, po_number="AAA")
        _seed_order(db_session, po_number="ZZZ")
        resp = orders_client.get("/api/v1/orders/?sort_by=po_number&sort_dir=desc")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert items[0]["po_number"] == "ZZZ"

    def test_invalid_sort_by_defaults_to_id(self, orders_client, db_session):
        resp = orders_client.get("/api/v1/orders/?sort_by=not_a_column")
        assert resp.status_code == 200


# ---- create_order endpoint ----


class TestCreateOrder:
    def test_create_pending_order(self, orders_client):
        resp = _create_order_via_api(orders_client, po_number="PO-NEW")
        assert resp.status_code == 201
        data = resp.json()
        assert data["order"]["status"] == "pending"
        assert data["order"]["po_number"] == "PO-NEW"
        assert data["_duplicate_warning"] is None

    def test_create_non_pending_rejected(self, orders_client):
        resp = _create_order_via_api(orders_client, status="shipped")
        assert resp.status_code == 422
        assert "pending" in resp.json()["detail"].lower()

    def test_create_with_all_fields(self, orders_client):
        resp = _create_order_via_api(
            orders_client,
            po_number="PO-FULL",
            order_date="2026-03-28",
            delivery_number="DEL-001",
            invoice_number="INV-001",
            extra={"note": "rush"},
        )
        assert resp.status_code == 201
        data = resp.json()["order"]
        assert data["delivery_number"] == "DEL-001"
        assert data["invoice_number"] == "INV-001"
        assert data["extra"]["note"] == "rush"

    def test_duplicate_po_warning(self, orders_client, db_session):
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="DupVendor")
        db_session.add(vendor)
        db_session.flush()

        # Create first order
        _seed_order(
            db_session,
            status="pending",
            po_number="PO-DUP",
            vendor_id=vendor.id,
        )

        # Create second with same PO
        resp = _create_order_via_api(
            orders_client, po_number="PO-DUP", vendor_id=vendor.id
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["_duplicate_warning"] is not None
        assert data["_duplicate_warning"]["warning"] == "duplicate_po_number"

    def test_duplicate_po_no_warning_when_no_po(self, orders_client):
        resp = _create_order_via_api(orders_client)
        assert resp.status_code == 201
        assert resp.json()["_duplicate_warning"] is None


# ---- get_order endpoint ----


class TestGetOrder:
    def test_get_existing(self, orders_client, db_session):
        order = _seed_order(db_session, po_number="PO-GET")
        resp = orders_client.get(f"/api/v1/orders/{order.id}")
        assert resp.status_code == 200
        assert resp.json()["po_number"] == "PO-GET"

    def test_get_not_found(self, orders_client):
        resp = orders_client.get("/api/v1/orders/99999")
        assert resp.status_code == 404


# ---- update_order endpoint ----


class TestUpdateOrder:
    def test_update_po_number(self, orders_client, db_session):
        order = _seed_order(db_session)
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}", json={"po_number": "PO-UPDATED"}
        )
        assert resp.status_code == 200
        assert resp.json()["po_number"] == "PO-UPDATED"

    def test_update_status_transition(self, orders_client, db_session):
        order = _seed_order(db_session, status="pending")
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}", json={"status": "shipped"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"

    def test_update_invalid_status_transition(self, orders_client, db_session):
        order = _seed_order(db_session, status="pending")
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}", json={"status": "received"}
        )
        assert resp.status_code == 422

    def test_update_not_found(self, orders_client):
        resp = orders_client.patch("/api/v1/orders/99999", json={"po_number": "X"})
        assert resp.status_code == 404

    def test_update_multiple_fields(self, orders_client, db_session):
        order = _seed_order(db_session)
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}",
            json={
                "po_number": "PO-MULTI",
                "delivery_number": "DEL-MULTI",
                "invoice_number": "INV-MULTI",
                "extra": {"key": "value"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["po_number"] == "PO-MULTI"
        assert data["delivery_number"] == "DEL-MULTI"
        assert data["extra"]["key"] == "value"


# ---- delete_order endpoint ----


class TestDeleteOrder:
    def test_soft_delete(self, orders_client, db_session):
        order = _seed_order(db_session, status="pending")
        resp = orders_client.delete(f"/api/v1/orders/{order.id}")
        assert resp.status_code == 204
        db_session.refresh(order)
        assert order.status == "deleted"

    def test_delete_not_found(self, orders_client):
        resp = orders_client.delete("/api/v1/orders/99999")
        assert resp.status_code == 404


# ---- Order Items: list ----


class TestListOrderItems:
    def test_list_items(self, orders_client, db_session):
        order = _seed_order(db_session)
        _seed_order_item(db_session, order.id, catalog_number="CAT-A")
        _seed_order_item(db_session, order.id, catalog_number="CAT-B")
        resp = orders_client.get(f"/api/v1/orders/{order.id}/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_list_items_order_not_found(self, orders_client):
        resp = orders_client.get("/api/v1/orders/99999/items")
        assert resp.status_code == 404

    def test_filter_by_catalog_number(self, orders_client, db_session):
        order = _seed_order(db_session)
        _seed_order_item(db_session, order.id, catalog_number="CAT-FILTER")
        _seed_order_item(db_session, order.id, catalog_number="CAT-OTHER")
        resp = orders_client.get(
            f"/api/v1/orders/{order.id}/items?catalog_number=FILTER"
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["catalog_number"] == "CAT-FILTER"

    def test_filter_by_lot_number(self, orders_client, db_session):
        order = _seed_order(db_session)
        _seed_order_item(db_session, order.id, lot_number="LOT-001")
        _seed_order_item(db_session, order.id, lot_number="LOT-002")
        resp = orders_client.get(f"/api/v1/orders/{order.id}/items?lot_number=LOT-001")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1


# ---- Order Items: create ----


class TestCreateOrderItem:
    def test_create_item(self, orders_client, db_session):
        order = _seed_order(db_session, status="pending")
        resp = orders_client.post(
            f"/api/v1/orders/{order.id}/items",
            json={
                "catalog_number": "CAT-NEW",
                "description": "A new item",
                "quantity": "3.5",
                "unit": "EA",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["catalog_number"] == "CAT-NEW"
        assert data["quantity"] == "3.5000"

    def test_create_item_on_received_order_rejected(self, orders_client, db_session):
        order = _seed_order(db_session, status="received")
        resp = orders_client.post(
            f"/api/v1/orders/{order.id}/items",
            json={"catalog_number": "CAT-X", "quantity": "1"},
        )
        assert resp.status_code == 422

    def test_create_item_on_cancelled_order_rejected(self, orders_client, db_session):
        order = _seed_order(db_session, status="cancelled")
        resp = orders_client.post(
            f"/api/v1/orders/{order.id}/items",
            json={"catalog_number": "CAT-X", "quantity": "1"},
        )
        assert resp.status_code == 422

    def test_create_item_on_deleted_order_rejected(self, orders_client, db_session):
        order = _seed_order(db_session, status="deleted")
        resp = orders_client.post(
            f"/api/v1/orders/{order.id}/items",
            json={"catalog_number": "CAT-X", "quantity": "1"},
        )
        assert resp.status_code == 422

    def test_create_item_order_not_found(self, orders_client):
        resp = orders_client.post(
            "/api/v1/orders/99999/items",
            json={"quantity": "1"},
        )
        assert resp.status_code == 404


# ---- Order Items: get ----


class TestGetOrderItem:
    def test_get_existing_item(self, orders_client, db_session):
        order = _seed_order(db_session)
        item = _seed_order_item(db_session, order.id, catalog_number="CAT-GET")
        resp = orders_client.get(f"/api/v1/orders/{order.id}/items/{item.id}")
        assert resp.status_code == 200
        assert resp.json()["catalog_number"] == "CAT-GET"

    def test_get_item_not_found(self, orders_client, db_session):
        order = _seed_order(db_session)
        resp = orders_client.get(f"/api/v1/orders/{order.id}/items/99999")
        assert resp.status_code == 404


# ---- Order Items: update ----


class TestUpdateOrderItem:
    def test_update_item(self, orders_client, db_session):
        order = _seed_order(db_session, status="pending")
        item = _seed_order_item(db_session, order.id, catalog_number="CAT-OLD")
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}/items/{item.id}",
            json={"catalog_number": "CAT-NEW", "quantity": "10"},
        )
        assert resp.status_code == 200
        assert resp.json()["catalog_number"] == "CAT-NEW"

    def test_update_item_on_received_order_rejected(self, orders_client, db_session):
        order = _seed_order(db_session, status="received")
        item = _seed_order_item(db_session, order.id, catalog_number="CAT-R")
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}/items/{item.id}",
            json={"catalog_number": "CAT-UPDATED"},
        )
        assert resp.status_code == 422

    def test_update_item_on_cancelled_order_rejected(self, orders_client, db_session):
        order = _seed_order(db_session, status="cancelled")
        item = _seed_order_item(db_session, order.id, catalog_number="CAT-C")
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}/items/{item.id}",
            json={"quantity": "5"},
        )
        assert resp.status_code == 422

    def test_update_item_on_deleted_order_rejected(self, orders_client, db_session):
        order = _seed_order(db_session, status="deleted")
        item = _seed_order_item(db_session, order.id, catalog_number="CAT-D")
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}/items/{item.id}",
            json={"quantity": "5"},
        )
        assert resp.status_code == 422

    def test_update_item_not_found(self, orders_client, db_session):
        order = _seed_order(db_session, status="pending")
        resp = orders_client.patch(
            f"/api/v1/orders/{order.id}/items/99999",
            json={"quantity": "1"},
        )
        assert resp.status_code == 404


# ---- Order Items: delete ----


class TestDeleteOrderItem:
    def test_delete_item(self, orders_client, db_session):
        order = _seed_order(db_session, status="pending")
        item = _seed_order_item(db_session, order.id, catalog_number="CAT-DEL")
        resp = orders_client.delete(f"/api/v1/orders/{order.id}/items/{item.id}")
        assert resp.status_code == 204

    def test_delete_item_on_received_order_rejected(self, orders_client, db_session):
        order = _seed_order(db_session, status="received")
        item = _seed_order_item(db_session, order.id, catalog_number="CAT-RD")
        resp = orders_client.delete(f"/api/v1/orders/{order.id}/items/{item.id}")
        assert resp.status_code == 422

    def test_delete_item_not_found(self, orders_client, db_session):
        order = _seed_order(db_session, status="pending")
        resp = orders_client.delete(f"/api/v1/orders/{order.id}/items/99999")
        assert resp.status_code == 404


# ---- receive_order endpoint ----


class TestReceiveOrder:
    def test_receive_order_not_found(self, orders_client):
        resp = orders_client.post(
            "/api/v1/orders/99999/receive",
            json={
                "items": [{"quantity": "1"}],
                "received_by": "TestUser",
            },
        )
        assert resp.status_code == 404

    def test_receive_order_success(self, orders_client, db_session):
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="RecvVendor")
        db_session.add(vendor)
        db_session.flush()
        product = Product(
            catalog_number="CAT-RECV", name="Recv Product", vendor_id=vendor.id
        )
        db_session.add(product)
        db_session.flush()

        order = _seed_order(db_session, status="shipped")
        item = _seed_order_item(
            db_session,
            order.id,
            catalog_number="CAT-RECV",
            quantity=Decimal("5"),
            product_id=product.id,
        )
        resp = orders_client.post(
            f"/api/v1/orders/{order.id}/receive",
            json={
                "items": [
                    {
                        "order_item_id": item.id,
                        "quantity": "5",
                        "lot_number": "LOT-RECV",
                    }
                ],
                "received_by": "Alice",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_receive_order_with_product_id(self, orders_client, db_session):
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="RecvVendor2")
        db_session.add(vendor)
        db_session.flush()
        product = Product(
            catalog_number="CAT-NOPROD", name="Recv Product 2", vendor_id=vendor.id
        )
        db_session.add(product)
        db_session.flush()

        order = _seed_order(db_session, status="shipped")
        resp = orders_client.post(
            f"/api/v1/orders/{order.id}/receive",
            json={
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": "2",
                        "lot_number": "LOT-NOPROD",
                        "unit": "EA",
                    }
                ],
                "received_by": "Bob",
            },
        )
        assert resp.status_code == 201

    def test_receive_order_already_received_rejected(self, db_session):
        """Cover receive_items guard for received status via direct call."""
        from lab_manager.services.inventory import receive_items

        order = Order(status=OrderStatus.received)
        db_session.add(order)
        db_session.flush()
        with pytest.raises(ValidationError, match="already"):
            receive_items(order.id, [], None, "TestUser", db_session)

    def test_receive_order_cancelled_rejected(self, db_session):
        """Cover receive_items guard for cancelled status via direct call."""
        from lab_manager.services.inventory import receive_items

        order = Order(status=OrderStatus.cancelled)
        db_session.add(order)
        db_session.flush()
        with pytest.raises(ValidationError, match="already"):
            receive_items(order.id, [], None, "TestUser", db_session)

    def test_receive_order_deleted_rejected(self, db_session):
        """Cover receive_items guard for deleted status via direct call."""
        from lab_manager.services.inventory import receive_items

        order = Order(status=OrderStatus.deleted)
        db_session.add(order)
        db_session.flush()
        with pytest.raises(ValidationError, match="already"):
            receive_items(order.id, [], None, "TestUser", db_session)

    def test_receive_order_with_location(self, orders_client, db_session):
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="RecvVendor3")
        db_session.add(vendor)
        db_session.flush()
        product = Product(
            catalog_number="CAT-LOC", name="Recv Product 3", vendor_id=vendor.id
        )
        db_session.add(product)
        db_session.flush()

        order = _seed_order(db_session, status="shipped")
        resp = orders_client.post(
            f"/api/v1/orders/{order.id}/receive",
            json={
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": "1",
                        "lot_number": "LOT-LOC",
                    }
                ],
                "location_id": None,
                "received_by": "Carol",
            },
        )
        assert resp.status_code == 201
