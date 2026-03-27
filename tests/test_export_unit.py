"""Comprehensive unit tests for CSV export route module.

Covers: _escape_cell, _escape_row, _csv_response, and all four endpoint functions
using direct function invocation with mocked dependencies.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from unittest.mock import MagicMock, patch


from lab_manager.api.routes.export import (
    _DANGEROUS_PREFIXES,
    _csv_response,
    _escape_cell,
    _escape_row,
    export_inventory,
    export_orders,
    export_products,
    export_vendors,
)


# ============================================================================
# _escape_cell
# ============================================================================


class TestEscapeCellNone:
    """None input handling."""

    def test_none_returns_empty_string(self):
        assert _escape_cell(None) == ""

    def test_none_is_not_type_str(self):
        result = _escape_cell(None)
        assert isinstance(result, str)


class TestEscapeCellNonString:
    """Non-string values returned as-is (no escaping applied)."""

    def test_integer(self):
        assert _escape_cell(42) == 42

    def test_float(self):
        assert _escape_cell(3.14) == 3.14

    def test_boolean_true(self):
        assert _escape_cell(True) is True

    def test_boolean_false(self):
        assert _escape_cell(False) is False

    def test_zero(self):
        assert _escape_cell(0) == 0

    def test_negative_integer(self):
        assert _escape_cell(-20) == -20

    def test_large_float(self):
        assert _escape_cell(1e9) == 1e9

    def test_list_value(self):
        lst = [1, 2, 3]
        assert _escape_cell(lst) is lst

    def test_dict_value(self):
        d = {"a": 1}
        assert _escape_cell(d) is d


class TestEscapeCellEquals:
    """Strings starting with '=' are formula injection vectors."""

    def test_formula_equals(self):
        assert _escape_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"

    def test_equals_only(self):
        assert _escape_cell("=") == "'="

    def test_equals_space(self):
        assert _escape_cell("= cmd") == "'= cmd"

    def test_equals_complex_formula(self):
        assert _escape_cell("=CMD|'/C calc'!A0") == "'=CMD|'/C calc'!A0"


class TestEscapeCellPlus:
    """Strings starting with '+' are formula injection vectors."""

    def test_formula_plus(self):
        assert _escape_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"

    def test_plus_only(self):
        assert _escape_cell("+") == "'+"

    def test_plus_digit(self):
        assert _escape_cell("+1+1") == "'+1+1"


class TestEscapeCellAt:
    """Strings starting with '@' are formula injection vectors."""

    def test_formula_at(self):
        assert _escape_cell("@SUM(A1)") == "'@SUM(A1)"

    def test_at_only(self):
        assert _escape_cell("@") == "'@"

    def test_at_email_like(self):
        assert _escape_cell("@import") == "'@import"


class TestEscapeCellTab:
    """Strings starting with TAB are formula injection vectors."""

    def test_tab_prefix(self):
        assert _escape_cell("\tcmd") == "'\tcmd"

    def test_tab_only(self):
        assert _escape_cell("\t") == "'\t"

    def test_tab_equals(self):
        assert _escape_cell("\t=cmd") == "'\t=cmd"


class TestEscapeCellCarriageReturn:
    """Strings starting with CR are formula injection vectors."""

    def test_cr_prefix(self):
        assert _escape_cell("\r=cmd") == "'\r=cmd"

    def test_cr_only(self):
        assert _escape_cell("\r") == "'\r"

    def test_cr_newline(self):
        assert _escape_cell("\r\nmalicious") == "'\r\nmalicious"


class TestEscapeCellNewline:
    """Strings starting with LF are formula injection vectors."""

    def test_newline_prefix(self):
        assert _escape_cell("\n=cmd") == "'\n=cmd"

    def test_newline_only(self):
        assert _escape_cell("\n") == "'\n"

    def test_newline_tab(self):
        assert _escape_cell("\n\tdata") == "'\n\tdata"


class TestEscapeCellMinus:
    """Minus prefix: safe when followed by digit, escaped otherwise."""

    def test_minus_with_letter_is_dangerous(self):
        assert _escape_cell("-cmd|' /C calc'!A0") == "'-cmd|' /C calc'!A0"

    def test_minus_digit_is_safe(self):
        assert _escape_cell("-1+1") == "-1+1"

    def test_minus_digit_temp(self):
        assert _escape_cell("-20C") == "-20C"

    def test_minus_zero_is_safe(self):
        assert _escape_cell("-0") == "-0"

    def test_minus_negative_number(self):
        assert _escape_cell("-99.5") == "-99.5"

    def test_minus_space_is_dangerous(self):
        assert _escape_cell("- formula") == "'- formula"

    def test_minus_equals_is_dangerous(self):
        assert _escape_cell("-=cmd") == "'-=cmd"

    def test_minus_alone_is_safe(self):
        """Single '-' has length 1, so the len > 1 check prevents escaping."""
        assert _escape_cell("-") == "-"

    def test_minus_underscore_is_dangerous(self):
        assert _escape_cell("_test") == "_test"  # underscore is safe

    def test_minus_dot_is_dangerous(self):
        assert _escape_cell("-.hidden") == "'-.hidden"


class TestEscapeCellSafeStrings:
    """Strings that do not start with a dangerous prefix."""

    def test_normal_text(self):
        assert _escape_cell("Normal text") == "Normal text"

    def test_empty_string(self):
        assert _escape_cell("") == ""

    def test_alphanumeric(self):
        assert _escape_cell("ABC123") == "ABC123"

    def test_space_prefix(self):
        assert _escape_cell(" hello") == " hello"

    def test_special_chars_safe_start(self):
        assert _escape_cell("#tag") == "#tag"

    def test_parentheses(self):
        assert _escape_cell("(value)") == "(value)"

    def test_bracket(self):
        assert _escape_cell("[array]") == "[array]"

    def test_slash(self):
        assert _escape_cell("/path/to/file") == "/path/to/file"

    def test_chinese(self):
        assert _escape_cell("试剂") == "试剂"

    def test_unicode_emoji(self):
        assert _escape_cell("🧪 reagent") == "🧪 reagent"


class TestEscapeCellSpecialCharsInside:
    """Strings with special chars in non-first position remain untouched."""

    def test_equals_in_middle(self):
        assert _escape_cell("a=b") == "a=b"

    def test_plus_in_middle(self):
        assert _escape_cell("a+b") == "a+b"

    def test_at_in_middle(self):
        assert _escape_cell("user@host") == "user@host"

    def test_minus_in_middle(self):
        assert _escape_cell("a-b") == "a-b"

    def test_formula_text_in_middle(self):
        assert _escape_cell("price =SUM(A1)") == "price =SUM(A1)"


# ============================================================================
# _DANGEROUS_PREFIXES constant
# ============================================================================


class TestDangerousPrefixes:
    """Verify the _DANGEROUS_PREFIXES tuple contents."""

    def test_is_tuple(self):
        assert isinstance(_DANGEROUS_PREFIXES, tuple)

    def test_contains_equals(self):
        assert "=" in _DANGEROUS_PREFIXES

    def test_contains_plus(self):
        assert "+" in _DANGEROUS_PREFIXES

    def test_contains_minus(self):
        assert "-" in _DANGEROUS_PREFIXES

    def test_contains_at(self):
        assert "@" in _DANGEROUS_PREFIXES

    def test_contains_tab(self):
        assert "\t" in _DANGEROUS_PREFIXES

    def test_contains_cr(self):
        assert "\r" in _DANGEROUS_PREFIXES

    def test_contains_lf(self):
        assert "\n" in _DANGEROUS_PREFIXES

    def test_seven_members(self):
        assert len(_DANGEROUS_PREFIXES) == 7


# ============================================================================
# _escape_row
# ============================================================================


class TestEscapeRowEmpty:
    """Empty dict handling."""

    def test_empty_dict(self):
        assert _escape_row({}) == {}

    def test_empty_dict_returns_new_dict(self):
        d = {}
        result = _escape_row(d)
        assert result == {}
        assert result is not d


class TestEscapeRowMixedTypes:
    """Dict with values of various types."""

    def test_mixed_types(self):
        row = {"name": "Acetone", "qty": 10, "price": 29.99, "active": True}
        result = _escape_row(row)
        assert result == {"name": "Acetone", "qty": 10, "price": 29.99, "active": True}

    def test_string_values_escaped(self):
        row = {"formula": "=SUM(A1)", "safe": "hello"}
        result = _escape_row(row)
        assert result["formula"] == "'=SUM(A1)"
        assert result["safe"] == "hello"


class TestEscapeRowNoneValues:
    """Dict with None values."""

    def test_none_becomes_empty(self):
        row = {"a": None, "b": "text"}
        result = _escape_row(row)
        assert result["a"] == ""
        assert result["b"] == "text"

    def test_all_none(self):
        row = {"x": None, "y": None}
        result = _escape_row(row)
        assert result == {"x": "", "y": ""}


class TestEscapeRowDangerousValues:
    """Dict with multiple dangerous formula-injection values."""

    def test_all_dangerous_prefixes(self):
        row = {
            "eq": "=cmd",
            "plus": "+cmd",
            "at": "@cmd",
            "tab": "\tcmd",
            "cr": "\rcmd",
            "lf": "\ncmd",
            "minus_letter": "-cmd",
        }
        result = _escape_row(row)
        assert result["eq"] == "'=cmd"
        assert result["plus"] == "'+cmd"
        assert result["at"] == "'@cmd"
        assert result["tab"] == "'\tcmd"
        assert result["cr"] == "'\rcmd"
        assert result["lf"] == "'\ncmd"
        assert result["minus_letter"] == "'-cmd"

    def test_minus_digit_not_escaped_in_row(self):
        row = {"temp": "-20C"}
        result = _escape_row(row)
        assert result["temp"] == "-20C"

    def test_preserves_keys(self):
        row = {"key1": "val1", "key2": "val2"}
        result = _escape_row(row)
        assert set(result.keys()) == {"key1", "key2"}


# ============================================================================
# _csv_response
# ============================================================================


class TestCsvResponseEmptyRows:
    """Empty rows list handling."""

    def test_empty_rows_with_fieldnames(self):
        resp = _csv_response([], "test.csv", fieldnames=["a", "b"])
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        # Header only, no data rows
        lines = body.strip().split("\r\n")
        assert lines[0] == "a,b"

    def test_empty_rows_without_fieldnames(self):
        resp = _csv_response([], "test.csv")
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        # fieldnames defaults to [] when no rows and no fieldnames
        lines = body.strip().split("\r\n")
        # Empty fieldnames means header line is just the newline
        assert body.strip() == ""

    def test_empty_rows_count(self):
        resp = _csv_response([], "test.csv", fieldnames=["x"])
        body = _read_streaming_response(resp)
        lines = [l for l in body.strip().split("\r\n") if l]
        assert len(lines) == 1  # header only


class TestCsvResponseNormalRows:
    """Normal data rows."""

    def test_single_row(self):
        rows = [{"name": "Alice", "age": "30"}]
        resp = _csv_response(rows, "test.csv")
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        result = list(reader)
        assert len(result) == 1
        assert result[0]["name"] == "Alice"
        assert result[0]["age"] == "30"

    def test_multiple_rows(self):
        rows = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]
        resp = _csv_response(rows, "test.csv")
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        result = list(reader)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["name"] == "Bob"

    def test_fieldnames_from_first_row(self):
        rows = [{"x": "1", "y": "2"}]
        resp = _csv_response(rows, "test.csv")
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        assert reader.fieldnames == ["x", "y"]

    def test_explicit_fieldnames_order(self):
        rows = [{"a": "1", "b": "2", "c": "3"}]
        resp = _csv_response(rows, "test.csv", fieldnames=["a", "b", "c"])
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        assert reader.fieldnames == ["a", "b", "c"]


class TestCsvResponseSpecialChars:
    """Rows containing special characters are properly escaped."""

    def test_formula_cells_escaped_in_csv(self):
        rows = [{"val": "=SUM(A1)"}]
        resp = _csv_response(rows, "test.csv")
        body = _read_streaming_response(resp)
        assert "'=SUM(A1)" in body

    def test_csv_comma_in_value(self):
        rows = [{"desc": "hello, world"}]
        resp = _csv_response(rows, "test.csv")
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        result = list(reader)
        assert result[0]["desc"] == "hello, world"

    def test_csv_quotes_in_value(self):
        rows = [{"desc": 'He said "hi"'}]
        resp = _csv_response(rows, "test.csv")
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        result = list(reader)
        assert result[0]["desc"] == 'He said "hi"'

    def test_none_in_row_becomes_empty_in_csv(self):
        rows = [{"name": "test", "value": None}]
        resp = _csv_response(rows, "test.csv")
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        result = list(reader)
        assert result[0]["value"] == ""


class TestCsvResponseHeaders:
    """Response HTTP headers."""

    def test_content_disposition(self):
        resp = _csv_response([{"a": "1"}], "inventory.csv")
        assert (
            resp.headers["content-disposition"]
            == 'attachment; filename="inventory.csv"'
        )

    def test_media_type(self):
        resp = _csv_response([{"a": "1"}], "test.csv")
        assert "text/csv" in resp.media_type

    def test_charset_utf8(self):
        resp = _csv_response([{"a": "1"}], "test.csv")
        assert "charset=utf-8" in resp.media_type

    def test_custom_filename(self):
        resp = _csv_response([], "custom_report.csv", fieldnames=["x"])
        assert "custom_report.csv" in resp.headers["content-disposition"]


# ============================================================================
# Endpoint tests: export_inventory
# ============================================================================


class TestExportInventory:
    """export_inventory endpoint via direct function call with mock db."""

    def test_inventory_basic(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.inventory_report.return_value = [
                {"product_name": "Acetone", "quantity": 10}
            ]
            resp = export_inventory(location_id=None, db=mock_db)
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        assert "product_name" in body
        assert "Acetone" in body
        mock_svc.inventory_report.assert_called_once_with(mock_db, location_id=None)

    def test_inventory_with_location_id(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.inventory_report.return_value = []
            resp = export_inventory(location_id=5, db=mock_db)
        assert resp.status_code == 200
        mock_svc.inventory_report.assert_called_once_with(mock_db, location_id=5)

    def test_inventory_empty_result(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.inventory_report.return_value = []
            resp = export_inventory(location_id=None, db=mock_db)
        body = _read_streaming_response(resp)
        # No rows, filename is inventory.csv, fieldnames derived from empty list
        assert "inventory.csv" in resp.headers["content-disposition"]

    def test_inventory_escapes_dangerous_values(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.inventory_report.return_value = [
                {"product_name": "=SUM(A1)", "quantity": 5}
            ]
            resp = export_inventory(location_id=None, db=mock_db)
        body = _read_streaming_response(resp)
        assert "'=SUM(A1)" in body

    def test_inventory_csv_filename(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.inventory_report.return_value = [{"a": "b"}]
            resp = export_inventory(location_id=None, db=mock_db)
        assert "inventory.csv" in resp.headers["content-disposition"]


# ============================================================================
# Endpoint tests: export_orders
# ============================================================================


class TestExportOrders:
    """export_orders endpoint via direct function call with mock db."""

    def test_orders_basic(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.order_history.return_value = [
                {"vendor": "Sigma", "total": "100.00"}
            ]
            resp = export_orders(
                vendor_id=None, date_from=None, date_to=None, db=mock_db
            )
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        assert "vendor" in body
        assert "Sigma" in body
        mock_svc.order_history.assert_called_once_with(
            mock_db, vendor_id=None, date_from=None, date_to=None
        )

    def test_orders_with_vendor_filter(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.order_history.return_value = []
            resp = export_orders(vendor_id=3, date_from=None, date_to=None, db=mock_db)
        mock_svc.order_history.assert_called_once_with(
            mock_db, vendor_id=3, date_from=None, date_to=None
        )

    def test_orders_with_date_range(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.order_history.return_value = []
            df = date(2026, 1, 1)
            dt = date(2026, 3, 27)
            resp = export_orders(vendor_id=None, date_from=df, date_to=dt, db=mock_db)
        mock_svc.order_history.assert_called_once_with(
            mock_db, vendor_id=None, date_from=df, date_to=dt
        )

    def test_orders_all_filters(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.order_history.return_value = [
                {"id": "1", "vendor": "V", "total": "50"}
            ]
            df = date(2026, 1, 1)
            dt = date(2026, 3, 27)
            resp = export_orders(vendor_id=7, date_from=df, date_to=dt, db=mock_db)
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        assert "id" in body

    def test_orders_csv_filename(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.order_history.return_value = [{"a": "b"}]
            resp = export_orders(
                vendor_id=None, date_from=None, date_to=None, db=mock_db
            )
        assert "orders.csv" in resp.headers["content-disposition"]

    def test_orders_empty_result(self):
        mock_db = MagicMock()
        with patch("lab_manager.api.routes.export.svc") as mock_svc:
            mock_svc.order_history.return_value = []
            resp = export_orders(
                vendor_id=None, date_from=None, date_to=None, db=mock_db
            )
        assert resp.status_code == 200


# ============================================================================
# Endpoint tests: export_products
# ============================================================================


class TestExportProducts:
    """export_products endpoint via direct function call with mock db."""

    def test_products_basic(self):
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.catalog_number = "S1234"
        mock_product.name = "Acetone"
        mock_product.vendor_id = 10
        mock_product.category = "Solvent"
        mock_product.cas_number = "67-64-1"
        mock_product.storage_temp = "-20C"
        mock_product.unit = "mL"
        mock_product.hazard_info = None
        mock_product.min_stock_level = 5
        mock_product.is_hazardous = True
        mock_product.is_controlled = False

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = [mock_product]

        resp = export_products(db=mock_db)
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        assert "catalog_number" in body
        assert "Acetone" in body
        assert "67-64-1" in body

    def test_products_empty(self):
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []

        resp = export_products(db=mock_db)
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        # Header row should still have all fieldnames
        reader = csv.DictReader(io.StringIO(body))
        assert reader.fieldnames == [
            "id",
            "catalog_number",
            "name",
            "vendor_id",
            "category",
            "cas_number",
            "storage_temp",
            "unit",
            "hazard_info",
            "min_stock_level",
            "is_hazardous",
            "is_controlled",
        ]

    def test_products_csv_filename(self):
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []
        resp = export_products(db=mock_db)
        assert "products.csv" in resp.headers["content-disposition"]

    def test_products_fieldnames_complete(self):
        """Verify all 12 expected fieldnames are present."""
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []
        resp = export_products(db=mock_db)
        body = _read_streaming_response(resp)
        header_line = body.strip().split("\r\n")[0]
        fields = header_line.split(",")
        assert len(fields) == 12

    def test_products_escapes_formula_in_name(self):
        mock_product = MagicMock()
        mock_product.id = 1
        mock_product.catalog_number = "X1"
        mock_product.name = "=MALICIOUS"
        mock_product.vendor_id = None
        mock_product.category = None
        mock_product.cas_number = None
        mock_product.storage_temp = None
        mock_product.unit = None
        mock_product.hazard_info = None
        mock_product.min_stock_level = None
        mock_product.is_hazardous = None
        mock_product.is_controlled = None

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = [mock_product]

        resp = export_products(db=mock_db)
        body = _read_streaming_response(resp)
        assert "'=MALICIOUS" in body

    def test_products_missing_attribute_defaults_none(self):
        """Product missing an attribute should get None -> empty string."""
        mock_product = MagicMock(spec=[])
        mock_product.id = 1

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = [mock_product]

        resp = export_products(db=mock_db)
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        rows = list(reader)
        assert len(rows) == 1


# ============================================================================
# Endpoint tests: export_vendors
# ============================================================================


class TestExportVendors:
    """export_vendors endpoint via direct function call with mock db."""

    def test_vendors_basic(self):
        mock_vendor = MagicMock()
        mock_vendor.id = 1
        mock_vendor.name = "Sigma-Aldrich"
        mock_vendor.website = "https://sigmaaldrich.com"
        mock_vendor.phone = "+1-800-123-4567"
        mock_vendor.email = "sales@sigma.com"
        mock_vendor.notes = None

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = [mock_vendor]

        resp = export_vendors(db=mock_db)
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        assert "Sigma-Aldrich" in body
        assert "https://sigmaaldrich.com" in body

    def test_vendors_empty(self):
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []

        resp = export_vendors(db=mock_db)
        assert resp.status_code == 200
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        assert reader.fieldnames == ["id", "name", "website", "phone", "email", "notes"]

    def test_vendors_csv_filename(self):
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []
        resp = export_vendors(db=mock_db)
        assert "vendors.csv" in resp.headers["content-disposition"]

    def test_vendors_fieldnames_count(self):
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = []
        resp = export_vendors(db=mock_db)
        body = _read_streaming_response(resp)
        header_line = body.strip().split("\r\n")[0]
        fields = header_line.split(",")
        assert len(fields) == 6

    def test_vendors_escapes_formula_in_notes(self):
        mock_vendor = MagicMock()
        mock_vendor.id = 1
        mock_vendor.name = "Safe"
        mock_vendor.website = None
        mock_vendor.phone = None
        mock_vendor.email = None
        mock_vendor.notes = "=CMD|malicious"

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = [mock_vendor]

        resp = export_vendors(db=mock_db)
        body = _read_streaming_response(resp)
        assert "'=CMD|malicious" in body

    def test_vendors_multiple_rows(self):
        vendors = []
        for i in range(3):
            v = MagicMock()
            v.id = i + 1
            v.name = f"Vendor {i + 1}"
            v.website = None
            v.phone = None
            v.email = None
            v.notes = None
            vendors.append(v)

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = vendors

        resp = export_vendors(db=mock_db)
        body = _read_streaming_response(resp)
        reader = csv.DictReader(io.StringIO(body))
        rows = list(reader)
        assert len(rows) == 3

    def test_vendors_missing_attribute(self):
        mock_vendor = MagicMock(spec=[])
        mock_vendor.id = 42

        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = [mock_vendor]

        resp = export_vendors(db=mock_db)
        assert resp.status_code == 200


# ============================================================================
# Helpers
# ============================================================================


async def _read_streaming_response_async(resp) -> str:
    """Read the full body from a StreamingResponse (async body_iterator)."""
    chunks = []
    async for chunk in resp.body_iterator:
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode("utf-8"))
        else:
            chunks.append(chunk)
    return "".join(chunks)


def _read_streaming_response(resp) -> str:
    """Synchronous wrapper for reading a StreamingResponse body."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(
                asyncio.run, _read_streaming_response_async(resp)
            ).result()
    return asyncio.run(_read_streaming_response_async(resp))
