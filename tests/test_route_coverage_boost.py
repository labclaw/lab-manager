"""Tests to boost coverage for uncovered lines in route modules.

Covers:
- documents.py: _run_extraction, _index_approved_doc branches
- email_ingest.py: _trigger_extraction, JSON invalid payload, raw email size limit
- import_routes.py: file too large, empty CSV, inventory location/date validation
- team.py: list_members, create_invitation, get_member, update_member, deactivate, join
- orders.py: status validation, status_group filters, create duplicate warning
- order_requests.py: auto-create staff, stats, approve/reject, create with invalid urgency
"""

from __future__ import annotations

import io
import os
import struct
import zlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine, db):
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-not-for-production"
    os.environ["ADMIN_PASSWORD"] = "test-admin-password-not-for-production"
    os.environ["UPLOAD_DIR"] = "/tmp/lab-manager-test-uploads"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


def _make_png() -> bytes:
    """Minimal valid 1x1 PNG."""

    def _chunk(ct: bytes, data: bytes) -> bytes:
        c = ct + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat = _chunk(b"IDAT", raw)
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# ===========================================================================
# 1. documents.py — _run_extraction branches (lines 169-170, 178-183, 193-210)
# ===========================================================================


class TestRunExtraction:
    """Test _run_extraction background task directly."""

    def test_extraction_doc_not_found(self, engine, db):
        """Lines 169-170: document not found for extraction."""
        import lab_manager.database as db_mod

        orig_engine = db_mod._engine
        orig_factory = db_mod._session_factory
        db_mod._engine = engine
        db_mod._session_factory = None

        try:
            from lab_manager.api.routes.documents import _run_extraction

            # Call with nonexistent doc_id — should return without error
            _run_extraction(99999)
        finally:
            db_mod._engine = orig_engine
            db_mod._session_factory = orig_factory

    def test_extraction_ocr_failure(self, engine, db):
        """Lines 178-183: OCR fails, doc set to needs_review."""
        from lab_manager.models.document import Document, DocumentStatus

        import lab_manager.database as db_mod

        orig_engine = db_mod._engine
        orig_factory = db_mod._session_factory
        db_mod._engine = engine
        db_mod._session_factory = None

        doc = Document(
            file_path="/tmp/lab-manager-test-uploads/test.png",
            file_name="test.png",
            status=DocumentStatus.processing,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

        try:
            with patch(
                "lab_manager.intake.ocr.extract_text_from_image",
                side_effect=RuntimeError("OCR engine error"),
            ):
                from lab_manager.api.routes.documents import _run_extraction

                _run_extraction(doc_id)

            # Refresh in a new session to see the update
            db.expire_all()
            updated = db.get(Document, doc_id)
            assert updated.status == DocumentStatus.needs_review
            assert "OCR failed" in (updated.review_notes or "")
        finally:
            db_mod._engine = orig_engine
            db_mod._session_factory = orig_factory

    def test_extraction_success(self, engine, db):
        """Lines 193-210: successful OCR + extraction path."""
        from lab_manager.models.document import Document, DocumentStatus

        import lab_manager.database as db_mod

        orig_engine = db_mod._engine
        orig_factory = db_mod._session_factory
        db_mod._engine = engine
        db_mod._session_factory = None

        doc = Document(
            file_path="/tmp/lab-manager-test-uploads/test.png",
            file_name="test.png",
            status=DocumentStatus.processing,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

        mock_extracted = MagicMock()
        mock_extracted.document_type = "packing_list"
        mock_extracted.vendor_name = "Sigma"
        mock_extracted.confidence = 0.95
        mock_extracted.model_dump.return_value = {"document_type": "packing_list"}

        try:
            with (
                patch(
                    "lab_manager.intake.ocr.extract_text_from_image",
                    return_value="Order #12345\nVendor: Sigma",
                ),
                patch(
                    "lab_manager.intake.extractor.extract_from_text",
                    return_value=mock_extracted,
                ),
            ):
                from lab_manager.api.routes.documents import _run_extraction

                _run_extraction(doc_id)

            db.expire_all()
            updated = db.get(Document, doc_id)
            assert updated.status == DocumentStatus.needs_review
            assert updated.document_type == "packing_list"
            assert updated.extraction_confidence == 0.95
        finally:
            db_mod._engine = orig_engine
            db_mod._session_factory = orig_factory

    def test_extraction_extractor_failure(self, engine, db):
        """Lines 204-207: extraction (not OCR) fails, sets needs_review."""
        from lab_manager.models.document import Document, DocumentStatus

        import lab_manager.database as db_mod

        orig_engine = db_mod._engine
        orig_factory = db_mod._session_factory
        db_mod._engine = engine
        db_mod._session_factory = None

        doc = Document(
            file_path="/tmp/lab-manager-test-uploads/test.png",
            file_name="test.png",
            status=DocumentStatus.processing,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id

        try:
            with (
                patch(
                    "lab_manager.intake.ocr.extract_text_from_image",
                    return_value="Some valid OCR text",
                ),
                patch(
                    "lab_manager.intake.extractor.extract_from_text",
                    side_effect=ValueError("extraction parse error"),
                ),
            ):
                from lab_manager.api.routes.documents import _run_extraction

                _run_extraction(doc_id)

            db.expire_all()
            updated = db.get(Document, doc_id)
            assert updated.status == DocumentStatus.needs_review
            assert "Extraction failed" in (updated.review_notes or "")
        finally:
            db_mod._engine = orig_engine
            db_mod._session_factory = orig_factory


# ===========================================================================
# 2. documents.py — _index_approved_doc (lines 238, 241-242, 259-260,
#    264-265, 280-281, 285-286, 290-291)
# ===========================================================================


class TestIndexApprovedDoc:
    """Test _index_approved_doc background task directly."""

    def test_index_doc_not_found(self, engine, db):
        """Line 238: doc not found, early return."""
        import lab_manager.database as db_mod

        orig_engine = db_mod._engine
        orig_factory = db_mod._session_factory
        db_mod._engine = engine
        db_mod._session_factory = None

        try:
            from lab_manager.api.routes.documents import _index_approved_doc

            _index_approved_doc(99999)  # should not raise
        finally:
            db_mod._engine = orig_engine
            db_mod._session_factory = orig_factory

    def test_index_doc_all_indexers_fail(self, engine, db):
        """Lines 241-242, 259-260, 264-265, 280-281, 285-286, 290-291:
        Each index_* call raises, but the function continues."""
        from lab_manager.models.document import Document, DocumentStatus
        from lab_manager.models.inventory import InventoryItem
        from lab_manager.models.order import Order, OrderItem, OrderStatus
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        import lab_manager.database as db_mod

        orig_engine = db_mod._engine
        orig_factory = db_mod._session_factory
        db_mod._engine = engine
        db_mod._session_factory = None

        # Create a full chain: vendor -> order -> items -> product -> inventory
        doc = Document(
            file_path="/tmp/test.png",
            file_name="test.png",
            status=DocumentStatus.approved,
        )
        db.add(doc)
        db.flush()

        vendor = Vendor(name="TestVendor")
        db.add(vendor)
        db.flush()

        order = Order(
            document_id=doc.id,
            vendor_id=vendor.id,
            status=OrderStatus.received,
        )
        db.add(order)
        db.flush()

        product = Product(
            catalog_number="CAT-001",
            name="Test Product",
            vendor_id=vendor.id,
        )
        db.add(product)
        db.flush()

        oi = OrderItem(
            order_id=order.id,
            catalog_number="CAT-001",
            description="Test item",
            quantity=1,
            product_id=product.id,
        )
        db.add(oi)
        db.flush()

        inv = InventoryItem(
            product_id=product.id,
            order_item_id=oi.id,
            quantity_on_hand=5,
            status="available",
        )
        db.add(inv)
        db.commit()

        doc_id = doc.id

        try:
            # Patch all index functions to raise at their source module
            with (
                patch(
                    "lab_manager.services.search.index_document_record",
                    side_effect=RuntimeError("index fail"),
                ),
                patch(
                    "lab_manager.services.search.index_vendor_record",
                    side_effect=RuntimeError("index fail"),
                ),
                patch(
                    "lab_manager.services.search.index_order_record",
                    side_effect=RuntimeError("index fail"),
                ),
                patch(
                    "lab_manager.services.search.index_order_item_record",
                    side_effect=RuntimeError("index fail"),
                ),
                patch(
                    "lab_manager.services.search.index_product_record",
                    side_effect=RuntimeError("index fail"),
                ),
                patch(
                    "lab_manager.services.search.index_inventory_record",
                    side_effect=RuntimeError("index fail"),
                ),
            ):
                from lab_manager.api.routes.documents import _index_approved_doc

                _index_approved_doc(doc_id)  # should not raise
        finally:
            db_mod._engine = orig_engine
            db_mod._session_factory = orig_factory


# ===========================================================================
# 3. email_ingest.py (lines 42-44, 95-97, 136)
# ===========================================================================


class TestEmailIngest:
    def test_trigger_extraction_calls_run_extraction(self):
        """Lines 42-44: _trigger_extraction delegates to _run_extraction."""
        with patch("lab_manager.api.routes.documents._run_extraction") as mock_run:
            from lab_manager.api.routes.email_ingest import _trigger_extraction

            _trigger_extraction(42)
            mock_run.assert_called_once_with(42)

    def test_json_ingest_invalid_payload(self, client):
        """Lines 95-97: invalid JSON payload returns 422."""
        resp = client.post(
            "/api/v1/email/ingest",
            content=b'{"bad": "data"}',
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422
        assert "Invalid JSON" in resp.json()["detail"]

    def test_raw_email_too_large(self, client):
        """Line 136: raw email exceeding size limit returns 413."""
        # Create a body larger than 50 MB
        big_body = b"X" * (50 * 1024 * 1024 + 1)
        resp = client.post(
            "/api/v1/email/ingest",
            content=big_body,
            headers={"Content-Type": "message/rfc822"},
        )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"]


# ===========================================================================
# 4. import_routes.py (lines 44, 54, 88-89, 93, 98, 125-126, 135-136,
#    256, 353, 371, 392-399, 416-423, 479)
# ===========================================================================


def _csv_bytes(header: str, *rows: str) -> bytes:
    lines = [header] + list(rows)
    return "\n".join(lines).encode("utf-8")


def _upload(client, entity: str, content: bytes, filename: str = "test.csv"):
    return client.post(
        f"/api/v1/import/{entity}",
        files={"file": (filename, io.BytesIO(content), "text/csv")},
    )


class TestImportRoutesCoverage:
    def test_file_too_large(self, client):
        """Line 44: file exceeds max size."""
        big = b"name\n" + b"x" * (10 * 1024 * 1024 + 1)
        resp = _upload(client, "vendors", big)
        data = resp.json()
        assert data["imported"] == 0
        assert any("too large" in e["message"] for e in data["errors"])

    def test_csv_parse_error_not_utf8(self, client):
        """Line 54 + line 88-89: non-UTF8 content."""
        bad_bytes = b"\xff\xfe" + b"\x80\x81" * 100
        resp = _upload(client, "vendors", bad_bytes)
        data = resp.json()
        assert data["imported"] == 0
        assert len(data["errors"]) > 0

    def test_csv_no_header(self, client):
        """Line 93: CSV with no header row."""
        resp = _upload(client, "vendors", b"")
        data = resp.json()
        assert data["imported"] == 0
        assert len(data["errors"]) > 0

    def test_csv_exceeds_max_rows(self, client):
        """Line 98: CSV with more than 5000 rows."""
        header = "name"
        rows = [f"Vendor{i}" for i in range(5002)]
        content = (header + "\n" + "\n".join(rows)).encode("utf-8")
        resp = _upload(client, "vendors", content)
        data = resp.json()
        assert data["imported"] == 0
        assert any("5000" in e["message"] for e in data["errors"])

    def test_product_missing_name(self, client):
        """Lines 125-126 (product): missing name value."""
        csv = _csv_bytes("catalog_number,name", "CAT-001,")
        resp = _upload(client, "products", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any(e["field"] == "name" for e in data["errors"])

    def test_product_invalid_vendor_id(self, client):
        """Lines 135-136: vendor_id does not exist."""
        csv = _csv_bytes("catalog_number,name,vendor_id", "CAT-001,Test Product,99999")
        resp = _upload(client, "products", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("vendor_id" in e["field"] for e in data["errors"])

    def test_product_missing_catalog_number(self, client):
        """Line 256 (catalog_number required)."""
        csv = _csv_bytes("catalog_number,name", ",Test Product")
        resp = _upload(client, "products", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any(e["field"] == "catalog_number" for e in data["errors"])

    def test_inventory_product_not_found(self, client):
        """Line 353: product_id does not exist."""
        csv = _csv_bytes("product_id,quantity_on_hand", "99999,10")
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("product_id" in e["field"] for e in data["errors"])

    def test_inventory_negative_quantity(self, client):
        """Line 371: negative quantity_on_hand."""
        csv = _csv_bytes("product_id,quantity_on_hand", "1,-5")
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("quantity_on_hand" in e["field"] for e in data["errors"])

    def test_inventory_invalid_location_id(self, client, db):
        """Lines 392-399: location_id does not exist."""
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="V1")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="P1", name="Product1", vendor_id=vendor.id)
        db.add(product)
        db.flush()

        csv = _csv_bytes(
            "product_id,quantity_on_hand,location_id",
            f"{product.id},10,99999",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("location_id" in e["field"] for e in data["errors"])

    def test_inventory_invalid_expiry_date(self, client, db):
        """Lines 416-423: bad expiry_date format."""
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="V2")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="P2", name="Product2", vendor_id=vendor.id)
        db.add(product)
        db.flush()

        csv = _csv_bytes(
            "product_id,quantity_on_hand,expiry_date",
            f"{product.id},10,not-a-date",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("expiry_date" in e["field"] for e in data["errors"])

    def test_inventory_invalid_opened_date(self, client, db):
        """Lines 416-423 variant: bad opened_date format."""
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="V3")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="P3", name="Product3", vendor_id=vendor.id)
        db.add(product)
        db.flush()

        csv = _csv_bytes(
            "product_id,quantity_on_hand,opened_date",
            f"{product.id},10,bad-date",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("opened_date" in e["field"] for e in data["errors"])

    def test_inventory_valid_import(self, client, db):
        """Line 479: successful inventory import with flush."""
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="V4")
        db.add(vendor)
        db.flush()
        product = Product(catalog_number="P4", name="Product4", vendor_id=vendor.id)
        db.add(product)
        db.flush()

        csv = _csv_bytes(
            "product_id,quantity_on_hand,unit",
            f"{product.id},10,mL",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 1
        assert data["errors"] == []


# ===========================================================================
# 5. team.py (lines 35, 77, 188, 255, 350, 385, 392-396)
# ===========================================================================


class TestTeamRoutesCoverage:
    def test_list_members(self, client):
        """Line 35: GET /api/v1/team/ returns paginated list."""
        resp = client.get("/api/v1/team/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_invite_invalid_name(self, client):
        """Line 77: name too long or empty raises 422."""
        resp = client.post(
            "/api/v1/team/invite",
            json={"email": "test@lab.edu", "name": "", "role": "grad_student"},
        )
        assert resp.status_code == 422

    def test_invite_valid(self, client):
        """Line 188: create invitation successfully."""
        resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": "newuser@lab.edu",
                "name": "New User",
                "role": "grad_student",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newuser@lab.edu"
        assert data["status"] == "pending"
        assert "token" in data

    def test_get_member_not_found(self, client):
        """Line 255: GET /api/v1/team/{id} returns 404."""
        resp = client.get("/api/v1/team/99999")
        assert resp.status_code == 404

    def test_get_member_found(self, client, db):
        """Line 255: GET member returns details with permissions."""
        from lab_manager.models.staff import Staff

        staff = Staff(
            name="TestMember",
            email="member@lab.edu",
            role="grad_student",
            role_level=3,
            is_active=True,
        )
        db.add(staff)
        db.flush()

        resp = client.get(f"/api/v1/team/{staff.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TestMember"
        assert "permissions" in data

    def test_update_member_role(self, client, db):
        """Line 350: PATCH /api/v1/team/{id} updates role."""
        from lab_manager.models.staff import Staff

        staff = Staff(
            name="PromoteMe",
            email="promote@lab.edu",
            role="grad_student",
            role_level=3,
            is_active=True,
        )
        db.add(staff)
        db.flush()

        resp = client.patch(
            f"/api/v1/team/{staff.id}",
            json={"role": "postdoc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "postdoc"

    def test_deactivate_member(self, client, db):
        """Line 385: DELETE /api/v1/team/{id} deactivates member."""
        from lab_manager.models.staff import Staff

        staff = Staff(
            name="DeactivateMe",
            email="deactivate@lab.edu",
            role="grad_student",
            role_level=3,
            is_active=True,
        )
        db.add(staff)
        db.flush()

        resp = client.delete(f"/api/v1/team/{staff.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_join_with_existing_inactive_staff(self, client, db):
        """Lines 392-396: join reactivates an existing inactive staff record."""
        from lab_manager.models.invitation import Invitation
        from lab_manager.models.staff import Staff

        # Create inactive staff
        staff = Staff(
            name="OldName",
            email="rejoiner@lab.edu",
            role="visitor",
            role_level=4,
            is_active=False,
        )
        db.add(staff)
        db.flush()

        # Create a pending invitation via the serializer
        from lab_manager.api.routes.team import _get_invite_serializer

        serializer = _get_invite_serializer()
        import secrets

        token_data = {
            "email": "rejoiner@lab.edu",
            "role": "grad_student",
            "nonce": secrets.token_hex(8),
        }
        token = serializer.dumps(token_data)

        invitation = Invitation(
            email="rejoiner@lab.edu",
            name="Rejoiner",
            role="grad_student",
            token=token,
            status="pending",
        )
        db.add(invitation)
        db.flush()

        resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "secure_password_123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["user"]["role"] == "grad_student"

        # Verify staff was reactivated
        db.expire_all()
        updated_staff = db.get(Staff, staff.id)
        assert updated_staff.is_active is True
        assert updated_staff.name == "Rejoiner"


# ===========================================================================
# 6. orders.py (lines 99, 205-208, 226, 261)
# ===========================================================================


class TestOrdersCoverage:
    def test_create_order_invalid_status(self, client):
        """Line 99: invalid status in OrderCreate raises validation error."""
        resp = client.post(
            "/api/v1/orders/",
            json={"status": "bogus_status"},
        )
        assert resp.status_code == 422

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_list_orders_status_group_active(self, mock_idx, client):
        """Lines 205-208: status_group='active' filters."""
        resp = client.get("/api/v1/orders/?status_group=active")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_list_orders_status_group_past(self, mock_idx, client):
        """Lines 205-208: status_group='past' filters."""
        resp = client.get("/api/v1/orders/?status_group=past")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_list_orders_status_group_drafts(self, mock_idx, client):
        """Lines 205-208: status_group='drafts' filters."""
        resp = client.get("/api/v1/orders/?status_group=drafts")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_create_order_non_pending_status(self, mock_idx, client):
        """Line 226: creating order with non-pending status rejected."""
        resp = client.post(
            "/api/v1/orders/",
            json={"status": "received"},
        )
        assert resp.status_code == 422

    @patch("lab_manager.api.routes.orders.index_order_record")
    def test_create_order_with_duplicate_warning(self, mock_idx, client, db):
        """Line 261: create order that triggers duplicate PO warning."""
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="OrderVendor")
        db.add(vendor)
        db.flush()

        # Create first order
        resp1 = client.post(
            "/api/v1/orders/",
            json={
                "po_number": "DUP-PO-001",
                "vendor_id": vendor.id,
                "status": "pending",
            },
        )
        assert resp1.status_code == 201

        # Second with same PO should be blocked by duplicate check (409)
        resp2 = client.post(
            "/api/v1/orders/",
            json={
                "po_number": "DUP-PO-001",
                "vendor_id": vendor.id,
                "status": "pending",
            },
        )
        assert resp2.status_code == 409


# ===========================================================================
# 7. order_requests.py (lines 90-92, 113, 144, 160, 208, 260)
# ===========================================================================


class TestOrderRequestsCoverage:
    def _seed(self, db):
        from lab_manager.models.staff import Staff
        from lab_manager.models.vendor import Vendor

        admin = Staff(name="pi_user", email="pi@lab.edu", role="pi", is_active=True)
        student = Staff(
            name="system", email="system@lab.edu", role="grad_student", is_active=True
        )
        vendor = Vendor(name="ReqVendor")
        db.add_all([admin, student, vendor])
        db.flush()
        return {"admin": admin, "student": student, "vendor": vendor}

    def test_auto_create_staff_on_request(self, client, db):
        """Lines 90-92: _get_current_staff auto-creates staff record."""
        # X-User header set to a name that doesn't exist yet
        resp = client.post(
            "/api/v1/requests/",
            json={
                "description": "New item",
                "quantity": "1",
            },
            headers={"X-User": "brand_new_user"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["requested_by"] is not None

    def test_stats_endpoint(self, client, db):
        """Line 113: stats endpoint returns counts by status."""
        self._seed(db)
        resp = client.get(
            "/api/v1/requests/stats",
            headers={"X-User": "pi_user"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "pending" in data

    def test_list_with_filters(self, client, db):
        """Line 144: list with urgency filter."""
        self._seed(db)
        resp = client.get(
            "/api/v1/requests/?urgency=urgent",
            headers={"X-User": "pi_user"},
        )
        assert resp.status_code == 200

    def test_create_invalid_urgency_normalized(self, client, db):
        """Line 160: invalid urgency gets normalized to 'normal'."""
        self._seed(db)
        resp = client.post(
            "/api/v1/requests/",
            json={
                "description": "Some item",
                "quantity": "1",
                "urgency": "super_urgent",
            },
            headers={"X-User": "system"},
        )
        assert resp.status_code == 201
        assert resp.json()["urgency"] == "normal"

    def test_approve_requires_vendor(self, client, db):
        """Line 208: approve without vendor_id returns 400."""
        seeds = self._seed(db)

        # Create request without vendor
        resp = client.post(
            "/api/v1/requests/",
            json={"description": "Need item", "quantity": "1"},
            headers={"X-User": "system"},
        )
        assert resp.status_code == 201
        req_id = resp.json()["id"]

        # Approve should fail because vendor_id is None
        resp2 = client.post(
            f"/api/v1/requests/{req_id}/approve",
            json={"note": "approved"},
            headers={"X-User": "pi_user"},
        )
        assert resp2.status_code == 400

    def test_reject_non_pending_fails(self, client, db):
        """Line 260: rejecting a non-pending request returns 409."""
        seeds = self._seed(db)

        # Create and then reject
        resp = client.post(
            "/api/v1/requests/",
            json={
                "description": "Reject me",
                "quantity": "1",
                "vendor_id": seeds["vendor"].id,
            },
            headers={"X-User": "system"},
        )
        assert resp.status_code == 201
        req_id = resp.json()["id"]

        # First reject
        resp2 = client.post(
            f"/api/v1/requests/{req_id}/reject",
            json={"note": "no"},
            headers={"X-User": "pi_user"},
        )
        assert resp2.status_code == 200

        # Second reject should fail — already rejected
        resp3 = client.post(
            f"/api/v1/requests/{req_id}/reject",
            json={"note": "no again"},
            headers={"X-User": "pi_user"},
        )
        assert resp3.status_code == 409
