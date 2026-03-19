"""Rule-based validation for extracted data."""

from __future__ import annotations

from datetime import date

MAX_REASONABLE_QTY = 10000


def validate(data: dict) -> list[dict]:
    """Run validation rules. Returns list of issues found."""
    issues = []

    # Vendor name
    vendor = data.get("vendor_name")
    if vendor and len(vendor) > 100:
        issues.append({"field": "vendor_name", "issue": "too_long", "severity": "critical"})
    if vendor and any(x in vendor.lower() for x in ["blvd", "street", "ave", "road", "suite", "drive"]):
        issues.append(
            {
                "field": "vendor_name",
                "issue": "looks_like_address",
                "severity": "critical",
            }
        )
    if vendor and any(x in vendor.lower() for x in ["provider:", "organization", "original material"]):
        issues.append({"field": "vendor_name", "issue": "template_text", "severity": "critical"})

    # Document type
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
    doc_type = data.get("document_type")
    if doc_type and doc_type not in valid_types:
        issues.append(
            {
                "field": "document_type",
                "issue": f"invalid: {doc_type}",
                "severity": "critical",
            }
        )

    # Items
    for i, item in enumerate(data.get("items", [])):
        if not isinstance(item, dict):
            continue
        qty = item.get("quantity")
        if qty is not None and qty < 0:
            issues.append(
                {
                    "field": f"items[{i}].quantity",
                    "issue": "negative_quantity",
                    "severity": "critical",
                }
            )
        if qty is not None and qty == 0:
            issues.append(
                {
                    "field": f"items[{i}].quantity",
                    "issue": "zero",
                    "severity": "critical",
                }
            )
        if qty is not None and qty >= MAX_REASONABLE_QTY:
            issues.append(
                {
                    "field": f"items[{i}].quantity",
                    "issue": f"large: {qty}",
                    "severity": "warning",
                }
            )

        lot = item.get("lot_number", "") or ""
        if lot.upper().startswith("VCAT"):
            issues.append(
                {
                    "field": f"items[{i}].lot_number",
                    "issue": "vcat_code_not_lot",
                    "severity": "critical",
                }
            )

    # Dates
    for field in ["order_date", "ship_date", "received_date"]:
        val = data.get(field)
        if not val:
            continue
        try:
            d = date.fromisoformat(val)
            if d.year < 2020 or d.year > 2027:
                issues.append(
                    {
                        "field": field,
                        "issue": f"unusual_year: {d.year}",
                        "severity": "warning",
                    }
                )
        except (ValueError, TypeError):
            issues.append({"field": field, "issue": "invalid_format", "severity": "warning"})

    return issues
