"""Test extraction schemas."""

from lab_manager.intake.schemas import ExtractedDocument


def test_extracted_document_from_dict():
    data = {
        "vendor_name": "Sigma-Aldrich",
        "document_type": "packing_list",
        "po_number": "PO-10997931",
        "order_date": "2026-03-04",
        "items": [
            {
                "catalog_number": "AB1031",
                "description": "AGGRECAN, RBX MS-50UG",
                "quantity": 1,
                "lot_number": "4361991",
            }
        ],
    }
    doc = ExtractedDocument(**data)
    assert doc.vendor_name == "Sigma-Aldrich"
    assert len(doc.items) == 1
    assert doc.items[0].catalog_number == "AB1031"


def test_extracted_document_optional_fields():
    """Minimal valid document."""
    doc = ExtractedDocument(vendor_name="Unknown", document_type="other", items=[])
    assert doc.po_number is None
