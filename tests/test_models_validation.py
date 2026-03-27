"""Comprehensive validation tests for all SQLModel data models.

Covers: instantiation with valid data, default values, field constraints,
required vs optional fields, relationship definitions, status enums, and edge cases.
"""

from datetime import date, datetime, timezone
from decimal import Decimal


from lab_manager.models.alert import Alert, AlertSeverity, AlertType
from lab_manager.models.audit import VALID_AUDIT_ACTIONS, AuditLog
from lab_manager.models.base import AuditMixin, utcnow
from lab_manager.models.consumption import ConsumptionAction, ConsumptionLog
from lab_manager.models.document import Document, DocumentStatus
from lab_manager.models.equipment import (
    VALID_EQUIPMENT_STATUSES,
    Equipment,
    EquipmentStatus,
)
from lab_manager.models.import_job import (
    ImportErrorRecord,
    ImportJob,
    ImportStatus,
    ImportType,
)
from lab_manager.models.inventory import ACTIVE_STATUSES, InventoryItem, InventoryStatus
from lab_manager.models.invitation import Invitation
from lab_manager.models.location import StorageLocation
from lab_manager.models.notification import Notification, NotificationPreference
from lab_manager.models.order import Order, OrderItem, OrderStatus
from lab_manager.models.order_request import OrderRequest, RequestStatus, RequestUrgency
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.usage_event import UsageEvent
from lab_manager.models.vendor import Vendor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fields(cls) -> set[str]:
    """Return the set of field names defined on a SQLModel class."""
    return set(cls.model_fields)


def _is_optional(cls, field_name: str) -> bool:
    """Check whether a field annotation is Optional (allows None)."""
    import typing

    annotation = cls.model_fields[field_name].annotation
    origin = getattr(annotation, "__origin__", None)
    if origin is typing.Union:
        return type(None) in annotation.__args__
    return False


# ===========================================================================
# 1. AuditMixin
# ===========================================================================


class TestAuditMixin:
    def test_has_required_fields(self):
        fields = _fields(AuditMixin)
        assert "created_at" in fields
        assert "updated_at" in fields
        assert "created_by" in fields

    def test_created_at_auto_set(self):
        m = AuditMixin()
        assert m.created_at is not None
        assert m.updated_at is not None
        assert m.created_at.tzinfo == timezone.utc

    def test_created_by_default_none(self):
        m = AuditMixin()
        assert m.created_by is None

    def test_utcnow_returns_utc(self):
        now = utcnow()
        assert now.tzinfo == timezone.utc


# ===========================================================================
# 2. Vendor
# ===========================================================================


class TestVendor:
    def test_valid_minimal(self):
        v = Vendor(name="Sigma-Aldrich")
        assert v.name == "Sigma-Aldrich"
        assert v.aliases == []
        assert v.website is None
        assert v.phone is None
        assert v.email is None
        assert v.notes is None
        assert v.id is None

    def test_all_fields(self):
        v = Vendor(
            name="Thermo Fisher",
            aliases=["Thermo", "Fisher Scientific"],
            website="https://thermofisher.com",
            phone="+1-800-555-0199",
            email="support@thermofisher.com",
            notes="Primary supplier",
        )
        assert v.name == "Thermo Fisher"
        assert len(v.aliases) == 2
        assert v.website == "https://thermofisher.com"

    def test_optional_fields_accept_none(self):
        v = Vendor(
            name="Bio-Rad",
            aliases=None,
            website=None,
            phone=None,
            email=None,
            notes=None,
        )
        assert v.name == "Bio-Rad"

    def test_aliases_default_factory(self):
        """Two instances should get independent alias lists."""
        v1 = Vendor(name="A")
        v2 = Vendor(name="B")
        v1.aliases.append("x")
        assert v2.aliases == []

    def test_relationships_defined(self):
        rels = set(Vendor.__sqlmodel_relationships__.keys())
        assert "products" in rels
        assert "orders" in rels

    def test_tablename(self):
        assert Vendor.__tablename__ == "vendors"

    def test_inherits_audit_mixin(self):
        assert issubclass(Vendor, AuditMixin)

    def test_id_default_none(self):
        v = Vendor(name="X")
        assert v.id is None


# ===========================================================================
# 3. Product
# ===========================================================================


class TestProduct:
    def test_valid_minimal(self):
        p = Product(catalog_number="AB1031", name="AGGRECAN RBX MS-50UG")
        assert p.catalog_number == "AB1031"
        assert p.name == "AGGRECAN RBX MS-50UG"
        assert p.vendor_id is None
        assert p.extra == {}

    def test_all_optional_fields_none(self):
        p = Product(
            catalog_number="X",
            name="Y",
            vendor_id=None,
            category=None,
            cas_number=None,
            molecular_weight=None,
            molecular_formula=None,
            smiles=None,
            pubchem_cid=None,
            storage_temp=None,
            unit=None,
            hazard_info=None,
            min_stock_level=None,
            max_stock_level=None,
            reorder_quantity=None,
            shelf_life_days=None,
            storage_requirements=None,
        )
        assert p.category is None
        assert p.molecular_weight is None

    def test_boolean_defaults(self):
        p = Product(catalog_number="X", name="Y")
        assert p.is_hazardous is False
        assert p.is_controlled is False
        assert p.is_active is True

    def test_decimal_stock_fields(self):
        p = Product(
            catalog_number="X",
            name="Y",
            min_stock_level=Decimal("10.5"),
            max_stock_level=Decimal("100.0"),
            reorder_quantity=Decimal("25.0"),
        )
        assert p.min_stock_level == Decimal("10.5")

    def test_extra_default_factory(self):
        p1 = Product(catalog_number="A", name="A")
        p2 = Product(catalog_number="B", name="B")
        p1.extra["key"] = "val"
        assert p2.extra == {}

    def test_relationships(self):
        rels = set(Product.__sqlmodel_relationships__.keys())
        assert "vendor" in rels
        assert "order_items" in rels
        assert "inventory_items" in rels
        assert "consumption_logs" in rels

    def test_tablename(self):
        assert Product.__tablename__ == "products"


# ===========================================================================
# 4. Staff
# ===========================================================================


class TestStaff:
    def test_valid_minimal(self):
        s = Staff(name="Jane Smith")
        assert s.name == "Jane Smith"
        assert s.role == "grad_student"
        assert s.role_level == 3
        assert s.is_active is True
        assert s.email is None
        assert s.failed_login_count == 0
        assert s.id is None

    def test_with_email(self):
        s = Staff(name="Bob", email="bob@example.com")
        assert s.email == "bob@example.com"

    def test_custom_role(self):
        s = Staff(name="Alice", role="PI", role_level=1)
        assert s.role == "PI"
        assert s.role_level == 1

    def test_inactive(self):
        s = Staff(name="Eve", is_active=False)
        assert s.is_active is False

    def test_optional_datetime_fields(self):
        s = Staff(
            name="X",
            last_login_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            access_expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
            locked_until=None,
        )
        assert s.last_login_at is not None
        assert s.locked_until is None

    def test_invited_by_self_referential_fk(self):
        s = Staff(name="X", invited_by=1)
        assert s.invited_by == 1

    def test_inherits_audit_mixin(self):
        assert issubclass(Staff, AuditMixin)


# ===========================================================================
# 5. StorageLocation
# ===========================================================================


class TestStorageLocation:
    def test_valid_minimal(self):
        loc = StorageLocation(name="Freezer -80C #1")
        assert loc.name == "Freezer -80C #1"
        assert loc.room is None
        assert loc.building is None
        assert loc.temperature is None
        assert loc.description is None

    def test_all_fields(self):
        loc = StorageLocation(
            name="Cold Room",
            room="CNY 149",
            building="Simches",
            temperature=-20,
            description="Shared cold room",
        )
        assert loc.temperature == -20
        assert loc.building == "Simches"

    def test_temperature_can_be_positive(self):
        loc = StorageLocation(name="Bench", temperature=22)
        assert loc.temperature == 22

    def test_relationships(self):
        rels = set(StorageLocation.__sqlmodel_relationships__.keys())
        assert "inventory_items" in rels
        assert "equipment" in rels


# ===========================================================================
# 6. Order + OrderItem + OrderStatus
# ===========================================================================


class TestOrderStatus:
    def test_enum_values(self):
        assert set(OrderStatus) == {
            OrderStatus.pending,
            OrderStatus.shipped,
            OrderStatus.received,
            OrderStatus.cancelled,
            OrderStatus.deleted,
        }

    def test_string_values(self):
        assert OrderStatus.pending.value == "pending"
        assert OrderStatus.received.value == "received"

    def test_is_str_enum(self):
        assert isinstance(OrderStatus.pending, str)


class TestOrder:
    def test_valid_minimal(self):
        o = Order()
        assert o.status == "pending"
        assert o.po_number is None
        assert o.vendor_id is None
        assert o.order_date is None
        assert o.extra == {}

    def test_all_fields(self):
        o = Order(
            po_number="PO-10997931",
            vendor_id=1,
            order_date=date(2026, 3, 4),
            ship_date=date(2026, 3, 5),
            received_date=date(2026, 3, 7),
            received_by="Jane",
            status="received",
            delivery_number="DN-123",
            invoice_number="INV-456",
        )
        assert o.po_number == "PO-10997931"
        assert o.status == "received"
        assert o.order_date == date(2026, 3, 4)

    def test_status_default(self):
        o = Order()
        assert o.status == "pending"

    def test_relationships(self):
        rels = set(Order.__sqlmodel_relationships__.keys())
        assert "vendor" in rels
        assert "items" in rels
        assert "document" in rels

    def test_inherits_audit_mixin(self):
        assert issubclass(Order, AuditMixin)


class TestOrderItem:
    def test_valid_minimal(self):
        item = OrderItem(order_id=1)
        assert item.order_id == 1
        assert item.quantity == Decimal("1")
        assert item.catalog_number is None
        assert item.extra == {}

    def test_all_optional_fields(self):
        item = OrderItem(
            order_id=5,
            catalog_number="AB1031",
            description="AGGRECAN RBX MS-50UG",
            quantity=Decimal("3.5"),
            unit="mg",
            lot_number="4361991",
            batch_number="B100",
            unit_price=Decimal("49.99"),
            product_id=10,
        )
        assert item.lot_number == "4361991"
        assert item.unit_price == Decimal("49.99")
        assert item.quantity == Decimal("3.5")

    def test_quantity_default(self):
        item = OrderItem(order_id=1)
        assert item.quantity == Decimal("1")

    def test_relationships(self):
        rels = set(OrderItem.__sqlmodel_relationships__.keys())
        assert "order" in rels
        assert "product" in rels
        assert "inventory_items" in rels


# ===========================================================================
# 7. InventoryItem + InventoryStatus
# ===========================================================================


class TestInventoryStatus:
    def test_enum_values(self):
        assert set(InventoryStatus) == {
            InventoryStatus.available,
            InventoryStatus.opened,
            InventoryStatus.depleted,
            InventoryStatus.disposed,
            InventoryStatus.expired,
            InventoryStatus.deleted,
        }

    def test_active_statuses(self):
        assert InventoryStatus.available in ACTIVE_STATUSES
        assert InventoryStatus.opened in ACTIVE_STATUSES
        assert InventoryStatus.depleted not in ACTIVE_STATUSES

    def test_is_str_enum(self):
        assert isinstance(InventoryStatus.available, str)


class TestInventoryItem:
    def test_valid_minimal(self):
        inv = InventoryItem(product_id=1)
        assert inv.product_id == 1
        assert inv.quantity_on_hand == Decimal("0")
        assert inv.status == "available"
        assert inv.location_id is None
        assert inv.lot_number is None

    def test_all_fields(self):
        inv = InventoryItem(
            product_id=2,
            location_id=3,
            quantity_on_hand=Decimal("10.5"),
            lot_number="LOT-999",
            unit="mL",
            expiry_date=date(2027, 1, 1),
            opened_date=date(2026, 3, 15),
            status="opened",
            notes="In use",
            received_by="Jane",
            order_item_id=10,
        )
        assert inv.quantity_on_hand == Decimal("10.5")
        assert inv.status == "opened"

    def test_defaults(self):
        inv = InventoryItem(product_id=1)
        assert inv.status == "available"
        assert inv.quantity_on_hand == Decimal("0")

    def test_relationships(self):
        rels = set(InventoryItem.__sqlmodel_relationships__.keys())
        assert "product" in rels
        assert "location" in rels
        assert "order_item" in rels
        assert "consumption_logs" in rels


# ===========================================================================
# 8. Document + DocumentStatus
# ===========================================================================


class TestDocumentStatus:
    def test_enum_values(self):
        assert set(DocumentStatus) == {
            DocumentStatus.pending,
            DocumentStatus.processing,
            DocumentStatus.extracted,
            DocumentStatus.needs_review,
            DocumentStatus.approved,
            DocumentStatus.rejected,
            DocumentStatus.ocr_failed,
            DocumentStatus.deleted,
        }

    def test_is_str_enum(self):
        assert isinstance(DocumentStatus.pending, str)


class TestDocument:
    def test_valid_minimal(self):
        doc = Document(
            file_path="uploads/scan.jpg",
            file_name="scan.jpg",
        )
        assert doc.file_path == "uploads/scan.jpg"
        assert doc.file_name == "scan.jpg"
        assert doc.status == "pending"
        assert doc.document_type is None
        assert doc.ocr_text is None
        assert doc.extracted_data is None

    def test_all_fields(self):
        doc = Document(
            file_path="uploads/coa.pdf",
            file_name="coa.pdf",
            document_type="certificate_of_analysis",
            vendor_name="Sigma-Aldrich",
            ocr_text="Extracted text here",
            extracted_data={"items": [1, 2]},
            extraction_model="gemini-3-pro-preview",
            extraction_confidence=0.95,
            status="approved",
            review_notes="Looks good",
            reviewed_by="admin",
        )
        assert doc.vendor_name == "Sigma-Aldrich"
        assert doc.extraction_confidence == 0.95
        assert doc.status == "approved"

    def test_status_default(self):
        doc = Document(file_path="x", file_name="y")
        assert doc.status == "pending"

    def test_relationships(self):
        rels = set(Document.__sqlmodel_relationships__.keys())
        assert "orders" in rels


# ===========================================================================
# 9. AuditLog
# ===========================================================================


class TestAuditLog:
    def test_valid_minimal(self):
        log = AuditLog(table_name="orders", record_id=1, action="create")
        assert log.table_name == "orders"
        assert log.record_id == 1
        assert log.action == "create"
        assert log.changes == {}
        assert log.changed_by is None

    def test_all_fields(self):
        log = AuditLog(
            table_name="products",
            record_id=42,
            action="update",
            changed_by="admin",
            changes={"name": {"old": "A", "new": "B"}},
        )
        assert log.changed_by == "admin"
        assert "name" in log.changes

    def test_valid_audit_actions(self):
        assert VALID_AUDIT_ACTIONS == ("create", "update", "delete")

    def test_timestamp_auto_set(self):
        log = AuditLog(table_name="t", record_id=1, action="create")
        assert log.timestamp is not None
        assert log.timestamp.tzinfo == timezone.utc

    def test_not_inheriting_audit_mixin(self):
        """AuditLog is its own standalone model, not inheriting AuditMixin."""
        assert not issubclass(AuditLog, AuditMixin)


# ===========================================================================
# 10. ConsumptionLog + ConsumptionAction
# ===========================================================================


class TestConsumptionAction:
    def test_enum_values(self):
        assert set(ConsumptionAction) == {
            ConsumptionAction.receive,
            ConsumptionAction.consume,
            ConsumptionAction.transfer,
            ConsumptionAction.adjust,
            ConsumptionAction.dispose,
            ConsumptionAction.open,
        }

    def test_is_str_enum(self):
        assert isinstance(ConsumptionAction.receive, str)


class TestConsumptionLog:
    def test_valid(self):
        log = ConsumptionLog(
            inventory_id=1,
            quantity_used=Decimal("2.5"),
            quantity_remaining=Decimal("7.5"),
            consumed_by="Jane",
            action="consume",
        )
        assert log.inventory_id == 1
        assert log.quantity_used == Decimal("2.5")
        assert log.action == "consume"

    def test_optional_fields(self):
        log = ConsumptionLog(
            inventory_id=1,
            quantity_used=Decimal("1"),
            quantity_remaining=Decimal("0"),
            consumed_by="X",
            action="dispose",
            product_id=None,
            purpose=None,
        )
        assert log.product_id is None
        assert log.purpose is None

    def test_relationships(self):
        rels = set(ConsumptionLog.__sqlmodel_relationships__.keys())
        assert "inventory_item" in rels
        assert "product" in rels


# ===========================================================================
# 11. Alert + AlertType + AlertSeverity
# ===========================================================================


class TestAlertType:
    def test_enum_values(self):
        assert set(AlertType) == {
            AlertType.expired,
            AlertType.expiring_soon,
            AlertType.out_of_stock,
            AlertType.low_stock,
            AlertType.pending_review,
            AlertType.stale_orders,
        }


class TestAlertSeverity:
    def test_enum_values(self):
        assert set(AlertSeverity) == {
            AlertSeverity.critical,
            AlertSeverity.warning,
            AlertSeverity.info,
        }


class TestAlert:
    def test_valid(self):
        a = Alert(
            alert_type="expired",
            severity="critical",
            message="Item X has expired",
            entity_type="inventory",
            entity_id=5,
        )
        assert a.alert_type == "expired"
        assert a.severity == "critical"
        assert a.is_acknowledged is False
        assert a.is_resolved is False
        assert a.acknowledged_by is None

    def test_defaults(self):
        a = Alert(
            alert_type="low_stock",
            severity="warning",
            message="Low",
            entity_type="product",
            entity_id=1,
        )
        assert a.is_acknowledged is False
        assert a.is_resolved is False

    def test_acknowledge(self):
        a = Alert(
            alert_type="expired",
            severity="critical",
            message="Expired",
            entity_type="inventory",
            entity_id=1,
            is_acknowledged=True,
            acknowledged_by="admin",
            acknowledged_at=datetime(2026, 3, 27, tzinfo=timezone.utc),
        )
        assert a.is_acknowledged is True
        assert a.acknowledged_by == "admin"

    def test_inherits_audit_mixin(self):
        assert issubclass(Alert, AuditMixin)


# ===========================================================================
# 12. Equipment + EquipmentStatus
# ===========================================================================


class TestEquipmentStatus:
    def test_class_attributes(self):
        assert EquipmentStatus.active == "active"
        assert EquipmentStatus.maintenance == "maintenance"
        assert EquipmentStatus.broken == "broken"
        assert EquipmentStatus.retired == "retired"
        assert EquipmentStatus.decommissioned == "decommissioned"
        assert EquipmentStatus.deleted == "deleted"

    def test_valid_statuses_tuple(self):
        assert VALID_EQUIPMENT_STATUSES == (
            "active",
            "maintenance",
            "broken",
            "retired",
            "decommissioned",
            "deleted",
        )


class TestEquipment:
    def test_valid_minimal(self):
        eq = Equipment(name="Centrifuge A")
        assert eq.name == "Centrifuge A"
        assert eq.status == "active"
        assert eq.is_api_controllable is False
        assert eq.estimated_value is None
        assert eq.photos == []
        assert eq.extra == {}

    def test_all_fields(self):
        eq = Equipment(
            name="NMR Spectrometer",
            manufacturer="Bruker",
            model="Avance III",
            serial_number="SN-12345",
            system_id="EQ-001",
            category="analytical",
            description="400 MHz NMR",
            location_id=1,
            room="Lab 201",
            estimated_value=Decimal("500000.00"),
            status="active",
            is_api_controllable=True,
            api_interface="tcp",
            notes="Calibrated",
            photos=["img1.jpg", "img2.jpg"],
            extracted_data={"key": "val"},
            extra={"color": "blue"},
        )
        assert eq.manufacturer == "Bruker"
        assert eq.estimated_value == Decimal("500000.00")
        assert eq.is_api_controllable is True

    def test_defaults(self):
        eq = Equipment(name="X")
        assert eq.status == "active"
        assert eq.is_api_controllable is False
        assert eq.photos == []
        assert eq.extra == {}

    def test_relationships(self):
        rels = set(Equipment.__sqlmodel_relationships__.keys())
        assert "location" in rels

    def test_inherits_audit_mixin(self):
        assert issubclass(Equipment, AuditMixin)


# ===========================================================================
# 13. OrderRequest + RequestStatus + RequestUrgency
# ===========================================================================


class TestRequestStatus:
    def test_enum_values(self):
        assert set(RequestStatus) == {
            RequestStatus.pending,
            RequestStatus.approved,
            RequestStatus.rejected,
            RequestStatus.cancelled,
        }


class TestRequestUrgency:
    def test_enum_values(self):
        assert set(RequestUrgency) == {
            RequestUrgency.normal,
            RequestUrgency.urgent,
        }


class TestOrderRequest:
    def test_valid_minimal(self):
        r = OrderRequest(requested_by=1)
        assert r.requested_by == 1
        assert r.status == "pending"
        assert r.urgency == "normal"
        assert r.quantity == Decimal("1")

    def test_all_optional_fields(self):
        r = OrderRequest(
            requested_by=2,
            product_id=10,
            vendor_id=5,
            catalog_number="AB100",
            description="Reagent X",
            quantity=Decimal("3"),
            unit="mL",
            estimated_price=Decimal("99.99"),
            justification="Running low",
            urgency="urgent",
            status="approved",
            reviewed_by=1,
            review_note="Approved",
            order_id=20,
            reviewed_at=datetime(2026, 3, 27, tzinfo=timezone.utc),
        )
        assert r.urgency == "urgent"
        assert r.status == "approved"
        assert r.reviewed_by == 1

    def test_defaults(self):
        r = OrderRequest(requested_by=1)
        assert r.status == "pending"
        assert r.urgency == "normal"
        assert r.quantity == Decimal("1")
        assert r.product_id is None
        assert r.vendor_id is None

    def test_relationships(self):
        rels = set(OrderRequest.__sqlmodel_relationships__.keys())
        assert "requester" in rels
        assert "reviewer" in rels
        assert "product" in rels
        assert "vendor" in rels
        assert "order" in rels


# ===========================================================================
# 14. Notification + NotificationPreference
# ===========================================================================


class TestNotification:
    def test_valid(self):
        n = Notification(
            staff_id=1,
            type="order_request",
            title="New request",
            message="You have a new order request",
        )
        assert n.staff_id == 1
        assert n.type == "order_request"
        assert n.is_read is False
        assert n.read_at is None
        assert n.link is None

    def test_read_notification(self):
        n = Notification(
            staff_id=1,
            type="info",
            title="T",
            message="M",
            is_read=True,
            read_at=datetime(2026, 3, 27, tzinfo=timezone.utc),
            link="/orders/1",
        )
        assert n.is_read is True
        assert n.link == "/orders/1"

    def test_defaults(self):
        n = Notification(staff_id=1, type="t", title="t", message="m")
        assert n.is_read is False


class TestNotificationPreference:
    def test_valid(self):
        np = NotificationPreference(staff_id=1)
        assert np.staff_id == 1
        assert np.in_app is True
        assert np.email_weekly is False
        assert np.order_requests is True
        assert np.document_reviews is True
        assert np.inventory_alerts is True
        assert np.team_changes is True

    def test_custom_preferences(self):
        np = NotificationPreference(
            staff_id=1,
            in_app=False,
            email_weekly=True,
            order_requests=False,
        )
        assert np.in_app is False
        assert np.email_weekly is True
        assert np.order_requests is False


# ===========================================================================
# 15. UsageEvent
# ===========================================================================


class TestUsageEvent:
    def test_valid(self):
        ue = UsageEvent(user_email="jane@example.com", event_type="page_view")
        assert ue.user_email == "jane@example.com"
        assert ue.event_type == "page_view"
        assert ue.page is None
        assert ue.metadata_ is None

    def test_all_fields(self):
        ue = UsageEvent(
            user_email="a@b.com",
            event_type="click",
            page="/inventory",
            metadata_={"button": "export"},
        )
        assert ue.page == "/inventory"
        assert ue.metadata_ == {"button": "export"}


# ===========================================================================
# 16. ImportJob + ImportErrorRecord + ImportType + ImportStatus
# ===========================================================================


class TestImportType:
    def test_enum_values(self):
        assert set(ImportType) == {
            ImportType.products,
            ImportType.vendors,
            ImportType.inventory,
        }


class TestImportStatus:
    def test_enum_values(self):
        assert set(ImportStatus) == {
            ImportStatus.uploading,
            ImportStatus.validating,
            ImportStatus.preview,
            ImportStatus.importing,
            ImportStatus.completed,
            ImportStatus.failed,
            ImportStatus.cancelled,
        }


class TestImportJob:
    def test_valid_minimal(self):
        j = ImportJob(
            import_type=ImportType.products,
            original_filename="products.csv",
            file_size_bytes=1024,
            file_hash="abc123" * 10 + "abcd",
        )
        assert j.import_type == ImportType.products
        assert j.status == ImportStatus.uploading
        assert j.total_rows is None
        assert j.valid_rows is None
        assert j.imported_rows == 0
        assert j.failed_rows == 0
        assert j.options == {}

    def test_progress_fields(self):
        j = ImportJob(
            import_type=ImportType.inventory,
            original_filename="inv.csv",
            file_size_bytes=2048,
            file_hash="a" * 64,
            total_rows=100,
            valid_rows=95,
            imported_rows=90,
            failed_rows=5,
        )
        assert j.total_rows == 100
        assert j.imported_rows == 90

    def test_preview_data_default_none(self):
        j = ImportJob(
            import_type=ImportType.vendors,
            original_filename="v.csv",
            file_size_bytes=512,
            file_hash="b" * 64,
        )
        assert j.preview_data is None

    def test_relationships(self):
        rels = set(ImportJob.__sqlmodel_relationships__.keys())
        assert "errors" in rels

    def test_inherits_audit_mixin(self):
        assert issubclass(ImportJob, AuditMixin)


class TestImportErrorRecord:
    def test_valid(self):
        e = ImportErrorRecord(
            job_id=1,
            row_number=5,
            field="catalog_number",
            error_type="validation",
            message="Catalog number is required",
        )
        assert e.job_id == 1
        assert e.row_number == 5
        assert e.error_type == "validation"

    def test_optional_fields(self):
        e = ImportErrorRecord(
            job_id=1,
            row_number=1,
            field=None,
            error_type="system",
            message="Unexpected error",
            raw_data=None,
        )
        assert e.field is None
        assert e.raw_data is None

    def test_not_inheriting_audit_mixin(self):
        """ImportErrorRecord extends SQLModel directly, not AuditMixin."""
        assert not issubclass(ImportErrorRecord, AuditMixin)

    def test_relationships(self):
        rels = set(ImportErrorRecord.__sqlmodel_relationships__.keys())
        assert "job" in rels


# ===========================================================================
# 17. Invitation
# ===========================================================================


class TestInvitation:
    def test_valid(self):
        inv = Invitation(
            email="newuser@example.com",
            name="New User",
            role="grad_student",
            token="tok_abc123xyz",
        )
        assert inv.email == "newuser@example.com"
        assert inv.role == "grad_student"
        assert inv.status == "pending"
        assert inv.invited_by is None
        assert inv.accepted_at is None
        assert inv.expires_at is None

    def test_all_fields(self):
        inv = Invitation(
            email="x@y.com",
            name="X",
            role="postdoc",
            token="tok_long_token_string",
            invited_by=1,
            status="accepted",
            accepted_at=datetime(2026, 3, 27, tzinfo=timezone.utc),
            expires_at=datetime(2026, 4, 27, tzinfo=timezone.utc),
            access_expires_at=None,
        )
        assert inv.status == "accepted"
        assert inv.invited_by == 1

    def test_defaults(self):
        inv = Invitation(email="a@b.com", name="A", role="PI", token="t")
        assert inv.status == "pending"
        assert inv.invited_by is None


# ===========================================================================
# 18. Cross-cutting: required vs optional field verification
# ===========================================================================


class TestRequiredFields:
    """Verify which fields are required vs optional by inspecting model metadata.

    SQLModel does not enforce required fields at instantiation time (only at DB
    insert), so we check field metadata instead.
    """

    def test_vendor_name_is_required_field(self):
        """Vendor.name has no default, so it's required at DB level."""
        assert "name" in Vendor.model_fields
        assert not _is_optional(Vendor, "name")
        assert Vendor.model_fields["name"].is_required()

    def test_product_catalog_number_and_name_required(self):
        assert "catalog_number" in Product.model_fields
        assert "name" in Product.model_fields
        assert not _is_optional(Product, "catalog_number")
        assert not _is_optional(Product, "name")

    def test_staff_name_required(self):
        assert "name" in Staff.model_fields
        assert not _is_optional(Staff, "name")

    def test_storage_location_name_required(self):
        assert "name" in StorageLocation.model_fields
        assert not _is_optional(StorageLocation, "name")

    def test_order_item_order_id_required(self):
        assert "order_id" in OrderItem.model_fields
        assert not _is_optional(OrderItem, "order_id")

    def test_inventory_item_product_id_required(self):
        assert "product_id" in InventoryItem.model_fields
        assert not _is_optional(InventoryItem, "product_id")

    def test_document_file_path_and_file_name_required(self):
        assert not _is_optional(Document, "file_path")
        assert not _is_optional(Document, "file_name")

    def test_alert_entity_id_required(self):
        assert "entity_id" in Alert.model_fields
        assert not _is_optional(Alert, "entity_id")
        assert Alert.model_fields["entity_id"].is_required()

    def test_notification_required_fields(self):
        for field in ("staff_id", "type", "title", "message"):
            assert field in Notification.model_fields
            assert not _is_optional(Notification, field)

    def test_usage_event_required_fields(self):
        assert not _is_optional(UsageEvent, "user_email")
        assert not _is_optional(UsageEvent, "event_type")

    def test_consumption_log_required_fields(self):
        for field in (
            "inventory_id",
            "quantity_used",
            "quantity_remaining",
            "consumed_by",
        ):
            assert not _is_optional(ConsumptionLog, field)

    def test_order_request_requested_by_required(self):
        assert "requested_by" in OrderRequest.model_fields
        assert not _is_optional(OrderRequest, "requested_by")

    def test_equipment_name_required(self):
        assert "name" in Equipment.model_fields
        assert not _is_optional(Equipment, "name")


# ===========================================================================
# 19. Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_vendor_empty_aliases_list(self):
        v = Vendor(name="X", aliases=[])
        assert v.aliases == []

    def test_product_empty_extra_dict(self):
        p = Product(catalog_number="X", name="Y", extra={})
        assert p.extra == {}

    def test_order_empty_extra_dict(self):
        o = Order(extra={})
        assert o.extra == {}

    def test_inventory_zero_quantity(self):
        inv = InventoryItem(product_id=1, quantity_on_hand=Decimal("0"))
        assert inv.quantity_on_hand == Decimal("0")

    def test_product_with_zero_shelf_life(self):
        p = Product(catalog_number="X", name="Y", shelf_life_days=0)
        assert p.shelf_life_days == 0

    def test_staff_zero_failed_login(self):
        s = Staff(name="X", failed_login_count=0)
        assert s.failed_login_count == 0

    def test_alert_resolved_without_acknowledge(self):
        a = Alert(
            alert_type="x",
            severity="info",
            message="m",
            entity_type="t",
            entity_id=1,
            is_acknowledged=False,
            is_resolved=True,
        )
        assert a.is_resolved is True
        assert a.is_acknowledged is False

    def test_audit_log_changes_empty_dict(self):
        log = AuditLog(table_name="t", record_id=1, action="delete", changes={})
        assert log.changes == {}

    def test_import_job_with_preview_data(self):
        j = ImportJob(
            import_type=ImportType.products,
            original_filename="f.csv",
            file_size_bytes=100,
            file_hash="c" * 64,
            preview_data=[{"col1": "val1"}],
        )
        assert len(j.preview_data) == 1

    def test_document_with_none_extracted_data(self):
        doc = Document(
            file_path="x",
            file_name="y",
            extracted_data=None,
            ocr_text=None,
        )
        assert doc.extracted_data is None

    def test_equipment_with_zero_value(self):
        eq = Equipment(name="X", estimated_value=Decimal("0"))
        assert eq.estimated_value == Decimal("0")

    def test_order_request_with_large_justification(self):
        r = OrderRequest(
            requested_by=1,
            justification="A" * 2000,
        )
        assert len(r.justification) == 2000

    def test_vendor_name_single_char(self):
        v = Vendor(name="X")
        assert v.name == "X"

    def test_staff_role_custom_value(self):
        s = Staff(name="X", role="custom_role")
        assert s.role == "custom_role"

    def test_product_cas_number_format(self):
        p = Product(
            catalog_number="X",
            name="Y",
            cas_number="50-00-0",  # formaldehyde
        )
        assert p.cas_number == "50-00-0"

    def test_consumption_log_with_all_action_values(self):
        for action in ("receive", "consume", "transfer", "adjust", "dispose", "open"):
            log = ConsumptionLog(
                inventory_id=1,
                quantity_used=Decimal("1"),
                quantity_remaining=Decimal("0"),
                consumed_by="X",
                action=action,
            )
            assert log.action == action

    def test_order_status_all_values(self):
        for status in ("pending", "shipped", "received", "cancelled", "deleted"):
            o = Order(status=status)
            assert o.status == status

    def test_inventory_status_all_values(self):
        for status in (
            "available",
            "opened",
            "depleted",
            "disposed",
            "expired",
            "deleted",
        ):
            inv = InventoryItem(product_id=1, status=status)
            assert inv.status == status

    def test_document_status_all_values(self):
        for status in (
            "pending",
            "processing",
            "extracted",
            "needs_review",
            "approved",
            "rejected",
            "ocr_failed",
            "deleted",
        ):
            doc = Document(file_path="x", file_name="y", status=status)
            assert doc.status == status
