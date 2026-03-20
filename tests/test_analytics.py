"""Test analytics and export API endpoints."""

from datetime import date


def _seed_data(db):
    """Insert minimal data to exercise analytics queries."""
    from lab_manager.models.vendor import Vendor
    from lab_manager.models.product import Product
    from lab_manager.models.order import Order, OrderItem
    from lab_manager.models.inventory import InventoryItem
    from lab_manager.models.document import Document
    from lab_manager.models.staff import Staff
    from lab_manager.models.location import StorageLocation

    vendor = Vendor(name="Thermo Fisher")
    db.add(vendor)
    db.flush()

    product = Product(catalog_number="A12345", name="Antibody X", vendor_id=vendor.id)
    db.add(product)
    db.flush()

    loc = StorageLocation(name="Freezer -20", room="149")
    db.add(loc)
    db.flush()

    staff = Staff(name="Alice", email="alice@example.com", role="member")
    db.add(staff)
    db.flush()

    order = Order(
        po_number="PO-001",
        vendor_id=vendor.id,
        order_date=date(2026, 3, 1),
        status="received",
        received_by="Alice",
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        catalog_number="A12345",
        description="Antibody X",
        quantity=2,
        unit_price=50.0,
    )
    db.add(item)
    db.flush()

    inv = InventoryItem(
        product_id=product.id,
        location_id=loc.id,
        lot_number="LOT1",
        quantity_on_hand=5,
        expiry_date=date(2026, 3, 20),
        status="available",
        order_item_id=item.id,
    )
    db.add(inv)

    doc = Document(
        file_path="uploads/scan1.jpg",
        file_name="scan1.jpg",
        document_type="packing_list",
        status="approved",
        extraction_confidence=0.95,
    )
    db.add(doc)
    doc2 = Document(
        file_path="uploads/scan2.jpg",
        file_name="scan2.jpg",
        document_type="invoice",
        status="pending",
        extraction_confidence=0.80,
    )
    db.add(doc2)
    db.commit()


# ---- Analytics endpoints ----


def test_dashboard(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_vendors"] == 1
    assert data["total_orders"] == 1
    assert data["total_products"] == 1
    assert data["total_documents"] == 2
    assert data["total_staff"] == 1
    assert data["documents_pending_review"] == 1
    assert data["documents_approved"] == 1
    assert data["orders_by_status"]["received"] == 1
    assert len(data["recent_orders"]) == 1
    assert data["recent_orders"][0]["vendor_name"] == "Thermo Fisher"


def test_spending_by_vendor(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/spending/by-vendor")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["vendor_name"] == "Thermo Fisher"
    assert data[0]["total_spend"] == 100.0


def test_spending_by_vendor_date_filter(client, db_session):
    _seed_data(db_session)
    resp = client.get(
        "/api/v1/analytics/spending/by-vendor?date_from=2026-04-01&date_to=2026-05-01"
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_spending_by_month(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/spending/by-month?months=12")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["month"] == "2026-03"
    assert data[0]["total_spend"] == 100.0


def test_inventory_value(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/inventory/value")
    assert resp.status_code == 200
    data = resp.json()
    # 5 on hand * $50 unit_price = $250
    assert data["total_value"] == 250.0


def test_inventory_report(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/inventory/report")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["product_name"] == "Antibody X"
    assert data[0]["vendor_name"] == "Thermo Fisher"
    assert data[0]["location_name"] == "Freezer -20"


def test_top_products(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/products/top?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["catalog_number"] == "A12345"
    assert data[0]["total_quantity"] == 2


def test_order_history(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/orders/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["vendor_name"] == "Thermo Fisher"
    assert data[0]["total_value"] == 100.0


def test_staff_activity(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/staff/activity")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Alice"
    assert data[0]["orders_received"] == 1


def test_vendor_summary(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/vendors/1/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Thermo Fisher"
    assert data["products_supplied"] == 1
    assert data["order_count"] == 1
    assert data["total_spend"] == 100.0


def test_vendor_summary_not_found(client, db_session):
    resp = client.get("/api/v1/analytics/vendors/999/summary")
    assert resp.status_code == 404


def test_document_stats(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/analytics/documents/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_documents"] == 2
    assert data["by_status"]["approved"] == 1
    assert data["by_status"]["pending"] == 1
    assert data["average_confidence"] is not None


# ---- Export endpoints ----


def test_export_inventory_csv(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/export/inventory")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    lines = resp.text.strip().split("\n")
    assert len(lines) == 2  # header + 1 row
    assert "Antibody X" in lines[1]


def test_export_orders_csv(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/export/orders")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert len(lines) == 2


def test_export_products_csv(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/export/products")
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) == 2
    assert "A12345" in lines[1]


def test_export_vendors_csv(client, db_session):
    _seed_data(db_session)
    resp = client.get("/api/v1/export/vendors")
    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) == 2
    assert "Thermo Fisher" in lines[1]


def test_export_empty_table(client, db_session):
    """CSV export with empty tables should return 200 with empty body."""
    resp = client.get("/api/v1/export/vendors")
    assert resp.status_code == 200


def test_dashboard_empty(client, db_session):
    """Dashboard with no data should return zeros, not errors."""
    resp = client.get("/api/v1/analytics/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_products"] == 0
    assert data["total_orders"] == 0
    assert data["recent_orders"] == []
    assert data["expiring_soon"] == []
