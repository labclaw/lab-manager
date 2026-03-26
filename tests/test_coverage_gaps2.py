"""Additional tests targeting remaining coverage gaps."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# intake/ocr.py — extract_text_from_image (mocked)
# ---------------------------------------------------------------------------


class TestOcrExtract:
    @patch("lab_manager.intake.ocr.genai.Client")
    @patch("lab_manager.intake.ocr.get_settings")
    def test_extract_text_from_image(self, mock_settings, mock_client_cls, tmp_path):
        from lab_manager.intake.ocr import extract_text_from_image

        mock_settings.return_value.extraction_api_key = "key"
        mock_settings.return_value.extraction_model = "gemini-2.5-flash"

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "OCR output text"
        mock_client.models.generate_content.return_value = mock_response

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG fake image data")

        result = extract_text_from_image(img)
        assert result == "OCR output text"


# ---------------------------------------------------------------------------
# intake/pipeline.py — _find_vendor, process_document
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_find_vendor_exact(self, db_session):
        from lab_manager.intake.pipeline import _find_vendor
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="Sigma-Aldrich")
        db_session.add(v)
        db_session.flush()

        result = _find_vendor("Sigma-Aldrich", db_session)
        assert result is not None
        assert result.name == "Sigma-Aldrich"

    def test_find_vendor_case_insensitive(self, db_session):
        from lab_manager.intake.pipeline import _find_vendor
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="Sigma-Aldrich")
        db_session.add(v)
        db_session.flush()

        result = _find_vendor("sigma-aldrich", db_session)
        assert result is not None

    def test_find_vendor_partial(self, db_session):
        from lab_manager.intake.pipeline import _find_vendor
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="EMD Millipore Corporation")
        db_session.add(v)
        db_session.flush()

        result = _find_vendor("EMD Millipore", db_session)
        assert result is not None

    def test_find_vendor_alias(self, db_session):
        from lab_manager.intake.pipeline import _find_vendor
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="Thermo Fisher", aliases=["ThermoFisher", "Life Technologies"])
        db_session.add(v)
        db_session.flush()

        result = _find_vendor("Life Technologies", db_session)
        assert result is not None

    def test_find_vendor_not_found(self, db_session):
        from lab_manager.intake.pipeline import _find_vendor

        result = _find_vendor("NonexistentVendor12345", db_session)
        assert result is None

    @patch("lab_manager.intake.pipeline.extract_text_from_image")
    @patch("lab_manager.intake.pipeline.extract_from_text")
    def test_process_document_success(
        self, mock_extract, mock_ocr, db_session, tmp_path
    ):
        from lab_manager.intake.pipeline import process_document
        from lab_manager.intake.schemas import ExtractedDocument

        mock_ocr.return_value = "OCR text"
        mock_extract.return_value = ExtractedDocument(
            vendor_name="ACME",
            document_type="invoice",
            confidence=0.9,
        )

        img = tmp_path / "test.png"
        img.write_bytes(b"fake image data")

        doc = process_document(img, db_session)
        assert doc.status == "needs_review"
        assert doc.vendor_name == "ACME"

    @patch("lab_manager.intake.pipeline.extract_text_from_image")
    def test_process_document_ocr_fails(self, mock_ocr, db_session, tmp_path):
        from lab_manager.intake.pipeline import process_document

        mock_ocr.side_effect = Exception("OCR error")

        img = tmp_path / "test.png"
        img.write_bytes(b"fake image data")

        doc = process_document(img, db_session)
        assert "OCR failed" in (doc.review_notes or "")

    @patch("lab_manager.intake.pipeline.extract_text_from_image")
    def test_process_document_empty_ocr(self, mock_ocr, db_session, tmp_path):
        from lab_manager.intake.pipeline import process_document

        mock_ocr.return_value = ""

        img = tmp_path / "test.png"
        img.write_bytes(b"fake image data")

        doc = process_document(img, db_session)
        assert doc.status == "ocr_failed"

    @patch("lab_manager.intake.pipeline.extract_text_from_image")
    @patch("lab_manager.intake.pipeline.extract_from_text")
    def test_process_document_extraction_fails(
        self, mock_extract, mock_ocr, db_session, tmp_path
    ):
        from lab_manager.intake.pipeline import process_document

        mock_ocr.return_value = "OCR text"
        mock_extract.side_effect = Exception("Extraction error")

        img = tmp_path / "test.png"
        img.write_bytes(b"fake image data")

        doc = process_document(img, db_session)
        assert "Extraction failed" in (doc.review_notes or "")

    @patch("lab_manager.intake.pipeline.extract_text_from_image")
    @patch("lab_manager.intake.pipeline.extract_from_text")
    def test_process_document_duplicate(
        self, mock_extract, mock_ocr, db_session, tmp_path
    ):
        from lab_manager.intake.pipeline import process_document
        from lab_manager.intake.schemas import ExtractedDocument

        mock_ocr.return_value = "text"
        mock_extract.return_value = ExtractedDocument(
            vendor_name="A", document_type="invoice", confidence=0.5
        )

        img = tmp_path / "doc.png"
        img.write_bytes(b"data")

        process_document(img, db_session)
        # Second call creates a hash-suffixed variant (same content, file exists)
        doc2 = process_document(img, db_session)
        # Pipeline dedupes by dest_name: second call finds hash-suffixed file
        # already in DB, so returns the same record
        assert doc2 is not None
        assert doc2.file_name is not None


# ---------------------------------------------------------------------------
# services/rag.py — _generate_sql, _execute_sql, _format_answer
# ---------------------------------------------------------------------------


class TestRagInternals:
    @patch("lab_manager.services.rag.create_completion")
    def test_generate_sql_strips_markdown(self, mock_completion):
        from lab_manager.services.rag import _generate_sql

        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "```sql\nSELECT * FROM vendors\n```"
        mock_completion.return_value = mock_resp

        sql = _generate_sql("List vendors")
        assert "SELECT" in sql
        assert "```" not in sql

    @patch("lab_manager.services.rag.create_completion")
    def test_format_answer(self, mock_completion):
        from lab_manager.services.rag import _format_answer

        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "There are 5 vendors in the database."
        mock_completion.return_value = mock_resp

        result = _format_answer("How many?", "SELECT 1", [{"c": 5}])
        assert "5 vendors" in result

    @patch("lab_manager.services.rag.create_completion")
    def test_generate_sql_openai_compatible_client(self, mock_completion):
        from lab_manager.services.rag import _generate_sql

        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "SELECT * FROM vendors"
        mock_completion.return_value = mock_resp

        sql = _generate_sql("List vendors")
        assert sql == "SELECT * FROM vendors"

    @patch("lab_manager.services.rag.create_completion")
    def test_format_answer_openai_compatible_client(self, mock_completion):
        from lab_manager.services.rag import _format_answer

        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "There are 2 matching orders."
        mock_completion.return_value = mock_resp

        result = _format_answer("How many?", "SELECT 1", [{"c": 2}])
        assert "2 matching orders" in result

    def test_get_model(self):
        from lab_manager.services.rag import _get_model

        result = _get_model()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# services/search.py — batch handling (>500 items)
# ---------------------------------------------------------------------------


class TestSearchBatching:
    @patch("lab_manager.services.search.get_search_client")
    @patch("lab_manager.services.search._BATCH_SIZE", 2)
    def test_sync_vendors_batching(self, mock_get_client, db_session):
        from lab_manager.services.search import sync_vendors
        from lab_manager.models.vendor import Vendor

        for i in range(5):
            db_session.add(Vendor(name=f"BatchV{i}"))
        db_session.flush()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count = sync_vendors(db_session)
        assert count == 5
        # Should have called add_documents multiple times due to batching
        assert mock_client.index.return_value.add_documents.call_count >= 2


# ---------------------------------------------------------------------------
# services/inventory.py — receive_items, stock queries, etc.
# ---------------------------------------------------------------------------


class TestInventoryServiceIntegration:
    def _create_order_with_items(self, db_session):
        """Helper to create vendor + product + order + order_item."""
        from lab_manager.models.order import Order, OrderItem
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="TestVendor")
        db_session.add(v)
        db_session.flush()

        p = Product(catalog_number="CAT-1", name="Test Product", vendor_id=v.id)
        db_session.add(p)
        db_session.flush()

        o = Order(vendor_id=v.id, po_number="PO-001", status="pending")
        db_session.add(o)
        db_session.flush()

        oi = OrderItem(
            order_id=o.id,
            catalog_number="CAT-1",
            quantity=5,
            unit="EA",
            lot_number="LOT-1",
            product_id=p.id,
        )
        db_session.add(oi)
        db_session.flush()

        return v, p, o, oi

    def test_receive_items(self, db_session):
        from lab_manager.services.inventory import receive_items

        v, p, o, oi = self._create_order_with_items(db_session)

        items = receive_items(
            order_id=o.id,
            items_received=[
                {
                    "order_item_id": oi.id,
                    "quantity": 5,
                    "lot_number": "LOT-1",
                }
            ],
            location_id=None,
            received_by="tester",
            db=db_session,
        )
        assert len(items) == 1
        assert items[0].quantity_on_hand == 5

    def test_receive_items_order_not_found(self, db_session):
        from lab_manager.exceptions import NotFoundError
        from lab_manager.services.inventory import receive_items

        with pytest.raises(NotFoundError):
            receive_items(999, [], 1, "tester", db_session)

    def test_receive_items_wrong_order(self, db_session):
        from lab_manager.exceptions import ValidationError
        from lab_manager.services.inventory import receive_items

        v, p, o, oi = self._create_order_with_items(db_session)

        # Create a second order
        from lab_manager.models.order import Order

        o2 = Order(vendor_id=v.id, po_number="PO-002", status="pending")
        db_session.add(o2)
        db_session.flush()

        with pytest.raises(ValidationError, match="belongs to order"):
            receive_items(
                order_id=o2.id,
                items_received=[{"order_item_id": oi.id, "quantity": 1}],
                location_id=None,
                received_by="tester",
                db=db_session,
            )

    def test_get_stock_level(self, db_session):
        from lab_manager.services.inventory import get_stock_level, receive_items

        v, p, o, oi = self._create_order_with_items(db_session)
        receive_items(
            o.id, [{"order_item_id": oi.id, "quantity": 5}], None, "t", db_session
        )

        result = get_stock_level(p.id, db_session)
        assert result["total_quantity"] >= 5

    def test_get_low_stock(self, db_session):
        from lab_manager.services.inventory import get_low_stock

        result = get_low_stock(db_session)
        assert isinstance(result, list)

    def test_get_expiring(self, db_session):
        from lab_manager.services.inventory import get_expiring

        result = get_expiring(db_session, days=30)
        assert isinstance(result, list)

    def test_get_consumption_history(self, db_session):
        from lab_manager.services.inventory import get_consumption_history

        result = get_consumption_history(999, db_session)
        assert isinstance(result, list)

    def test_get_item_history(self, db_session):
        from lab_manager.services.inventory import get_item_history

        result = get_item_history(999, db_session)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# api/admin.py — admin auth backend
# ---------------------------------------------------------------------------


class TestAdminAuth:
    @patch("lab_manager.config.get_settings")
    def test_make_auth_backend(self, mock_settings):
        from lab_manager.api.admin import _make_auth_backend

        mock_settings.return_value.admin_secret_key = "test-secret"
        mock_settings.return_value.api_key = ""
        mock_settings.return_value.auth_enabled = False
        mock_settings.return_value.admin_password = ""

        backend = _make_auth_backend()
        assert backend is not None

    @patch("lab_manager.config.get_settings")
    def test_make_auth_backend_no_secret(self, mock_settings):
        from lab_manager.api.admin import _make_auth_backend

        mock_settings.return_value.admin_secret_key = ""
        mock_settings.return_value.api_key = ""
        mock_settings.return_value.auth_enabled = False
        mock_settings.return_value.admin_password = ""

        backend = _make_auth_backend()
        assert backend is not None


# ---------------------------------------------------------------------------
# api/app.py — health check paths, auth/me, login, logout
# ---------------------------------------------------------------------------


class TestAppEndpoints:
    def test_health_degraded_no_pg(self, client):
        """Health check should report PostgreSQL status."""
        resp = client.get("/api/health")
        # With SQLite, PG will be "error" if get_engine fails
        assert resp.status_code in (200, 503)

    def test_auth_me_no_auth(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["name"] == "Lab User"

    def test_logout(self, client):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200

    def test_root_returns_html(self, client):
        # Root endpoint serves static HTML, but may 404 if no index.html
        resp = client.get("/")
        assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# api/routes/documents.py — review, upload
# ---------------------------------------------------------------------------


class TestDocumentReview:
    def test_review_approve(self, client, db_session):
        from lab_manager.models.document import Document

        doc = Document(
            file_path="/tmp/test.pdf",
            file_name="test-review.pdf",
            status="needs_review",
            extracted_data={
                "vendor_name": "Test Vendor",
                "items": [{"catalog_number": "C1", "quantity": 1}],
            },
        )
        db_session.add(doc)
        db_session.flush()

        resp = client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "approve", "reviewed_by": "tester"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_review_reject(self, client, db_session):
        from lab_manager.models.document import Document

        doc = Document(
            file_path="/tmp/test2.pdf",
            file_name="test-reject.pdf",
            status="needs_review",
        )
        db_session.add(doc)
        db_session.flush()

        resp = client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "reject", "reviewed_by": "tester", "review_notes": "bad"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_upload_bad_type(self, client):
        import io

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_success(self, client):
        import io

        resp = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.png", io.BytesIO(b"\x89PNGfake"), "image/png")},
        )
        assert resp.status_code == 201

    def test_upload_too_large(self, client):
        import io

        # Create file larger than 50MB limit
        with patch("lab_manager.api.routes.documents._MAX_UPLOAD_BYTES", 10):
            resp = client.post(
                "/api/v1/documents/upload",
                files={
                    "file": (
                        "big.png",
                        io.BytesIO(b"\x89PNG" + b"x" * 20),
                        "image/png",
                    )
                },
            )
            assert resp.status_code == 413


# ---------------------------------------------------------------------------
# api/routes/inventory.py — low-stock, expiring endpoints
# ---------------------------------------------------------------------------


class TestInventoryEndpoints:
    def test_low_stock(self, client):
        resp = client.get("/api/v1/inventory/low-stock")
        assert resp.status_code == 200

    def test_expiring(self, client):
        resp = client.get("/api/v1/inventory/expiring?days=30")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# api/routes/products.py — CAS validation, product with duplicate
# ---------------------------------------------------------------------------


class TestProductEndpoints:
    def test_create_with_invalid_cas(self, client, db_session):
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="CAS-V")
        db_session.add(v)
        db_session.flush()

        resp = client.post(
            "/api/v1/products/",
            json={
                "catalog_number": "CAS-TEST",
                "name": "CAS Product",
                "vendor_id": v.id,
                "cas_number": "invalid",
            },
        )
        assert resp.status_code == 422

    def test_create_with_valid_cas(self, client, db_session):
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="CAS-V2")
        db_session.add(v)
        db_session.flush()

        resp = client.post(
            "/api/v1/products/",
            json={
                "catalog_number": "CAS-TEST2",
                "name": "CAS Product",
                "vendor_id": v.id,
                "cas_number": "7732-18-5",
            },
        )
        assert resp.status_code == 201

    def test_cas_empty_string(self):
        from lab_manager.api.routes.products import _validate_cas

        assert _validate_cas("") is None

    def test_cas_none(self):
        from lab_manager.api.routes.products import _validate_cas

        assert _validate_cas(None) is None


# ---------------------------------------------------------------------------
# intake/providers/__init__.py — edge case: parse_json_response fallback fail
# ---------------------------------------------------------------------------


class TestParseJsonEdgeCases:
    def test_json_with_braces_but_invalid(self):
        from lab_manager.intake.providers import parse_json_response

        result = parse_json_response("text {not valid json} more text")
        assert result is None


# ---------------------------------------------------------------------------
# services/analytics.py — spending_by_month, vendor_summary not_found
# ---------------------------------------------------------------------------


class TestAnalyticsGaps:
    def test_spending_by_month(self, db_session):
        from lab_manager.services.analytics import spending_by_month

        result = spending_by_month(db_session, months=12)
        assert isinstance(result, list)

    def test_vendor_summary_not_found(self, db_session):
        from lab_manager.services.analytics import vendor_summary

        result = vendor_summary(db_session, 99999)
        assert result is None

    def test_document_processing_stats(self, db_session):
        from lab_manager.services.analytics import document_processing_stats

        result = document_processing_stats(db_session)
        assert "total_documents" in result


# ---------------------------------------------------------------------------
# intake/consensus.py — edge cases
# ---------------------------------------------------------------------------


class TestConsensusGaps:
    def test_consensus_merge_all_agree(self):
        from lab_manager.intake.consensus import consensus_merge

        extractions = {
            "model_a": {"vendor_name": "A", "po_number": "PO1"},
            "model_b": {"vendor_name": "A", "po_number": "PO1"},
            "model_c": {"vendor_name": "A", "po_number": "PO1"},
        }
        merged = consensus_merge(extractions)
        assert merged["vendor_name"] == "A"
        assert merged["_needs_human"] is False

    def test_consensus_merge_majority(self):
        from lab_manager.intake.consensus import consensus_merge

        extractions = {
            "model_a": {"vendor_name": "A"},
            "model_b": {"vendor_name": "A"},
            "model_c": {"vendor_name": "B"},
        }
        merged = consensus_merge(extractions)
        assert merged["vendor_name"] == "A"

    def test_consensus_merge_all_none(self):
        from lab_manager.intake.consensus import consensus_merge

        extractions = {"a": None, "b": None}
        merged = consensus_merge(extractions)
        assert merged["_error"] == "all_models_failed"
        assert merged["_needs_human"] is True

    def test_consensus_merge_single_model(self):
        from lab_manager.intake.consensus import consensus_merge

        extractions = {
            "only_model": {"vendor_name": "X"},
            "failed": None,
        }
        merged = consensus_merge(extractions)
        assert merged["vendor_name"] == "X"
        assert merged["_needs_human"] is True
        assert merged["_consensus"]["method"] == "single_model"

    def test_consensus_merge_all_disagree(self):
        from lab_manager.intake.consensus import consensus_merge

        extractions = {
            "model_a": {"vendor_name": "A"},
            "model_b": {"vendor_name": "B"},
            "model_c": {"vendor_name": "C"},
        }
        merged = consensus_merge(extractions)
        assert merged["_needs_human"] is True
        assert merged["_consensus"]["vendor_name"]["agreement"] == "none"

    def test_extract_parallel(self):
        from lab_manager.intake.consensus import extract_parallel
        from lab_manager.intake.providers import VLMProvider

        class FakeProvider(VLMProvider):
            name = "fake"

            def extract(self, image_path, prompt):
                return {"vendor_name": "Test"}

            def extract_from_image(self, image_path, prompt):
                return '{"vendor_name": "Test"}'

        results = extract_parallel([FakeProvider()], "fake.png", "test prompt")
        assert "fake" in results
        assert results["fake"]["vendor_name"] == "Test"

    @patch("lab_manager.intake.consensus.extract_parallel")
    def test_cross_model_review_no_reviews(self, mock_parallel):
        from lab_manager.intake.consensus import cross_model_review

        mock_parallel.return_value = {}  # No valid reviews
        merged = {"vendor_name": "A", "_consensus": {}, "_needs_human": False}
        result = cross_model_review([], "img.png", merged)
        assert result["vendor_name"] == "A"

    @patch("lab_manager.intake.consensus.extract_parallel")
    def test_cross_model_review_with_corrections(self, mock_parallel):
        from lab_manager.intake.consensus import cross_model_review

        # Two reviewers agree on a correction
        mock_parallel.return_value = {
            "reviewer_a": {"vendor_name": "Corrected"},
            "reviewer_b": {"vendor_name": "Corrected"},
        }
        merged = {"vendor_name": "Wrong", "_consensus": {}, "_needs_human": False}
        result = cross_model_review([], "img.png", merged)
        assert result["vendor_name"] == "Corrected"
        assert "vendor_name" in result["_review_round"]["corrections_applied"]


# ---------------------------------------------------------------------------
# intake/validator.py — edge cases
# ---------------------------------------------------------------------------


class TestValidatorGaps:
    def test_validate_empty_items(self):
        from lab_manager.intake.validator import validate

        result = validate(
            {
                "vendor_name": "Test",
                "document_type": "invoice",
                "items": [],
            }
        )
        assert isinstance(result, list)
        assert len(result) == 0  # Valid data, no issues

    def test_validate_with_items(self):
        from lab_manager.intake.validator import validate

        result = validate(
            {
                "vendor_name": "Test Vendor",
                "document_type": "packing_list",
                "items": [
                    {"catalog_number": "ABC-123", "quantity": 5},
                ],
            }
        )
        assert isinstance(result, list)

    def test_validate_vendor_too_long(self):
        from lab_manager.intake.validator import validate

        result = validate({"vendor_name": "X" * 101})
        assert any(i["issue"] == "too_long" for i in result)

    def test_validate_vendor_looks_like_address(self):
        from lab_manager.intake.validator import validate

        result = validate({"vendor_name": "123 Main Street Corp"})
        assert any(i["issue"] == "looks_like_address" for i in result)

    def test_validate_vendor_template_text(self):
        from lab_manager.intake.validator import validate

        result = validate({"vendor_name": "Provider: Some Organization"})
        assert any(i["issue"] == "template_text" for i in result)

    def test_validate_invalid_doc_type(self):
        from lab_manager.intake.validator import validate

        result = validate({"document_type": "invalid_type"})
        assert any("invalid" in i["issue"] for i in result)

    def test_validate_negative_qty(self):
        from lab_manager.intake.validator import validate

        result = validate({"items": [{"quantity": -1}]})
        assert any(i["issue"] == "negative_quantity" for i in result)

    def test_validate_zero_qty(self):
        from lab_manager.intake.validator import validate

        result = validate({"items": [{"quantity": 0}]})
        assert any(i["issue"] == "zero" for i in result)

    def test_validate_large_qty(self):
        from lab_manager.intake.validator import validate

        result = validate({"items": [{"quantity": 10001}]})
        assert any("large" in i["issue"] for i in result)

    def test_validate_vcat_lot(self):
        from lab_manager.intake.validator import validate

        result = validate({"items": [{"lot_number": "VCAT12345"}]})
        assert any(i["issue"] == "vcat_code_not_lot" for i in result)

    def test_validate_unusual_date(self):
        from lab_manager.intake.validator import validate

        result = validate({"order_date": "2018-01-01"})
        assert any("unusual_year" in i["issue"] for i in result)

    def test_validate_invalid_date(self):
        from lab_manager.intake.validator import validate

        result = validate({"order_date": "not-a-date"})
        assert any(i["issue"] == "invalid_format" for i in result)
