"""Tests for intake validation rules."""

from datetime import datetime


from lab_manager.intake.validator import MAX_REASONABLE_QTY, validate


# ---------------------------------------------------------------------------
# Vendor name validation
# ---------------------------------------------------------------------------


class TestVendorNameValidation:
    """Tests for vendor_name field checks."""

    def test_vendor_name_too_long(self):
        data = {"vendor_name": "x" * 101}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "too_long" for i in issues
        )

    def test_vendor_name_at_max_length_ok(self):
        data = {"vendor_name": "x" * 100}
        issues = validate(data)
        assert not any(i["field"] == "vendor_name" for i in issues)

    def test_vendor_name_looking_like_address_blvd(self):
        data = {"vendor_name": "123 Main Blvd Suite 100"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "looks_like_address"
            for i in issues
        )

    def test_vendor_name_looking_like_address_street(self):
        data = {"vendor_name": "42 Wallaby Street"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "looks_like_address"
            for i in issues
        )

    def test_vendor_name_looking_like_address_ave(self):
        data = {"vendor_name": "Massachusetts Ave"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "looks_like_address"
            for i in issues
        )

    def test_vendor_name_looking_like_address_road(self):
        data = {"vendor_name": "Long Road"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "looks_like_address"
            for i in issues
        )

    def test_vendor_name_looking_like_address_suite(self):
        data = {"vendor_name": "Lab Supplies Suite 200"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "looks_like_address"
            for i in issues
        )

    def test_vendor_name_looking_like_address_drive(self):
        data = {"vendor_name": "Innovation Drive Corp"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "looks_like_address"
            for i in issues
        )

    def test_vendor_name_template_text_provider(self):
        data = {"vendor_name": "Provider: ABC Corp"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "template_text"
            for i in issues
        )

    def test_vendor_name_template_text_organization(self):
        data = {"vendor_name": "Original Organization Name"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "template_text"
            for i in issues
        )

    def test_vendor_name_template_text_original_material(self):
        data = {"vendor_name": "Original Material Provider"}
        issues = validate(data)
        assert any(
            i["field"] == "vendor_name" and i["issue"] == "template_text"
            for i in issues
        )

    def test_vendor_name_case_insensitive_address_check(self):
        data = {"vendor_name": "LONG ROAD"}
        issues = validate(data)
        assert any(i["issue"] == "looks_like_address" for i in issues)

    def test_valid_vendor_name_no_issues(self):
        data = {"vendor_name": "Sigma-Aldrich"}
        issues = validate(data)
        assert not any(i["field"] == "vendor_name" for i in issues)

    def test_no_vendor_name_no_issues(self):
        data = {}
        issues = validate(data)
        assert not any(i["field"] == "vendor_name" for i in issues)

    def test_vendor_name_none_no_issues(self):
        data = {"vendor_name": None}
        issues = validate(data)
        assert not any(i["field"] == "vendor_name" for i in issues)


# ---------------------------------------------------------------------------
# Document type validation
# ---------------------------------------------------------------------------


class TestDocumentTypeValidation:
    """Tests for document_type field checks."""

    def test_valid_document_types_no_issues(self):
        valid_types = {
            "packing_list",
            "invoice",
            "certificate_of_analysis",
            "shipping_label",
            "quote",
            "receipt",
            "mta",
            "other",
        }
        for dt in valid_types:
            issues = validate({"document_type": dt})
            assert not any(i["field"] == "document_type" for i in issues), (
                f"{dt} should be valid"
            )

    def test_invalid_document_type(self):
        data = {"document_type": "recipe"}
        issues = validate(data)
        assert len(issues) == 1
        assert issues[0]["field"] == "document_type"
        assert "invalid" in issues[0]["issue"]
        assert issues[0]["severity"] == "critical"

    def test_missing_document_type_no_issues(self):
        issues = validate({})
        assert not any(i["field"] == "document_type" for i in issues)


# ---------------------------------------------------------------------------
# Item validation
# ---------------------------------------------------------------------------


class TestItemValidation:
    """Tests for items list checks."""

    def test_negative_quantity_flagged(self):
        data = {"items": [{"quantity": -1}]}
        issues = validate(data)
        assert any(
            i["field"] == "items[0].quantity" and i["issue"] == "negative_quantity"
            for i in issues
        )

    def test_zero_quantity_flagged(self):
        data = {"items": [{"quantity": 0}]}
        issues = validate(data)
        assert any(
            i["field"] == "items[0].quantity" and i["issue"] == "zero" for i in issues
        )

    def test_large_quantity_warning(self):
        data = {"items": [{"quantity": MAX_REASONABLE_QTY}]}
        issues = validate(data)
        assert any(
            i["field"] == "items[0].quantity" and "large" in i["issue"] for i in issues
        )
        assert any(i["severity"] == "warning" for i in issues)

    def test_quantity_below_threshold_ok(self):
        data = {"items": [{"quantity": 50}]}
        issues = validate(data)
        assert not any(i["field"] == "items[0].quantity" for i in issues)

    def test_multiple_items_indexed_correctly(self):
        data = {"items": [{"quantity": -1}, {"quantity": 0}, {"quantity": 50}]}
        issues = validate(data)
        fields = [i["field"] for i in issues]
        assert "items[0].quantity" in fields
        assert "items[1].quantity" in fields
        # Item 2 is fine
        assert "items[2].quantity" not in fields

    def test_lot_number_vcat_prefix_flagged(self):
        data = {"items": [{"lot_number": "VCAT12345"}]}
        issues = validate(data)
        assert any(
            i["field"] == "items[0].lot_number" and i["issue"] == "vcat_code_not_lot"
            for i in issues
        )

    def test_lot_number_vcat_case_insensitive(self):
        data = {"items": [{"lot_number": "vcat-test-001"}]}
        issues = validate(data)
        assert any(i["issue"] == "vcat_code_not_lot" for i in issues)

    def test_lot_number_normal_ok(self):
        data = {"items": [{"lot_number": "LOT-2024-001"}]}
        issues = validate(data)
        assert not any("lot_number" in i["field"] for i in issues)

    def test_lot_number_none_ok(self):
        data = {"items": [{"lot_number": None}]}
        issues = validate(data)
        assert not any("lot_number" in i["field"] for i in issues)

    def test_lot_number_empty_string_ok(self):
        data = {"items": [{"lot_number": ""}]}
        issues = validate(data)
        assert not any("lot_number" in i["field"] for i in issues)

    def test_item_not_dict_skipped(self):
        """Non-dict items should not crash validation."""
        data = {"items": ["not a dict", 42, None]}
        issues = validate(data)
        assert not any("items" in i["field"] for i in issues)

    def test_empty_items_list_ok(self):
        issues = validate({"items": []})
        assert not any("items" in i["field"] for i in issues)

    def test_no_items_key_ok(self):
        issues = validate({})
        assert not any("items" in i["field"] for i in issues)


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------


class TestDateValidation:
    """Tests for date field validation."""

    def test_valid_dates_no_issues(self):
        year = datetime.now().year
        data = {
            "order_date": f"{year}-01-15",
            "ship_date": f"{year}-02-01",
            "received_date": f"{year}-02-05",
        }
        issues = validate(data)
        assert not any(
            i["field"] in ("order_date", "ship_date", "received_date") for i in issues
        )

    def test_unreasonable_year_flagged(self):
        data = {"order_date": "1990-01-01"}
        issues = validate(data)
        assert any(
            i["field"] == "order_date" and "unusual_year" in i["issue"] for i in issues
        )

    def test_future_year_beyond_bounds_flagged(self):
        year = datetime.now().year
        data = {"ship_date": f"{year + 5}-06-01"}
        issues = validate(data)
        assert any(
            i["field"] == "ship_date" and "unusual_year" in i["issue"] for i in issues
        )

    def test_invalid_date_format_flagged(self):
        data = {"order_date": "not-a-date"}
        issues = validate(data)
        assert any(
            i["field"] == "order_date" and i["issue"] == "invalid_format"
            for i in issues
        )

    def test_empty_date_string_not_flagged(self):
        """Empty string is treated as absent by the validator (falsy check)."""
        data = {"order_date": ""}
        issues = validate(data)
        assert not any(i["field"] == "order_date" for i in issues)

    def test_missing_date_no_issues(self):
        issues = validate({})
        assert not any("date" in i["field"] for i in issues)

    def test_none_date_no_issues(self):
        issues = validate({"order_date": None})
        assert not any(i["field"] == "order_date" for i in issues)

    def test_boundary_year_min_minus_one(self):
        """One year below the minimum should be flagged."""
        year = datetime.now().year
        data = {"received_date": f"{year - 7}-01-01"}
        issues = validate(data)
        assert any(i["field"] == "received_date" for i in issues)

    def test_boundary_year_min_exact(self):
        """Exact minimum year should NOT be flagged."""
        year = datetime.now().year
        data = {"received_date": f"{year - 6}-01-01"}
        issues = validate(data)
        assert not any(i["field"] == "received_date" for i in issues)


# ---------------------------------------------------------------------------
# Combined / edge-case validation
# ---------------------------------------------------------------------------


class TestCombinedValidation:
    """Tests for multiple validation rules firing together."""

    def test_clean_data_returns_empty_issues(self):
        data = {
            "vendor_name": "Thermo Fisher",
            "document_type": "invoice",
            "items": [{"quantity": 10, "lot_number": "LOT-001"}],
            "order_date": "2025-03-15",
        }
        issues = validate(data)
        assert issues == []

    def test_multiple_issues_reported(self):
        data = {
            "vendor_name": "x" * 101,
            "document_type": "invalid",
            "items": [{"quantity": -5, "lot_number": "VCAT999"}],
            "order_date": "1800-01-01",
        }
        issues = validate(data)
        fields = [i["field"] for i in issues]
        assert "vendor_name" in fields
        assert "document_type" in fields
        assert "items[0].quantity" in fields
        assert "items[0].lot_number" in fields
        assert "order_date" in fields

    def test_severity_levels(self):
        """Check that severity is correctly assigned."""
        data = {
            "vendor_name": "x" * 101,
            "items": [{"quantity": MAX_REASONABLE_QTY}],
            "order_date": "not-a-date",
        }
        issues = validate(data)
        severities = {i["field"]: i["severity"] for i in issues}
        assert severities["vendor_name"] == "critical"
        assert severities["items[0].quantity"] == "warning"
        assert severities["order_date"] == "warning"

    def test_max_reasonable_qty_constant(self):
        assert MAX_REASONABLE_QTY == 10000
