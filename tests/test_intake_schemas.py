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


def test_extracted_document_vendor_name_optional():
    """Documents without a reliable vendor can still be represented."""
    doc = ExtractedDocument(vendor_name=None, document_type="other", items=[])
    assert doc.vendor_name is None


def test_extracted_item_expiry_date_round_trip():
    """expiry_date survives serialization and deserialization."""
    from lab_manager.intake.schemas import ExtractedItem

    item = ExtractedItem(
        catalog_number="AB1031",
        description="Test reagent",
        quantity=1,
        expiry_date="2027-06-15",
    )
    assert item.expiry_date == "2027-06-15"

    # Round-trip through dict
    data = item.model_dump()
    assert data["expiry_date"] == "2027-06-15"
    restored = ExtractedItem(**data)
    assert restored.expiry_date == "2027-06-15"

    # None when omitted
    item_no_expiry = ExtractedItem(catalog_number="X1")
    assert item_no_expiry.expiry_date is None


def test_extraction_prompt_matches_valid_doc_types():
    """EXTRACTION_PROMPT doc_type list must match VALID_DOC_TYPES in schemas."""
    import re

    from lab_manager.intake.extractor import EXTRACTION_PROMPT
    from lab_manager.intake.schemas import VALID_DOC_TYPES

    match = re.search(r"document_type:\s*one of\s+(.+)", EXTRACTION_PROMPT)
    assert match, "EXTRACTION_PROMPT must contain a 'document_type: one of ...' line"
    prompt_types = {t.strip() for t in match.group(1).split(",")}
    assert prompt_types == VALID_DOC_TYPES, (
        f"Prompt types {prompt_types} != schema types {VALID_DOC_TYPES}"
    )
