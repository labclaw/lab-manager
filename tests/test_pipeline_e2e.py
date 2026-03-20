"""End-to-end pipeline tests: upload → extract → review → inventory → search → ask AI."""

from __future__ import annotations

import os
import struct
import zlib
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.config import get_settings
from lab_manager.intake.schemas import ExtractedDocument, ExtractedItem
from lab_manager.models.document import Document, DocumentStatus


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


SAMPLE_EXTRACTED = ExtractedDocument(
    vendor_name="Sigma-Aldrich",
    document_type="packing_list",
    po_number="PO-12345",
    order_number="SO-67890",
    order_date="2026-03-15",
    ship_date="2026-03-16",
    received_by="Dr. Smith",
    items=[
        ExtractedItem(
            catalog_number="A1234",
            description="Acetone, ACS reagent",
            quantity=2,
            unit="L",
            lot_number="SHBJ1234",
            unit_price=45.00,
        ),
        ExtractedItem(
            catalog_number="B5678",
            description="Sodium Chloride, BioReagent",
            quantity=500,
            unit="G",
            lot_number="MKBR5678",
            unit_price=28.50,
        ),
    ],
    confidence=0.92,
)


@pytest.fixture()
def upload_dir(tmp_path):
    d = tmp_path / "uploads"
    d.mkdir()
    os.environ["UPLOAD_DIR"] = str(d)
    get_settings.cache_clear()
    yield d
    get_settings.cache_clear()


@pytest.fixture()
def client(upload_dir, db_session):
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


class TestBackgroundExtraction:
    """Verify _run_extraction correctly processes uploaded documents."""

    def test_extraction_sets_fields(self, db_session, upload_dir):
        """Background extraction populates extracted_data, vendor_name, etc."""
        from lab_manager.api.routes.documents import _run_extraction

        # Create a document record pointing to a real PNG
        png = _make_png()
        dest = upload_dir / "test_extract.png"
        dest.write_bytes(png)

        doc = Document(
            file_path=str(dest),
            file_name="test_extract.png",
            status=DocumentStatus.processing,
        )
        db_session.add(doc)
        db_session.flush()
        db_session.refresh(doc)
        doc_id = doc.id

        # Mock OCR and extraction
        with (
            patch(
                "lab_manager.intake.ocr.extract_text_from_image",
                return_value="SIGMA-ALDRICH PACKING LIST PO-12345",
            ),
            patch(
                "lab_manager.intake.extractor.extract_from_text",
                return_value=SAMPLE_EXTRACTED,
            ),
            patch(
                "lab_manager.database.get_session_factory",
                return_value=lambda: db_session,
            ),
        ):
            _run_extraction(doc_id)

        db_session.expire_all()
        doc = db_session.get(Document, doc_id)
        assert doc.status == DocumentStatus.needs_review
        assert doc.vendor_name == "Sigma-Aldrich"
        assert doc.document_type == "packing_list"
        assert doc.extracted_data is not None
        assert doc.extracted_data["po_number"] == "PO-12345"
        assert len(doc.extracted_data["items"]) == 2
        assert doc.extraction_confidence == 0.92

    def test_extraction_handles_ocr_failure(self, db_session, upload_dir):
        """OCR failure sets status to needs_review with error note."""
        from lab_manager.api.routes.documents import _run_extraction

        png = _make_png()
        dest = upload_dir / "ocr_fail.png"
        dest.write_bytes(png)

        doc = Document(
            file_path=str(dest),
            file_name="ocr_fail.png",
            status=DocumentStatus.processing,
        )
        db_session.add(doc)
        db_session.flush()
        db_session.refresh(doc)
        doc_id = doc.id

        with (
            patch(
                "lab_manager.intake.ocr.extract_text_from_image",
                side_effect=RuntimeError("API timeout"),
            ),
            patch(
                "lab_manager.database.get_session_factory",
                return_value=lambda: db_session,
            ),
        ):
            _run_extraction(doc_id)

        db_session.expire_all()
        doc = db_session.get(Document, doc_id)
        assert doc.status == DocumentStatus.needs_review
        assert "OCR failed" in doc.review_notes

    def test_extraction_handles_empty_ocr(self, db_session, upload_dir):
        """Empty OCR text sets status to ocr_failed."""
        from lab_manager.api.routes.documents import _run_extraction

        png = _make_png()
        dest = upload_dir / "empty_ocr.png"
        dest.write_bytes(png)

        doc = Document(
            file_path=str(dest),
            file_name="empty_ocr.png",
            status=DocumentStatus.processing,
        )
        db_session.add(doc)
        db_session.flush()
        db_session.refresh(doc)
        doc_id = doc.id

        with (
            patch(
                "lab_manager.intake.ocr.extract_text_from_image",
                return_value="   ",
            ),
            patch(
                "lab_manager.database.get_session_factory",
                return_value=lambda: db_session,
            ),
        ):
            _run_extraction(doc_id)

        db_session.expire_all()
        doc = db_session.get(Document, doc_id)
        assert doc.status == DocumentStatus.ocr_failed
        assert "empty" in doc.review_notes.lower()


class TestApproveFlow:
    """Verify approve creates vendor, order, product, inventory records."""

    def _create_extracted_doc(self, db_session, upload_dir):
        """Helper: create a document with extracted data ready for review."""
        png = _make_png()
        dest = upload_dir / "approve_test.png"
        dest.write_bytes(png)

        doc = Document(
            file_path=str(dest),
            file_name="approve_test.png",
            status=DocumentStatus.needs_review,
            vendor_name="Sigma-Aldrich",
            document_type="packing_list",
            extracted_data=SAMPLE_EXTRACTED.model_dump(),
            extraction_confidence=0.92,
        )
        db_session.add(doc)
        db_session.commit()
        db_session.refresh(doc)
        return doc

    @patch("lab_manager.api.routes.documents._index_approved_doc")
    def test_approve_creates_vendor(self, mock_index, client, db_session, upload_dir):
        """Approving a doc upserts the vendor."""
        from lab_manager.models.vendor import Vendor

        doc = self._create_extracted_doc(db_session, upload_dir)

        resp = client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "approve", "reviewed_by": "admin"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        vendor = db_session.query(Vendor).filter(Vendor.name == "Sigma-Aldrich").first()
        assert vendor is not None

    @patch("lab_manager.api.routes.documents._index_approved_doc")
    def test_approve_creates_order_and_items(
        self, mock_index, client, db_session, upload_dir
    ):
        """Approving creates Order + OrderItems from extracted data."""
        from lab_manager.models.order import Order, OrderItem

        doc = self._create_extracted_doc(db_session, upload_dir)

        client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "approve", "reviewed_by": "admin"},
        )

        order = db_session.query(Order).filter(Order.document_id == doc.id).first()
        assert order is not None
        assert order.po_number == "PO-12345"

        items = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        assert len(items) == 2
        catalog_numbers = {i.catalog_number for i in items}
        assert "A1234" in catalog_numbers
        assert "B5678" in catalog_numbers

    @patch("lab_manager.api.routes.documents._index_approved_doc")
    def test_approve_creates_products(self, mock_index, client, db_session, upload_dir):
        """Approving upserts Product records for each line item."""
        from lab_manager.models.product import Product

        doc = self._create_extracted_doc(db_session, upload_dir)

        client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "approve", "reviewed_by": "admin"},
        )

        products = db_session.query(Product).all()
        assert len(products) >= 2
        names = {p.catalog_number for p in products}
        assert "A1234" in names
        assert "B5678" in names

    @patch("lab_manager.api.routes.documents._index_approved_doc")
    def test_approve_creates_inventory(
        self, mock_index, client, db_session, upload_dir
    ):
        """Approving creates InventoryItem for each line item with a product."""
        from lab_manager.models.inventory import InventoryItem

        doc = self._create_extracted_doc(db_session, upload_dir)

        client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "approve", "reviewed_by": "admin"},
        )

        inv_items = db_session.query(InventoryItem).all()
        assert len(inv_items) >= 2
        lots = {i.lot_number for i in inv_items}
        assert "SHBJ1234" in lots
        assert "MKBR5678" in lots

    @patch("lab_manager.api.routes.documents._index_approved_doc")
    def test_approve_triggers_indexing(
        self, mock_index, client, db_session, upload_dir
    ):
        """Approving triggers background search indexing."""
        doc = self._create_extracted_doc(db_session, upload_dir)

        client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "approve", "reviewed_by": "admin"},
        )

        mock_index.assert_called_once_with(doc.id)

    @patch("lab_manager.api.routes.documents._index_approved_doc")
    def test_reject_does_not_create_records(
        self, mock_index, client, db_session, upload_dir
    ):
        """Rejecting a doc does not create vendor/order/product/inventory."""
        from lab_manager.models.order import Order
        from lab_manager.models.vendor import Vendor

        doc = self._create_extracted_doc(db_session, upload_dir)

        resp = client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={
                "action": "reject",
                "reviewed_by": "admin",
                "review_notes": "bad scan",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        assert db_session.query(Vendor).count() == 0
        assert db_session.query(Order).count() == 0
        mock_index.assert_not_called()


class TestSearchIndexing:
    """Verify search indexing functions work correctly."""

    def test_index_document_record(self, db_session):
        """index_document_record calls Meilisearch add_documents."""
        doc = Document(
            id=1,
            file_path="/tmp/test.png",
            file_name="test.png",
            status="approved",
            vendor_name="TestVendor",
            document_type="invoice",
            ocr_text="Some OCR text",
        )

        mock_client = MagicMock()
        with patch(
            "lab_manager.services.search.get_search_client",
            return_value=mock_client,
        ):
            from lab_manager.services.search import index_document_record

            index_document_record(doc)

        mock_client.index.assert_called_with("documents")
        call_args = mock_client.index("documents").add_documents.call_args
        added_docs = call_args[0][0]
        assert len(added_docs) == 1
        assert added_docs[0]["id"] == 1
        assert added_docs[0]["vendor_name"] == "TestVendor"


class TestAskAIReturnsSQLResults:
    """Verify Ask AI returns SQL and raw_results."""

    def test_ask_returns_sql_and_results(self, client, db_session):
        """Ask AI endpoint returns sql query and raw results when SQL path succeeds."""
        mock_results = [
            {"id": 1, "name": "Acetone", "catalog_number": "A1234"},
            {"id": 2, "name": "Sodium Chloride", "catalog_number": "B5678"},
        ]

        with (
            patch(
                "lab_manager.services.rag._generate_sql",
                return_value="SELECT id, name, catalog_number FROM products",
            ),
            patch(
                "lab_manager.services.rag._execute_sql",
                return_value=mock_results,
            ),
            patch(
                "lab_manager.services.rag._format_answer",
                return_value="Found 2 products: Acetone and Sodium Chloride.",
            ),
            patch(
                "lab_manager.services.rag._get_client",
                return_value=MagicMock(),
            ),
        ):
            resp = client.post(
                "/api/v1/ask",
                json={"question": "What products do we have?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "sql"
        assert data["sql"] == "SELECT id, name, catalog_number FROM products"
        assert len(data["raw_results"]) == 2
        assert data["raw_results"][0]["name"] == "Acetone"
        assert data["row_count"] == 2
