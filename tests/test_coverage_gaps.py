"""Tests targeting specific coverage gaps across the codebase."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.serialization import serialize_value


# ---------------------------------------------------------------------------
# services/serialization.py — numpy-like types, Decimal
# ---------------------------------------------------------------------------


class TestSerializeValue:
    def test_numpy_int64(self):
        FakeInt64 = type(
            "int64",
            (),
            {
                "__int__": lambda self: self._v,
                "__init__": lambda self, v: setattr(self, "_v", v),
            },
        )
        obj = FakeInt64(42)
        assert serialize_value(obj) == 42

    def test_numpy_float32(self):
        # Create a type whose __name__ is "float32" via metaclass
        FakeFloat32 = type(
            "float32",
            (),
            {
                "__float__": lambda self: self._v,
                "__init__": lambda self, v: setattr(self, "_v", v),
            },
        )
        obj = FakeFloat32(3.14)
        assert serialize_value(obj) == pytest.approx(3.14)

    def test_unknown_type_to_str(self):
        class Custom:
            def __str__(self):
                return "custom-str"

        assert serialize_value(Custom()) == "custom-str"

    def test_decimal(self):
        assert serialize_value(Decimal("1.5")) == 1.5

    def test_date(self):
        assert serialize_value(date(2026, 1, 15)) == "2026-01-15"

    def test_datetime(self):
        dt = datetime(2026, 1, 15, 10, 30, 0)
        assert "2026-01-15" in serialize_value(dt)

    def test_list_passthrough(self):
        assert serialize_value([1, 2]) == [1, 2]

    def test_dict_passthrough(self):
        assert serialize_value({"k": "v"}) == {"k": "v"}


# ---------------------------------------------------------------------------
# intake/ocr.py — _get_mime_type
# ---------------------------------------------------------------------------


class TestOcrMimeType:
    def test_known_types(self):
        from lab_manager.intake.ocr import _get_mime_type

        assert _get_mime_type("test.jpg") == "image/jpeg"
        assert _get_mime_type("test.jpeg") == "image/jpeg"
        assert _get_mime_type("test.png") == "image/png"
        assert _get_mime_type("test.tif") == "image/tiff"
        assert _get_mime_type("test.tiff") == "image/tiff"
        assert _get_mime_type("test.bmp") == "image/bmp"
        assert _get_mime_type("test.webp") == "image/webp"
        assert _get_mime_type("test.pdf") == "application/pdf"
        assert _get_mime_type("test.gif") == "image/gif"

    def test_unknown_type(self):
        from lab_manager.intake.ocr import _get_mime_type

        assert _get_mime_type("test.xyz") == "image/xyz"

    def test_no_extension(self):
        from lab_manager.intake.ocr import _get_mime_type

        result = _get_mime_type("noext")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# intake/extractor.py — _call_llm (mocked)
# ---------------------------------------------------------------------------


class TestExtractor:
    @patch("lab_manager.intake.extractor.genai.Client")
    @patch("lab_manager.intake.extractor.instructor.from_genai")
    @patch("lab_manager.intake.extractor.get_settings")
    def test_call_llm(self, mock_settings, mock_from_genai, mock_client_cls):
        from lab_manager.intake.extractor import _call_llm
        from lab_manager.intake.schemas import ExtractedDocument

        mock_settings.return_value.extraction_api_key = "test-key"
        mock_settings.return_value.extraction_model = "gemini-2.5-flash"

        mock_instructor_client = MagicMock()
        mock_from_genai.return_value = mock_instructor_client
        mock_result = MagicMock(spec=ExtractedDocument)
        mock_instructor_client.chat.completions.create.return_value = mock_result

        result = _call_llm("some ocr text")
        assert result is mock_result

    @patch("lab_manager.intake.extractor.genai.Client")
    @patch("lab_manager.intake.extractor.instructor.from_genai")
    @patch("lab_manager.intake.extractor.get_settings")
    def test_extract_from_text(self, mock_settings, mock_from_genai, mock_client_cls):
        from lab_manager.intake.extractor import extract_from_text
        from lab_manager.intake.schemas import ExtractedDocument

        mock_settings.return_value.extraction_api_key = "test-key"
        mock_settings.return_value.extraction_model = "gemini-2.5-flash"

        mock_instructor_client = MagicMock()
        mock_from_genai.return_value = mock_instructor_client
        mock_result = MagicMock(spec=ExtractedDocument)
        mock_instructor_client.chat.completions.create.return_value = mock_result

        result = extract_from_text("ocr text")
        assert result is mock_result


# ---------------------------------------------------------------------------
# intake/schemas.py — invalid document_type
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_invalid_document_type(self):
        from lab_manager.intake.schemas import ExtractedDocument

        with pytest.raises(Exception):
            ExtractedDocument(
                vendor_name="Test",
                document_type="invalid_type_xyz",
            )


# ---------------------------------------------------------------------------
# api/pagination.py — apply_sort with invalid column
# ---------------------------------------------------------------------------


class TestPagination:
    def test_apply_sort_invalid_column(self, db_session):
        from lab_manager.api.pagination import apply_sort
        from lab_manager.models.vendor import Vendor

        q = db_session.query(Vendor)
        result = apply_sort(q, Vendor, "nonexistent", "asc", {"id", "name"})
        # Should fall back to "id"
        assert result is not None

    def test_paginate_with_more_pages(self, db_session):
        """Test paginate when there are more items than page_size."""
        from sqlalchemy import select

        from lab_manager.api.pagination import paginate
        from lab_manager.models.vendor import Vendor

        for i in range(5):
            db_session.add(Vendor(name=f"V{i}"))
        db_session.flush()

        q = select(Vendor)
        result = paginate(q, db_session, page=1, page_size=2)
        assert result["page_size"] == 2
        assert len(result["items"]) == 2
        assert result["total"] >= 5


# ---------------------------------------------------------------------------
# api/deps.py — verify_api_key
# ---------------------------------------------------------------------------


class TestDeps:
    def test_verify_api_key_auth_disabled(self):
        from lab_manager.api.deps import verify_api_key

        with patch("lab_manager.api.deps.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = False
            # Should not raise
            verify_api_key(x_api_key=None)

    def test_verify_api_key_no_key_configured(self):
        from fastapi import HTTPException

        from lab_manager.api.deps import verify_api_key

        with patch("lab_manager.api.deps.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True
            mock_settings.return_value.api_key = ""
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(x_api_key="test")
            assert exc_info.value.status_code == 500

    def test_verify_api_key_wrong_key(self):
        from fastapi import HTTPException

        from lab_manager.api.deps import verify_api_key

        with patch("lab_manager.api.deps.get_settings") as mock_settings:
            mock_settings.return_value.auth_enabled = True
            mock_settings.return_value.api_key = "correct-key"
            with pytest.raises(HTTPException) as exc_info:
                verify_api_key(x_api_key="wrong-key")
            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# models/audit.py — log_change
# ---------------------------------------------------------------------------


class TestAuditModel:
    def test_log_change(self, db_session):
        from lab_manager.models.audit import log_change

        log_change(
            db_session,
            table_name="vendors",
            record_id=1,
            action="create",
            changed_by="test",
            changes={"name": {"old": None, "new": "Test"}},
        )
        db_session.flush()
        from lab_manager.models.audit import AuditLog

        logs = db_session.query(AuditLog).all()
        assert len(logs) >= 1


# ---------------------------------------------------------------------------
# services/rag.py — _validate_sql, _serialize_rows, _fallback_search, ask
# ---------------------------------------------------------------------------


class TestRagService:
    def test_validate_sql_valid(self):
        from lab_manager.services.rag import _validate_sql

        sql = _validate_sql("SELECT * FROM vendors LIMIT 10")
        assert "SELECT" in sql

    def test_validate_sql_with_cte(self):
        from lab_manager.services.rag import _validate_sql

        sql = _validate_sql(
            "WITH v AS (SELECT id FROM vendors) SELECT * FROM vendors LIMIT 10"
        )
        assert "WITH" in sql

    def test_validate_sql_rejects_insert(self):
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="must start with SELECT"):
            _validate_sql("INSERT INTO vendors (name) VALUES ('x')")

    def test_validate_sql_rejects_stacked(self):
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="Stacked"):
            _validate_sql("SELECT 1; DROP TABLE vendors")

    def test_validate_sql_rejects_comments(self):
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="comments"):
            _validate_sql("SELECT * FROM vendors -- drop table")

    def test_validate_sql_rejects_block_comments(self):
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="comments"):
            _validate_sql("SELECT * /* inject */ FROM vendors")

    def test_validate_sql_rejects_bad_start(self):
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="must start with SELECT"):
            _validate_sql("UPDATE vendors SET name='x'")

    def test_validate_sql_rejects_forbidden_table(self):
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="forbidden"):
            _validate_sql("SELECT * FROM pg_shadow")

    def test_validate_sql_rejects_unknown_table(self):
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="not allowed"):
            _validate_sql("SELECT * FROM some_unknown_table")

    def test_validate_sql_rejects_password_hash(self):
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="forbidden columns"):
            _validate_sql("SELECT password_hash FROM vendors")

    def test_serialize_rows(self):
        from lab_manager.services.rag import _serialize_rows

        rows = [{"d": date(2026, 1, 1), "n": 42}]
        result = _serialize_rows(rows)
        assert result[0]["d"] == "2026-01-01"
        assert result[0]["n"] == 42

    def test_ask_empty_question(self, db_session):
        from lab_manager.services.rag import ask

        result = ask("", db_session)
        assert result["answer"] == "Please provide a question."

    def test_ask_whitespace_question(self, db_session):
        from lab_manager.services.rag import ask

        result = ask("   ", db_session)
        assert result["answer"] == "Please provide a question."

    @patch("lab_manager.services.rag._get_client")
    def test_ask_no_api_key(self, mock_get_client, db_session):
        from lab_manager.services.rag import ask

        mock_get_client.side_effect = RuntimeError("No API key")
        with patch("lab_manager.services.rag._fallback_search") as mock_fb:
            mock_fb.return_value = {
                "question": "test",
                "answer": "fallback",
                "raw_results": [],
                "source": "search",
            }
            result = ask("How many products?", db_session)
            assert result["source"] == "search"

    @patch("lab_manager.services.rag._get_client")
    def test_ask_sql_gen_fails(self, mock_get_client, db_session):
        from lab_manager.services.rag import ask

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        with patch("lab_manager.services.rag._generate_sql") as mock_gen:
            mock_gen.side_effect = ValueError("bad sql")
            with patch("lab_manager.services.rag._fallback_search") as mock_fb:
                mock_fb.return_value = {
                    "question": "q",
                    "answer": "f",
                    "raw_results": [],
                    "source": "search",
                }
                result = ask("How many?", db_session)
                assert result["source"] == "search"

    @patch("lab_manager.services.rag._get_client")
    def test_ask_sql_exec_fails(self, mock_get_client, db_session):
        from lab_manager.services.rag import ask

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        with (
            patch("lab_manager.services.rag._generate_sql") as mock_gen,
            patch("lab_manager.services.rag._execute_sql") as mock_exec,
            patch("lab_manager.services.rag._fallback_search") as mock_fb,
        ):
            mock_gen.return_value = "SELECT 1"
            mock_exec.side_effect = Exception("sql error")
            mock_fb.return_value = {
                "question": "q",
                "answer": "f",
                "raw_results": [],
                "source": "search",
            }
            result = ask("How many?", db_session)
            assert result["source"] == "search"

    @patch("lab_manager.services.rag._get_client")
    def test_ask_format_fails(self, mock_get_client, db_session):
        from lab_manager.services.rag import ask

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        with (
            patch("lab_manager.services.rag._generate_sql") as mock_gen,
            patch("lab_manager.services.rag._execute_sql") as mock_exec,
            patch("lab_manager.services.rag._format_answer") as mock_fmt,
        ):
            mock_gen.return_value = "SELECT 1"
            mock_exec.return_value = [{"col": 1}]
            mock_fmt.side_effect = Exception("format error")
            result = ask("How many?", db_session)
            assert "formatting failed" in result["answer"]
            assert result["source"] == "sql"

    @patch("lab_manager.services.rag._get_client")
    def test_ask_success(self, mock_get_client, db_session):
        from lab_manager.services.rag import ask

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        with (
            patch("lab_manager.services.rag._generate_sql") as mock_gen,
            patch("lab_manager.services.rag._execute_sql") as mock_exec,
            patch("lab_manager.services.rag._format_answer") as mock_fmt,
        ):
            mock_gen.return_value = "SELECT count(*) FROM vendors"
            mock_exec.return_value = [{"count": 5}]
            mock_fmt.return_value = "There are 5 vendors."
            result = ask("How many vendors?", db_session)
            assert result["answer"] == "There are 5 vendors."
            assert result["source"] == "sql"

    def test_ask_truncates_long_question(self, db_session):
        from lab_manager.services.rag import MAX_QUESTION_LENGTH, ask

        long_q = "x" * (MAX_QUESTION_LENGTH + 500)
        with patch("lab_manager.services.rag._get_client") as mock_gc:
            mock_gc.side_effect = RuntimeError("no key")
            with patch("lab_manager.services.rag._fallback_search") as mock_fb:
                mock_fb.return_value = {
                    "question": long_q,
                    "answer": "f",
                    "raw_results": [],
                    "source": "search",
                }
                ask(long_q, db_session)
                # Should have been truncated before calling fallback
                call_q = mock_fb.call_args[0][0]
                assert len(call_q) <= MAX_QUESTION_LENGTH

    def test_fallback_search_no_hits(self):
        from lab_manager.services.rag import _fallback_search

        with patch("lab_manager.services.search.get_search_client") as mock_gc:
            mock_client = MagicMock()
            mock_gc.return_value = mock_client
            mock_client.index.return_value.search.return_value = {"hits": []}
            result = _fallback_search("test query")
            assert "No results" in result["answer"]

    def test_fallback_search_with_hits(self):
        from lab_manager.services.rag import _fallback_search

        with patch("lab_manager.services.search.get_search_client") as mock_gc:
            mock_client = MagicMock()
            mock_gc.return_value = mock_client
            mock_client.index.return_value.search.return_value = {"hits": [{"id": 1}]}
            result = _fallback_search("test query")
            assert "1 results" in result["answer"]

    def test_fallback_search_exception(self):
        from lab_manager.services.rag import _fallback_search

        with patch("lab_manager.services.search.get_search_client") as mock_gc:
            mock_gc.side_effect = Exception("fail")
            result = _fallback_search("test query")
            assert "unavailable" in result["answer"]


# ---------------------------------------------------------------------------
# api/routes/search.py — search + suggest endpoints
# ---------------------------------------------------------------------------


class TestSearchRoutes:
    def test_search_specific_index(self, client):
        with patch("lab_manager.services.search.get_search_client") as mock_gc:
            mock_client = MagicMock()
            mock_gc.return_value = mock_client
            mock_client.index.return_value.search.return_value = {"hits": [{"id": 1}]}
            resp = client.get("/api/v1/search/?q=test&index=products")
            assert resp.status_code == 200
            data = resp.json()
            assert data["index"] == "products"

    def test_search_all_indexes(self, client):
        with patch("lab_manager.services.search.get_search_client") as mock_gc:
            mock_client = MagicMock()
            mock_gc.return_value = mock_client
            mock_client.index.return_value.search.return_value = {"hits": []}
            resp = client.get("/api/v1/search/?q=test")
            assert resp.status_code == 200

    def test_suggest_endpoint(self, client):
        with patch("lab_manager.services.search.get_search_client") as mock_gc:
            mock_client = MagicMock()
            mock_gc.return_value = mock_client
            mock_client.index.return_value.search.return_value = {"hits": []}
            resp = client.get("/api/v1/search/suggest?q=test")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# api/routes/ask.py — ask endpoints
# ---------------------------------------------------------------------------


class TestAskRoutes:
    @patch("lab_manager.api.routes.ask.ask")
    def test_ask_post(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "q",
            "answer": "a",
            "raw_results": [],
            "row_count": 3,
            "source": "sql",
        }
        resp = client.post("/api/v1/ask", json={"question": "How many?"})
        assert resp.status_code == 200
        assert resp.json()["row_count"] == 3

    @patch("lab_manager.api.routes.ask.ask")
    def test_ask_get(self, mock_ask, client):
        mock_ask.return_value = {
            "question": "q",
            "answer": "a",
            "raw_results": [],
            "row_count": 7,
            "source": "sql",
        }
        resp = client.get("/api/v1/ask?q=How+many")
        assert resp.status_code == 200
        assert resp.json()["row_count"] == 7


class TestAskRouteRegistration:
    def test_ask_routes_are_versioned(self):
        from lab_manager.api.app import create_app

        app = create_app()
        paths = {route.path for route in app.routes if hasattr(route, "path")}

        assert "/api/v1/ask" in paths
        assert "/api/v1/ask/" in paths
        assert "/api/ask" not in paths
        assert "/api/ask/" not in paths


# ---------------------------------------------------------------------------
# api/routes/audit.py — filter params
# ---------------------------------------------------------------------------


class TestAuditRoutes:
    def test_list_with_table_filter(self, client):
        resp = client.get("/api/v1/audit/?table=vendors")
        assert resp.status_code == 200

    def test_list_with_record_id_filter(self, client):
        resp = client.get("/api/v1/audit/?record_id=1")
        assert resp.status_code == 200

    def test_list_with_action_filter(self, client):
        resp = client.get("/api/v1/audit/?action=create")
        assert resp.status_code == 200

    def test_list_with_changed_by_filter(self, client):
        resp = client.get("/api/v1/audit/?changed_by=admin")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# api/routes/alerts.py — filter params
# ---------------------------------------------------------------------------


class TestAlertRoutes:
    def test_list_with_type_filter(self, client):
        resp = client.get("/api/v1/alerts/?alert_type=expired")
        assert resp.status_code == 200

    def test_list_with_severity_filter(self, client):
        resp = client.get("/api/v1/alerts/?severity=critical")
        assert resp.status_code == 200

    def test_list_with_acknowledged_filter(self, client):
        resp = client.get("/api/v1/alerts/?acknowledged=true")
        assert resp.status_code == 200

    def test_list_with_resolved_filter(self, client):
        resp = client.get("/api/v1/alerts/?resolved=true")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# api/routes/inventory.py — expiring_before, search filters
# ---------------------------------------------------------------------------


class TestInventoryRoutes:
    def test_list_with_expiring_before(self, client):
        resp = client.get("/api/v1/inventory/?expiring_before=2027-01-01")
        assert resp.status_code == 200

    def test_list_with_search(self, client):
        resp = client.get("/api/v1/inventory/?search=test")
        assert resp.status_code == 200

    def test_list_with_location_filter(self, client):
        resp = client.get("/api/v1/inventory/?location_id=1")
        assert resp.status_code == 200

    def test_list_with_status_filter(self, client):
        resp = client.get("/api/v1/inventory/?status=available")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# api/routes/products.py — include_inactive, search
# ---------------------------------------------------------------------------


class TestProductRoutes:
    def test_list_include_inactive(self, client):
        resp = client.get("/api/v1/products/?include_inactive=true")
        assert resp.status_code == 200

    def test_list_with_category(self, client):
        resp = client.get("/api/v1/products/?category=reagent")
        assert resp.status_code == 200

    def test_list_with_catalog_search(self, client):
        resp = client.get("/api/v1/products/?catalog_number=ABC")
        assert resp.status_code == 200

    def test_list_with_search(self, client):
        resp = client.get("/api/v1/products/?search=test")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# api/routes/vendors.py — search, delete with conflict
# ---------------------------------------------------------------------------


class TestVendorRoutes:
    def test_delete_vendor_conflict(self, client, db_session):
        """Test that vendor delete raises 409 when IntegrityError occurs."""
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="V-delete-test")
        db_session.add(v)
        db_session.flush()
        vid = v.id

        # SQLite doesn't enforce FK by default, so mock the IntegrityError
        from sqlalchemy.exc import IntegrityError

        with patch("lab_manager.api.routes.vendors.get_or_404") as mock_get:
            mock_get.return_value = v
            with patch.object(db_session, "delete", side_effect=None):
                with patch.object(
                    db_session,
                    "flush",
                    side_effect=IntegrityError("", {}, Exception()),
                ):
                    resp = client.delete(f"/api/v1/vendors/{vid}")
                    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# api/routes/documents.py — search, upload bad type, extraction model filter
# ---------------------------------------------------------------------------


class TestDocumentRoutes:
    def test_list_with_search(self, client):
        resp = client.get("/api/v1/documents/?search=test")
        assert resp.status_code == 200

    def test_list_with_extraction_model(self, client):
        resp = client.get("/api/v1/documents/?extraction_model=gemini")
        assert resp.status_code == 200

    def test_create_with_path_traversal(self, client):
        resp = client.post(
            "/api/v1/documents/",
            json={
                "file_path": "../../../etc/passwd",
                "file_name": "test.pdf",
            },
        )
        assert resp.status_code == 422

    def test_create_with_blocked_path(self, client):
        resp = client.post(
            "/api/v1/documents/",
            json={
                "file_path": "/etc/shadow",
                "file_name": "test.pdf",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# api/routes/export.py — empty csv
# ---------------------------------------------------------------------------


class TestExportRoutes:
    def test_export_empty_inventory(self, client):
        resp = client.get("/api/v1/export/inventory")
        assert resp.status_code == 200

    def test_export_products_csv(self, client):
        resp = client.get("/api/v1/export/products")
        assert resp.status_code == 200

    def test_export_vendors_csv(self, client):
        resp = client.get("/api/v1/export/vendors")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# services/alerts.py — get_expiring_items, get_low_stock_items
# ---------------------------------------------------------------------------


class TestAlertService:
    def test_get_expiring_items(self, db_session):
        from lab_manager.services.alerts import get_expiring_items

        result = get_expiring_items(db_session, days_ahead=30)
        assert isinstance(result, list)

    def test_get_low_stock_items(self, db_session):
        from lab_manager.services.alerts import get_low_stock_items

        result = get_low_stock_items(db_session, threshold=1)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# services/inventory.py — NaN/Inf rejection
# ---------------------------------------------------------------------------


class TestInventoryService:
    def test_to_decimal_nan(self):
        from lab_manager.services.inventory import _to_decimal

        with pytest.raises(Exception, match="finite"):
            _to_decimal(float("nan"))

    def test_to_decimal_inf(self):
        from lab_manager.services.inventory import _to_decimal

        with pytest.raises(Exception, match="finite"):
            _to_decimal(float("inf"))


# ---------------------------------------------------------------------------
# services/analytics.py — _money helper
# ---------------------------------------------------------------------------


class TestAnalyticsService:
    def test_money_none(self):
        from lab_manager.services.analytics import _money

        assert _money(None) == 0.0

    def test_money_value(self):
        from lab_manager.services.analytics import _money

        assert _money(3.14159) == 3.14
