"""Test database models."""

from datetime import date

from lab_manager.models.audit import AuditLog
from lab_manager.models.base import AuditMixin
from lab_manager.models.document import Document
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.location import StorageLocation
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.vendor import Vendor


def test_audit_mixin_has_timestamps():
    """AuditMixin should define created_at, updated_at, created_by."""
    fields = {f for f in AuditMixin.model_fields}
    assert "created_at" in fields
    assert "updated_at" in fields
    assert "created_by" in fields


def test_vendor_model():
    v = Vendor(name="Sigma-Aldrich", aliases=["MilliporeSigma", "Merck"])
    assert v.name == "Sigma-Aldrich"
    assert "MilliporeSigma" in v.aliases


def test_product_model():
    p = Product(
        catalog_number="AB1031",
        name="AGGRECAN, RBX MS-50UG",
        vendor_id=1,
    )
    assert p.catalog_number == "AB1031"


def test_staff_model():
    s = Staff(name="Shiqian Shen", email="sshen@mgh.harvard.edu", role="PI")
    assert s.role == "PI"


def test_location_model():
    loc = StorageLocation(name="Freezer -80C #1", temperature=-80, room="CNY 149")
    assert loc.temperature == -80


def test_order_model():
    o = Order(
        po_number="PO-10997931",
        vendor_id=1,
        order_date=date(2026, 3, 4),
        status="received",
    )
    assert o.po_number == "PO-10997931"


def test_order_item_model():
    item = OrderItem(
        order_id=1,
        catalog_number="AB1031",
        description="AGGRECAN, RBX MS-50UG",
        quantity=1,
        lot_number="4361991",
    )
    assert item.lot_number == "4361991"


def test_inventory_item_model():
    inv = InventoryItem(
        product_id=1,
        location_id=1,
        quantity_on_hand=5,
        lot_number="4361991",
    )
    assert inv.quantity_on_hand == 5


def test_document_model():
    doc = Document(
        file_path="uploads/scan001.jpg",
        file_name="scan001.jpg",
        document_type="packing_list",
        status="pending",
    )
    assert doc.status == "pending"


def test_audit_log_model():
    log = AuditLog(
        table_name="orders",
        record_id=1,
        action="create",
        changed_by="sshen",
        changes={"po_number": {"old": None, "new": "PO-123"}},
    )
    assert log.action == "create"
