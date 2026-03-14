"""Test structured extraction from OCR text."""

from lab_manager.intake.extractor import extract_from_text
from lab_manager.intake.schemas import ExtractedDocument

SAMPLE_OCR = """MILLIPORE SIGMA
PACKING LIST
DELIVERY NO. 236655726
CUSTOMER PO PO-10997931
CATALOG NUMBER AB1031
AGGRECAN, RBX MS-50UG
Lot#: 4361991 (Qty: 1 EA)"""


def test_extract_from_text_returns_schema(monkeypatch):
    """Test that extraction returns valid ExtractedDocument."""

    # Mock the LLM call for testing
    def mock_extract(text: str) -> ExtractedDocument:
        return ExtractedDocument(
            vendor_name="EMD Millipore Corporation",
            document_type="packing_list",
            po_number="PO-10997931",
            items=[
                {
                    "catalog_number": "AB1031",
                    "description": "AGGRECAN, RBX MS-50UG",
                    "quantity": 1,
                    "lot_number": "4361991",
                }
            ],
        )

    monkeypatch.setattr("lab_manager.intake.extractor._call_llm", mock_extract)
    result = extract_from_text(SAMPLE_OCR)
    assert isinstance(result, ExtractedDocument)
    assert result.po_number == "PO-10997931"
    assert result.items[0].catalog_number == "AB1031"
