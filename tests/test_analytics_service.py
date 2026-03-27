"""Tests for analytics service — pure function tests with DB session fixture."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.location import StorageLocation
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services.analytics import (
    _money,
    dashboard_summary,
    spending_by_vendor,
    spending_by_month,
    inventory_value,
    top_products,
    order_history,
    staff_activity,
    vendor_summary,
    inventory_report,
    document_processing_stats,
)


class TestMoney:
    def test_none_to_zero(self):
        assert _money(None) == 0.0

    def test_integer(self):
        assert _money(100) == 100.0

    def test_float_rounded(self):
        assert _money(3.14159) == 3.14

    def test_decimal(self):
        assert _money(Decimal("99.999")) == 100.0

    def test_zero(self):
        assert _money(0) == 0.0

    def test_negative(self):
        # Python uses banker's rounding: round(-5.555, 2) -> -5.55
        assert _money(-5.555) == -5.55


def _create_vendor(db: Session, name: str = "TestVendor") -> Vendor:
    v = Vendor(name=name)
    db.add(v)
    db.flush()
    return v


def _create_product(
    db: Session,
    vendor_id: int,
    name: str = "TestProduct",
    catalog: str = "CAT001",
    min_stock=None,
) -> Product:
    p = Product(
        name=name,
        catalog_number=catalog,
        vendor_id=vendor_id,
        min_stock_level=min_stock,
    )
    db.add(p)
    db.flush()
    return p


def _create_order(
    db: Session,
    vendor_id: int,
    po: str = "PO-001",
    order_date=None,
    status="received",
    received_by=None,
) -> Order:
    o = Order(
        vendor_id=vendor_id,
        po_number=po,
        order_date=order_date,
        status=status,
        received_by=received_by,
    )
    db.add(o)
    db.flush()
    return o


def _create_order_item(
    db: Session,
    order_id: int,
    catalog_number="CAT001",
    description="Item",
    qty=1,
    price=10.0,
) -> OrderItem:
    oi = OrderItem(
        order_id=order_id,
        catalog_number=catalog_number,
        description=description,
        quantity=qty,
        unit_price=Decimal(str(price)),
    )
    db.add(oi)
    db.flush()
    return oi


def _create_inventory_item(
    db: Session,
    product_id: int,
    qty=10,
    status="available",
    expiry=None,
    order_item_id=None,
    location_id=None,
) -> InventoryItem:
    item = InventoryItem(
        product_id=product_id,
        quantity_on_hand=Decimal(str(qty)),
        status=status,
        expiry_date=expiry,
        order_item_id=order_item_id,
        location_id=location_id,
    )
    db.add(item)
    db.flush()
    return item


class TestDashboardSummaryEmpty:
    def test_empty_db(self, db_session):
        result = dashboard_summary(db_session)
        assert result["total_products"] == 0
        assert result["total_vendors"] == 0
        assert result["total_orders"] == 0
        assert result["total_inventory_items"] == 0
        assert result["total_documents"] == 0
        assert result["total_staff"] == 0
        assert result["documents_pending_review"] == 0
        assert result["documents_approved"] == 0
        assert result["recent_orders"] == []
        assert result["expiring_soon"] == []
        assert result["low_stock_count"] == 0
        assert isinstance(result["orders_by_status"], dict)
        assert isinstance(result["inventory_by_status"], dict)


class TestDashboardSummaryWithData:
    def test_with_records(self, db_session):
        v = _create_vendor(db_session, "Acme")
        p = _create_product(db_session, v.id, "Widget", "W-100")
        o = _create_order(db_session, v.id, "PO-100", date(2025, 1, 15))
        oi = _create_order_item(db_session, o.id, "W-100", "Widget", 2, 25.0)
        _create_inventory_item(db_session, p.id, qty=5, order_item_id=oi.id)
        db_session.commit()

        result = dashboard_summary(db_session)
        assert result["total_products"] == 1
        assert result["total_vendors"] == 1
        assert result["total_orders"] == 1
        assert result["total_inventory_items"] == 1
        assert len(result["recent_orders"]) == 1
        assert result["recent_orders"][0]["vendor_name"] == "Acme"

    def test_expiring_soon_items(self, db_session):
        v = _create_vendor(db_session, "BioCo")
        p = _create_product(db_session, v.id, "Reagent", "R-200")
        # Item expiring in 10 days (within 30-day cutoff)
        soon = date.today() + timedelta(days=10)
        _create_inventory_item(db_session, p.id, qty=3, status="available", expiry=soon)
        # Item expiring far in the future (not within cutoff)
        far = date.today() + timedelta(days=365)
        _create_inventory_item(db_session, p.id, qty=5, status="available", expiry=far)
        db_session.commit()

        result = dashboard_summary(db_session)
        assert len(result["expiring_soon"]) == 1
        assert result["expiring_soon"][0]["product_name"] == "Reagent"

    def test_low_stock_products(self, db_session):
        v = _create_vendor(db_session, "ChemCo")
        p = _create_product(db_session, v.id, "Solvent", "S-300", min_stock=20)
        # Only 5 on hand, below min_stock_level=20
        _create_inventory_item(db_session, p.id, qty=5, status="available")
        db_session.commit()

        result = dashboard_summary(db_session)
        assert result["low_stock_count"] == 1


class TestSpendingByVendor:
    def test_empty_db(self, db_session):
        result = spending_by_vendor(db_session)
        assert result == []

    def test_single_vendor_spending(self, db_session):
        v = _create_vendor(db_session, "Sigma")
        o = _create_order(db_session, v.id, "PO-1", date(2025, 3, 1))
        _create_order_item(db_session, o.id, "C-1", "Chemical A", 3, 50.0)
        db_session.commit()

        result = spending_by_vendor(db_session)
        assert len(result) == 1
        assert result[0]["vendor_name"] == "Sigma"
        assert result[0]["order_count"] == 1
        assert result[0]["item_count"] == 3
        assert result[0]["total_spend"] == 150.0

    def test_date_filter(self, db_session):
        v = _create_vendor(db_session, "Fisher")
        o1 = _create_order(db_session, v.id, "PO-1", date(2024, 6, 1))
        o2 = _create_order(db_session, v.id, "PO-2", date(2025, 3, 1))
        _create_order_item(db_session, o1.id, "C-1", "Item", 1, 100.0)
        _create_order_item(db_session, o2.id, "C-2", "Item", 1, 200.0)
        db_session.commit()

        # Only March 2025 order should be included
        result = spending_by_vendor(db_session, date_from=date(2025, 1, 1))
        assert len(result) == 1
        assert result[0]["total_spend"] == 200.0

    def test_date_to_filter(self, db_session):
        v = _create_vendor(db_session, "Thermo")
        o1 = _create_order(db_session, v.id, "PO-1", date(2024, 1, 1))
        o2 = _create_order(db_session, v.id, "PO-2", date(2025, 1, 1))
        _create_order_item(db_session, o1.id, "C-1", "Item", 1, 50.0)
        _create_order_item(db_session, o2.id, "C-2", "Item", 1, 75.0)
        db_session.commit()

        result = spending_by_vendor(db_session, date_to=date(2024, 12, 31))
        assert len(result) == 1
        assert result[0]["total_spend"] == 50.0


class TestSpendingByMonth:
    def test_empty_db(self, db_session):
        result = spending_by_month(db_session)
        assert result == []

    def test_monthly_aggregation(self, db_session):
        v = _create_vendor(db_session, "V")
        # Use dates within the last 12 months from today
        today = date.today()
        m1 = today.replace(day=1)
        m2 = (m1 - timedelta(days=35)).replace(day=10)
        o1 = _create_order(db_session, v.id, "PO-1", m1)
        o2 = _create_order(db_session, v.id, "PO-2", m1)
        o3 = _create_order(db_session, v.id, "PO-3", m2)
        _create_order_item(db_session, o1.id, "C-1", "Item", 1, 100.0)
        _create_order_item(db_session, o2.id, "C-2", "Item", 1, 50.0)
        _create_order_item(db_session, o3.id, "C-3", "Item", 1, 75.0)
        db_session.commit()

        result = spending_by_month(db_session, months=12)
        assert len(result) >= 2
        total_orders = sum(r["order_count"] for r in result)
        assert total_orders == 3
        total_spend = sum(r["total_spend"] for r in result)
        assert total_spend == 225.0


class TestInventoryValue:
    def test_empty_db(self, db_session):
        result = inventory_value(db_session)
        assert result["total_value"] == 0.0
        assert result["item_count"] == 0

    def test_with_items(self, db_session):
        v = _create_vendor(db_session, "V")
        p = _create_product(db_session, v.id, "P", "C-1")
        o = _create_order(db_session, v.id, "PO-1")
        oi = _create_order_item(db_session, o.id, "C-1", "P", 1, 10.0)
        _create_inventory_item(db_session, p.id, qty=5, order_item_id=oi.id)
        db_session.commit()

        result = inventory_value(db_session)
        assert result["item_count"] == 1
        assert result["total_value"] == 50.0


class TestTopProducts:
    def test_empty_db(self, db_session):
        result = top_products(db_session)
        assert result == []

    def test_top_products_ordered(self, db_session):
        v = _create_vendor(db_session, "V")
        o1 = _create_order(db_session, v.id, "PO-1")
        o2 = _create_order(db_session, v.id, "PO-2")
        _create_order_item(db_session, o1.id, "C-A", "Product A", 3, 10.0)
        _create_order_item(db_session, o1.id, "C-B", "Product B", 1, 10.0)
        _create_order_item(db_session, o2.id, "C-A", "Product A", 2, 10.0)
        db_session.commit()

        result = top_products(db_session, limit=10)
        assert len(result) >= 1
        # Product A should be first (ordered twice)
        first = result[0]
        assert first["catalog_number"] == "C-A"
        assert first["times_ordered"] == 2


class TestOrderHistory:
    def test_empty_db(self, db_session):
        result = order_history(db_session)
        assert result == []

    def test_order_history_with_vendor_filter(self, db_session):
        v1 = _create_vendor(db_session, "V1")
        v2 = _create_vendor(db_session, "V2")
        _create_order(db_session, v1.id, "PO-1", date(2025, 1, 1))
        _create_order(db_session, v2.id, "PO-2", date(2025, 2, 1))
        db_session.commit()

        result = order_history(db_session, vendor_id=v1.id)
        assert len(result) == 1
        assert result[0]["vendor_name"] == "V1"

    def test_order_history_limit(self, db_session):
        v = _create_vendor(db_session, "V")
        for i in range(5):
            _create_order(db_session, v.id, f"PO-{i}", date(2025, 1, 1))
        db_session.commit()

        result = order_history(db_session, limit=3)
        assert len(result) == 3

    def test_order_history_date_range(self, db_session):
        v = _create_vendor(db_session, "V")
        _create_order(db_session, v.id, "PO-1", date(2024, 6, 15))
        _create_order(db_session, v.id, "PO-2", date(2025, 3, 15))
        db_session.commit()

        result = order_history(
            db_session, date_from=date(2025, 1, 1), date_to=date(2025, 12, 31)
        )
        assert len(result) == 1


class TestStaffActivity:
    def test_empty_db(self, db_session):
        result = staff_activity(db_session)
        assert result == []

    def test_staff_with_orders(self, db_session):
        v = _create_vendor(db_session, "V")
        _create_order(db_session, v.id, "PO-1", date(2025, 1, 1), received_by="Alice")
        _create_order(db_session, v.id, "PO-2", date(2025, 2, 1), received_by="Alice")
        _create_order(db_session, v.id, "PO-3", date(2025, 3, 1), received_by="Bob")
        db_session.commit()

        result = staff_activity(db_session)
        assert len(result) == 2
        alice = next(r for r in result if r["name"] == "Alice")
        assert alice["orders_received"] == 2
        bob = next(r for r in result if r["name"] == "Bob")
        assert bob["orders_received"] == 1


class TestVendorSummary:
    def test_nonexistent_vendor(self, db_session):
        result = vendor_summary(db_session, vendor_id=9999)
        assert result is None

    def test_vendor_summary_with_data(self, db_session):
        v = _create_vendor(db_session, "Sigma")
        _create_product(db_session, v.id, "P1", "C-1")
        o = _create_order(db_session, v.id, "PO-1", date(2025, 3, 1))
        _create_order_item(db_session, o.id, "C-1", "P1", 2, 50.0)
        db_session.commit()

        result = vendor_summary(db_session, vendor_id=v.id)
        assert result is not None
        assert result["name"] == "Sigma"
        assert result["products_supplied"] == 1
        assert result["order_count"] == 1
        assert result["total_spend"] == 100.0
        assert result["last_order_date"] is not None


class TestInventoryReport:
    def test_empty_db(self, db_session):
        result = inventory_report(db_session)
        assert result == []

    def test_inventory_report_basic(self, db_session):
        v = _create_vendor(db_session, "V")
        p = _create_product(db_session, v.id, "Reagent", "R-1")
        loc = StorageLocation(name="Fridge A")
        db_session.add(loc)
        db_session.flush()
        _create_inventory_item(
            db_session, p.id, qty=10, status="available", location_id=loc.id
        )
        db_session.commit()

        result = inventory_report(db_session)
        assert len(result) == 1
        assert result[0]["product_name"] == "Reagent"
        assert result[0]["location_name"] == "Fridge A"

    def test_inventory_report_filtered_by_location(self, db_session):
        v = _create_vendor(db_session, "V")
        p = _create_product(db_session, v.id, "P", "C-1")
        loc1 = StorageLocation(name="Fridge A")
        loc2 = StorageLocation(name="Freezer B")
        db_session.add_all([loc1, loc2])
        db_session.flush()
        _create_inventory_item(db_session, p.id, qty=5, location_id=loc1.id)
        _create_inventory_item(db_session, p.id, qty=3, location_id=loc2.id)
        db_session.commit()

        result = inventory_report(db_session, location_id=loc1.id)
        assert len(result) == 1
        assert result[0]["location_name"] == "Fridge A"


class TestDocumentProcessingStats:
    def test_empty_db(self, db_session):
        result = document_processing_stats(db_session)
        assert result["total_documents"] == 0
        assert result["rejected_count"] == 0
        assert result["rejection_rate"] == 0.0
        assert result["average_confidence"] is None

    def test_with_documents(self, db_session):
        doc1 = Document(
            file_path="/uploads/test1.pdf",
            file_name="test1.pdf",
            status=DocumentStatus.approved,
            document_type="invoice",
            extraction_confidence=0.95,
        )
        doc2 = Document(
            file_path="/uploads/test2.pdf",
            file_name="test2.pdf",
            status=DocumentStatus.rejected,
            document_type="packing_list",
            extraction_confidence=0.3,
        )
        db_session.add_all([doc1, doc2])
        db_session.commit()

        result = document_processing_stats(db_session)
        assert result["total_documents"] == 2
        assert result["rejected_count"] == 1
        assert result["rejection_rate"] == 50.0
        assert result["average_confidence"] is not None
