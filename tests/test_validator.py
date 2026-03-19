"""Tests for rule-based extraction validator."""

from lab_manager.intake.validator import validate


def test_valid_document_passes():
    data = {
        "vendor_name": "Sigma-Aldrich",
        "document_type": "packing_list",
        "order_date": "2026-03-01",
        "items": [{"catalog_number": "AB1031", "quantity": 5, "lot_number": "LOT-123"}],
    }
    issues = validate(data)
    assert issues == []


def test_vendor_name_too_long():
    data = {"vendor_name": "A" * 101}
    issues = validate(data)
    assert any(i["issue"] == "too_long" and i["severity"] == "critical" for i in issues)


def test_vendor_name_is_address():
    data = {"vendor_name": "1234 Science Blvd Suite 100"}
    issues = validate(data)
    assert any(i["issue"] == "looks_like_address" for i in issues)


def test_vendor_name_is_template():
    data = {"vendor_name": "Organization Name Here"}
    issues = validate(data)
    assert any(i["issue"] == "template_text" for i in issues)


def test_invalid_document_type():
    data = {"document_type": "foobar"}
    issues = validate(data)
    assert any(i["field"] == "document_type" and i["severity"] == "critical" for i in issues)


def test_valid_document_types():
    valid = [
        "packing_list",
        "invoice",
        "certificate_of_analysis",
        "shipping_label",
        "quote",
        "receipt",
        "mta",
        "other",
    ]
    for dt in valid:
        issues = validate({"document_type": dt})
        doc_issues = [i for i in issues if i["field"] == "document_type"]
        assert doc_issues == [], f"{dt} should be valid but got {doc_issues}"


def test_quantity_zero():
    data = {"items": [{"quantity": 0}]}
    issues = validate(data)
    assert any(i["issue"] == "zero" and i["severity"] == "critical" for i in issues)


def test_quantity_negative():
    data = {"items": [{"quantity": -5}]}
    issues = validate(data)
    assert any(i["issue"] == "negative_quantity" and i["severity"] == "critical" for i in issues)


def test_quantity_large():
    data = {"items": [{"quantity": 50000}]}
    issues = validate(data)
    assert any("large" in i["issue"] and i["severity"] == "warning" for i in issues)


def test_quantity_normal():
    data = {"items": [{"quantity": 10}]}
    issues = validate(data)
    qty_issues = [i for i in issues if "quantity" in i.get("field", "")]
    assert qty_issues == []


def test_lot_number_is_vcat():
    data = {"items": [{"lot_number": "VCAT: RGF-3050"}]}
    issues = validate(data)
    assert any(i["issue"] == "vcat_code_not_lot" for i in issues)


def test_date_year_out_of_range():
    data = {"order_date": "2019-06-15"}
    issues = validate(data)
    assert any("unusual_year" in i["issue"] for i in issues)


def test_multiple_issues():
    data = {
        "vendor_name": "A" * 101,
        "document_type": "foobar",
        "items": [{"quantity": 0, "lot_number": "VCAT: ABC"}],
        "order_date": "2019-01-01",
    }
    issues = validate(data)
    fields_with_issues = {i["field"] for i in issues}
    assert "vendor_name" in fields_with_issues
    assert "document_type" in fields_with_issues
    assert "items[0].quantity" in fields_with_issues
    assert "items[0].lot_number" in fields_with_issues
    assert "order_date" in fields_with_issues
