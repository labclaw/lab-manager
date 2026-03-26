"""Tests for api/routes/documents.py — cover _create_order_from_doc, review_document guards, upload edge cases, _index_approved_doc, list filters."""

import io
import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError


# ---- DocumentCreate / DocumentUpdate validators ----


class TestDocumentCreateValidators:
    def test_valid_status_values(self):
        from lab_manager.api.routes.documents import DocumentCreate

        doc = DocumentCreate(
            file_path="uploads/test.png",
            file_name="test.png",
            status="pending",
        )
        assert doc.status == "pending"

    def test_invalid_status_raises(self):
        from lab_manager.api.routes.documents import DocumentCreate

        with pytest.raises(ValidationError):
            DocumentCreate(
                file_path="uploads/test.png",
                file_name="test.png",
                status="invalid_status",
            )

    def test_path_traversal_rejected(self):
        from lab_manager.api.routes.documents import DocumentCreate

        with pytest.raises(ValidationError, match="upload_dir"):
            DocumentCreate(
                file_path="../../etc/passwd",
                file_name="test.png",
            )

    def test_blocked_prefix_rejected(self):
        from lab_manager.api.routes.documents import DocumentCreate

        with pytest.raises(ValidationError, match="upload_dir"):
            DocumentCreate(
                file_path="/etc/passwd",
                file_name="test.png",
            )

    def test_all_valid_statuses(self):
        from lab_manager.api.routes.documents import DocumentCreate

        for status in [
            "pending",
            "processing",
            "needs_review",
            "approved",
            "rejected",
            "ocr_failed",
            "deleted",
        ]:
            doc = DocumentCreate(
                file_path="uploads/test.png",
                file_name="test.png",
                status=status,
            )
            assert doc.status == status


class TestDocumentUpdateValidators:
    def test_none_values_ok(self):
        from lab_manager.api.routes.documents import DocumentUpdate

        update = DocumentUpdate()
        assert update.file_path is None
        assert update.status is None

    def test_valid_partial_update(self):
        from lab_manager.api.routes.documents import DocumentUpdate

        update = DocumentUpdate(status="approved")
        assert update.status == "approved"

    def test_invalid_status_raises(self):
        from lab_manager.api.routes.documents import DocumentUpdate

        with pytest.raises(ValidationError):
            DocumentUpdate(status="bogus")

    def test_path_traversal_on_update(self):
        from lab_manager.api.routes.documents import DocumentUpdate

        with pytest.raises(ValidationError, match="upload_dir"):
            DocumentUpdate(file_path="/etc/shadow")


class TestValidateFilePath:
    def test_normal_path(self):
        from lab_manager.api.routes.documents import _validate_file_path

        assert _validate_file_path("test.png") == "test.png"

    def test_double_dot_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir"):
            _validate_file_path("../../etc/passwd")

    def test_var_prefix_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir"):
            _validate_file_path("/var/tmp/test.png")

    def test_root_prefix_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir"):
            _validate_file_path("/root/test.png")

    def test_home_prefix_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir"):
            _validate_file_path("/home/user/test.png")

    def test_proc_prefix_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir"):
            _validate_file_path("/proc/self/mem")

    def test_sys_prefix_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir"):
            _validate_file_path("/sys/kernel/notes")


# ---- Upload endpoint edge cases ----


class TestUploadEdgeCases:
    @pytest.fixture()
    def upload_client(self, db_session, tmp_path):
        d = tmp_path / "uploads"
        d.mkdir()
        os.environ["UPLOAD_DIR"] = str(d)
        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from lab_manager.api.routes import documents

        app = create_app()
        documents._run_extraction = lambda doc_id: None

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            yield c, d
        get_settings.cache_clear()

    def _make_png(self):
        import struct
        import zlib

        def _chunk(chunk_type, data):
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        raw = zlib.compress(b"\x00\xff\xff\xff")
        idat = _chunk(b"IDAT", raw)
        iend = _chunk(b"IEND", b"")
        return sig + ihdr + idat + iend

    def test_upload_null_bytes_stripped(self, upload_client):
        client, _ = upload_client
        png = self._make_png()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("evil\x00name.png", io.BytesIO(png), "image/png")},
        )
        assert resp.status_code == 201
        assert "\x00" not in resp.json()["file_name"]

    def test_upload_slash_stripped(self, upload_client):
        client, _ = upload_client
        png = self._make_png()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("path/with/slashes.png", io.BytesIO(png), "image/png")},
        )
        assert resp.status_code == 201
        assert "/" not in resp.json()["file_name"]

    def test_upload_backslash_stripped(self, upload_client):
        client, _ = upload_client
        png = self._make_png()
        resp = client.post(
            "/api/v1/documents/upload",
            files={
                "file": ("path\\with\\backslashes.png", io.BytesIO(png), "image/png")
            },
        )
        assert resp.status_code == 201
        assert "\\" not in resp.json()["file_name"]

    def test_upload_tiff_accepted(self, upload_client):
        client, _ = upload_client
        fake_tiff = b"II\x2a\x00" + b"\x00" * 100
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("scan.tiff", io.BytesIO(fake_tiff), "image/tiff")},
        )
        assert resp.status_code == 201

    def test_upload_unnamed_file(self, upload_client):
        client, _ = upload_client
        png = self._make_png()
        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("", io.BytesIO(png), "image/png")},
        )
        # FastAPI rejects empty filename at framework level
        assert resp.status_code in (201, 422)


# ---- Review endpoint status guards ----


class TestReviewDocumentGuards:
    @pytest.fixture()
    def review_client(self, db_session, tmp_path):
        d = tmp_path / "uploads"
        d.mkdir()
        os.environ["UPLOAD_DIR"] = str(d)
        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from lab_manager.api.routes import documents

        app = create_app()
        documents._run_extraction = lambda doc_id: None

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            yield c
        get_settings.cache_clear()

    def _create_needs_review_doc(self, client):
        """Create a document in needs_review status via direct DB insert."""
        from lab_manager.models.document import Document, DocumentStatus

        # Use the API to create a doc, then update its status

        doc = Document(
            file_path="/tmp/test.png",
            file_name="test_review.png",
            status=DocumentStatus.needs_review,
            vendor_name="TestVendor",
            extracted_data={
                "vendor_name": "TestVendor",
                "items": [{"catalog_number": "CAT-001", "quantity": 5, "unit": "EA"}],
            },
        )
        from lab_manager.api.deps import get_db

        # Get the session from the app
        db = client.app.dependency_overrides[get_db]
        gen = db()
        session = next(gen)
        session.add(doc)
        session.flush()
        doc_id = doc.id
        return doc_id, session

    def test_review_processing_rejected(self, db_session):
        from lab_manager.models.document import Document, DocumentStatus

        doc = Document(
            file_path="/tmp/test.png",
            file_name="proc.png",
            status=DocumentStatus.processing,
        )
        db_session.add(doc)
        db_session.flush()

        os.environ["UPLOAD_DIR"] = "/tmp/test-uploads"
        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from lab_manager.api.routes import documents

        app = create_app()
        documents._run_extraction = lambda doc_id: None

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            resp = c.post(
                f"/api/v1/documents/{doc.id}/review",
                json={"action": "approve"},
            )
            assert resp.status_code == 409
            assert "processed" in resp.json()["detail"].lower()
        get_settings.cache_clear()

    def test_review_already_approved_rejected(self, db_session):
        from lab_manager.models.document import Document, DocumentStatus

        doc = Document(
            file_path="/tmp/test.png",
            file_name="approved.png",
            status=DocumentStatus.approved,
        )
        db_session.add(doc)
        db_session.flush()

        os.environ["UPLOAD_DIR"] = "/tmp/test-uploads"
        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from lab_manager.api.routes import documents

        app = create_app()
        documents._run_extraction = lambda doc_id: None

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            resp = c.post(
                f"/api/v1/documents/{doc.id}/review",
                json={"action": "reject"},
            )
            assert resp.status_code == 409
        get_settings.cache_clear()

    def test_review_reject_success(self, db_session):
        from lab_manager.models.document import Document, DocumentStatus

        doc = Document(
            file_path="/tmp/test.png",
            file_name="reject_me.png",
            status=DocumentStatus.needs_review,
            vendor_name="TestVendor",
            extracted_data={"vendor_name": "TestVendor", "items": []},
        )
        db_session.add(doc)
        db_session.flush()

        os.environ["UPLOAD_DIR"] = "/tmp/test-uploads"
        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from lab_manager.api.routes import documents

        app = create_app()
        documents._run_extraction = lambda doc_id: None

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            resp = c.post(
                f"/api/v1/documents/{doc.id}/review",
                json={
                    "action": "reject",
                    "reviewed_by": "Reviewer",
                    "review_notes": "Bad quality",
                },
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "rejected"
        get_settings.cache_clear()

    def test_approve_creates_order(self, db_session):
        from lab_manager.models.document import Document, DocumentStatus

        doc = Document(
            file_path="/tmp/test.png",
            file_name="approve_me.png",
            status=DocumentStatus.needs_review,
            vendor_name="Sigma-Aldrich",
            extracted_data={
                "vendor_name": "Sigma-Aldrich",
                "items": [
                    {
                        "catalog_number": "CAT-001",
                        "description": "Reagent X",
                        "quantity": 5,
                        "unit": "EA",
                    }
                ],
            },
        )
        db_session.add(doc)
        db_session.flush()

        os.environ["UPLOAD_DIR"] = "/tmp/test-uploads"
        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from lab_manager.api.routes import documents

        app = create_app()
        documents._run_extraction = lambda doc_id: None
        documents._index_approved_doc = lambda doc_id: None

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            resp = c.post(
                f"/api/v1/documents/{doc.id}/review",
                json={"action": "approve", "reviewed_by": "Reviewer"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "approved"
        get_settings.cache_clear()


# ---- _create_order_from_doc ----


class TestCreateOrderFromDoc:
    def test_no_vendor_no_items_skips(self, db_session):
        from lab_manager.api.routes.documents import _create_order_from_doc
        from lab_manager.models.document import Document, DocumentStatus

        doc = Document(
            file_path="/tmp/test.png",
            file_name="empty.png",
            status=DocumentStatus.needs_review,
            extracted_data={"vendor_name": "", "items": []},
        )
        db_session.add(doc)
        db_session.flush()
        # Should not raise, just skip
        _create_order_from_doc(doc, db_session)

    def test_order_without_items(self, db_session):
        from lab_manager.api.routes.documents import _create_order_from_doc
        from lab_manager.models.document import Document, DocumentStatus
        from lab_manager.models.order import Order

        doc = Document(
            file_path="/tmp/test.png",
            file_name="no_items.png",
            status=DocumentStatus.needs_review,
            vendor_name="TestVendor",
            extracted_data={"vendor_name": "TestVendor", "items": []},
        )
        db_session.add(doc)
        db_session.flush()

        _create_order_from_doc(doc, db_session)
        order = db_session.query(Order).filter(Order.document_id == doc.id).first()
        assert order is not None

    def test_bad_order_date_handled(self, db_session):
        from lab_manager.api.routes.documents import _create_order_from_doc
        from lab_manager.models.document import Document, DocumentStatus
        from lab_manager.models.order import Order

        doc = Document(
            file_path="/tmp/test.png",
            file_name="bad_date.png",
            status=DocumentStatus.needs_review,
            vendor_name="TestVendor",
            extracted_data={
                "vendor_name": "TestVendor",
                "items": [{"catalog_number": "CAT-001", "quantity": 2}],
                "order_date": "not-a-date",
            },
        )
        db_session.add(doc)
        db_session.flush()

        _create_order_from_doc(doc, db_session)
        order = db_session.query(Order).filter(Order.document_id == doc.id).first()
        assert order is not None
        assert order.order_date is None

    def test_items_create_product_and_inventory(self, db_session):
        from lab_manager.api.routes.documents import _create_order_from_doc
        from lab_manager.models.document import Document, DocumentStatus
        from lab_manager.models.inventory import InventoryItem
        from lab_manager.models.order import Order, OrderItem
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        doc = Document(
            file_path="/tmp/test.png",
            file_name="full.png",
            status=DocumentStatus.needs_review,
            vendor_name="Sigma-Aldrich",
            extracted_data={
                "vendor_name": "Sigma-Aldrich",
                "items": [
                    {
                        "catalog_number": "CAT-001",
                        "description": "Reagent",
                        "quantity": 5,
                        "unit": "EA",
                    },
                ],
            },
        )
        db_session.add(doc)
        db_session.flush()

        _create_order_from_doc(doc, db_session)

        vendor = db_session.query(Vendor).filter(Vendor.name == "Sigma-Aldrich").first()
        assert vendor is not None
        product = (
            db_session.query(Product)
            .filter(Product.catalog_number == "CAT-001")
            .first()
        )
        assert product is not None
        assert product.vendor_id == vendor.id
        order = db_session.query(Order).filter(Order.document_id == doc.id).first()
        assert order is not None
        oi = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).first()
        assert oi is not None
        inv = (
            db_session.query(InventoryItem)
            .filter(InventoryItem.order_item_id == oi.id)
            .first()
        )
        assert inv is not None

    def test_existing_product_reused(self, db_session):
        from lab_manager.api.routes.documents import _create_order_from_doc
        from lab_manager.models.document import Document, DocumentStatus
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        vendor = Vendor(name="ExistingVendor")
        db_session.add(vendor)
        db_session.flush()
        product = Product(
            catalog_number="CAT-EXIST", name="Existing Product", vendor_id=vendor.id
        )
        db_session.add(product)
        db_session.flush()

        doc = Document(
            file_path="/tmp/test.png",
            file_name="reuse.png",
            status=DocumentStatus.needs_review,
            vendor_name="ExistingVendor",
            extracted_data={
                "vendor_name": "ExistingVendor",
                "items": [{"catalog_number": "CAT-EXIST", "quantity": 3}],
            },
        )
        db_session.add(doc)
        db_session.flush()

        _create_order_from_doc(doc, db_session)
        products = (
            db_session.query(Product)
            .filter(Product.catalog_number == "CAT-EXIST")
            .all()
        )
        assert len(products) == 1  # reused, not duplicated


# ---- List documents with filters ----


class TestListDocuments:
    @pytest.fixture()
    def list_client(self, db_session):
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

    def _seed_docs(self, db):
        from lab_manager.models.document import Document, DocumentStatus

        docs = [
            Document(
                file_path="/tmp/a.png",
                file_name="a.png",
                status=DocumentStatus.approved,
                vendor_name="Sigma",
                document_type="invoice",
            ),
            Document(
                file_path="/tmp/b.png",
                file_name="b.png",
                status=DocumentStatus.pending,
                vendor_name="Fisher",
                document_type="packing_list",
            ),
            Document(
                file_path="/tmp/c.png",
                file_name="c.png",
                status=DocumentStatus.approved,
                vendor_name="Sigma",
                document_type="certificate_of_analysis",
            ),
        ]
        for d in docs:
            db.add(d)
        db.flush()

    def test_filter_by_status(self, list_client, db_session):
        self._seed_docs(db_session)
        resp = list_client.get("/api/v1/documents/?status=pending")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["status"] == "pending" for i in items)

    def test_filter_by_vendor_name(self, list_client, db_session):
        self._seed_docs(db_session)
        resp = list_client.get("/api/v1/documents/?vendor_name=Sigma")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all("Sigma" in i["vendor_name"] for i in items)

    def test_filter_by_document_type(self, list_client, db_session):
        self._seed_docs(db_session)
        resp = list_client.get("/api/v1/documents/?document_type=invoice")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["document_type"] == "invoice" for i in items)

    def test_sort_by_name_desc(self, list_client, db_session):
        self._seed_docs(db_session)
        resp = list_client.get("/api/v1/documents/?sort_by=file_name&sort_dir=desc")
        assert resp.status_code == 200
        names = [i["file_name"] for i in resp.json()["items"]]
        assert names == sorted(names, reverse=True)

    def test_search_filter(self, list_client, db_session):
        self._seed_docs(db_session)
        resp = list_client.get("/api/v1/documents/?search=Sigma")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

    def test_filter_by_extraction_model(self, list_client, db_session):
        self._seed_docs(db_session)
        from lab_manager.models.document import Document, DocumentStatus

        doc = Document(
            file_path="/tmp/d.png",
            file_name="d.png",
            status=DocumentStatus.approved,
            extraction_model="gemini-2.5-flash",
        )
        db_session.add(doc)
        db_session.flush()

        resp = list_client.get("/api/v1/documents/?extraction_model=gemini-2.5-flash")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i.get("extraction_model") == "gemini-2.5-flash" for i in items)


# ---- Stats endpoint ----


class TestDocumentStats:
    @pytest.fixture()
    def stats_client(self, db_session):
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

    def test_stats_empty(self, stats_client):
        resp = stats_client.get("/api/v1/documents/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 0
        assert data["total_orders"] == 0

    def test_stats_with_data(self, stats_client, db_session):
        from lab_manager.models.document import Document, DocumentStatus

        db_session.add(
            Document(
                file_path="/tmp/s.png",
                file_name="s.png",
                status=DocumentStatus.approved,
            )
        )
        db_session.flush()
        resp = stats_client.get("/api/v1/documents/stats")
        assert resp.status_code == 200
        assert resp.json()["total_documents"] == 1
        assert "approved" in resp.json()["by_status"]
