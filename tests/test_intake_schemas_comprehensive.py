"""Comprehensive tests for intake schema validators."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from lab_manager.intake.schemas import VALID_DOC_TYPES, ExtractedDocument, ExtractedItem


# ---------------------------------------------------------------------------
# ExtractedItem
# ---------------------------------------------------------------------------


class TestExtractedItem:
    """Tests for the ExtractedItem schema."""

    def test_all_fields_none_by_default(self):
        item = ExtractedItem()
        assert item.catalog_number is None
        assert item.description is None
        assert item.quantity is None
        assert item.unit is None
        assert item.lot_number is None
        assert item.batch_number is None
        assert item.cas_number is None
        assert item.storage_temp is None
        assert item.unit_price is None

    def test_full_item_creation(self):
        item = ExtractedItem(
            catalog_number="S12345",
            description="Anti-mouse CD3 antibody",
            quantity=Decimal("5"),
            unit="UG",
            lot_number="LOT-2024-001",
            batch_number="B-99",
            cas_number="1234-56-7",
            storage_temp="-20C",
            unit_price=Decimal("150.00"),
        )
        assert item.catalog_number == "S12345"
        assert item.description == "Anti-mouse CD3 antibody"
        assert item.quantity == Decimal("5")
        assert item.unit == "UG"
        assert item.lot_number == "LOT-2024-001"
        assert item.batch_number == "B-99"
        assert item.cas_number == "1234-56-7"
        assert item.storage_temp == "-20C"
        assert item.unit_price == Decimal("150.00")

    def test_quantity_accepts_integer_string(self):
        item = ExtractedItem(quantity=10)
        assert item.quantity == Decimal("10")

    def test_quantity_accepts_decimal_string(self):
        item = ExtractedItem(quantity=Decimal("3.5"))
        assert item.quantity == Decimal("3.5")

    def test_unit_price_precision(self):
        item = ExtractedItem(unit_price=Decimal("99.999"))
        assert item.unit_price == Decimal("99.999")

    def test_empty_strings_allowed(self):
        """Empty strings are valid for optional string fields."""
        item = ExtractedItem(description="", catalog_number="")
        assert item.description == ""
        assert item.catalog_number == ""

    def test_model_dump(self):
        item = ExtractedItem(catalog_number="ABC", quantity=Decimal("2"))
        d = item.model_dump()
        assert d["catalog_number"] == "ABC"
        assert d["quantity"] == Decimal("2")
        # None fields should still appear
        assert d["description"] is None

    def test_model_dump_exclude_none(self):
        item = ExtractedItem(catalog_number="ABC")
        d = item.model_dump(exclude_none=True)
        assert "catalog_number" in d
        assert "description" not in d


# ---------------------------------------------------------------------------
# ExtractedDocument
# ---------------------------------------------------------------------------


class TestExtractedDocumentDocumentType:
    """Tests for document_type validation."""

    def test_all_valid_doc_types_accepted(self):
        for dt in VALID_DOC_TYPES:
            doc = ExtractedDocument(document_type=dt)
            assert doc.document_type == dt

    def test_invalid_doc_type_rejected(self):
        with pytest.raises(ValidationError, match="invalid document_type"):
            ExtractedDocument(document_type="banana")

    def test_empty_string_doc_type_rejected(self):
        with pytest.raises(ValidationError, match="invalid document_type"):
            ExtractedDocument(document_type="")

    def test_case_sensitive_doc_type(self):
        """Document type validation is case-sensitive."""
        with pytest.raises(ValidationError):
            ExtractedDocument(document_type="Invoice")

    def test_doc_type_with_whitespace_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedDocument(document_type=" invoice ")


class TestExtractedDocumentDefaults:
    """Tests for default values and optional fields."""

    def test_optional_fields_default_to_none(self):
        doc = ExtractedDocument(document_type="invoice")
        assert doc.vendor_name is None
        assert doc.po_number is None
        assert doc.order_number is None
        assert doc.invoice_number is None
        assert doc.delivery_number is None
        assert doc.order_date is None
        assert doc.ship_date is None
        assert doc.received_date is None
        assert doc.received_by is None
        assert doc.ship_to_address is None
        assert doc.bill_to_address is None
        assert doc.confidence is None

    def test_items_default_to_empty_list(self):
        doc = ExtractedDocument(document_type="invoice")
        assert doc.items == []

    def test_items_with_entries(self):
        doc = ExtractedDocument(
            document_type="packing_list",
            items=[
                ExtractedItem(catalog_number="A1"),
                ExtractedItem(catalog_number="B2"),
            ],
        )
        assert len(doc.items) == 2
        assert doc.items[0].catalog_number == "A1"
        assert doc.items[1].catalog_number == "B2"


class TestExtractedDocumentConfidence:
    """Tests for confidence field boundaries."""

    def test_confidence_zero(self):
        doc = ExtractedDocument(document_type="invoice", confidence=0.0)
        assert doc.confidence == 0.0

    def test_confidence_one(self):
        doc = ExtractedDocument(document_type="invoice", confidence=1.0)
        assert doc.confidence == 1.0

    def test_confidence_fraction(self):
        doc = ExtractedDocument(document_type="invoice", confidence=0.85)
        assert doc.confidence == 0.85

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedDocument(document_type="invoice", confidence=1.1)

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedDocument(document_type="invoice", confidence=-0.1)

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValidationError):
            ExtractedDocument(document_type="invoice", confidence=-1.0)


class TestExtractedDocumentFull:
    """Tests for fully populated documents."""

    def test_full_document_creation(self):
        doc = ExtractedDocument(
            vendor_name="Sigma-Aldrich",
            document_type="packing_list",
            po_number="PO-12345",
            order_number="SO-67890",
            invoice_number="INV-001",
            delivery_number="DEL-999",
            order_date="2024-01-15",
            ship_date="2024-01-16",
            received_date="2024-01-20",
            received_by="Jane Doe",
            ship_to_address="123 Main St, Boston, MA",
            bill_to_address="456 Billing Ave, Cambridge, MA",
            items=[
                ExtractedItem(
                    catalog_number="SRE0001",
                    description="DMEM media",
                    quantity=Decimal("10"),
                    unit="EA",
                )
            ],
            confidence=0.92,
        )
        assert doc.vendor_name == "Sigma-Aldrich"
        assert doc.po_number == "PO-12345"
        assert doc.order_date == "2024-01-15"
        assert len(doc.items) == 1
        assert doc.items[0].quantity == Decimal("10")
        assert doc.confidence == 0.92

    def test_model_dump_roundtrip(self):
        """Verify dump + re-create produces equal document."""
        original = ExtractedDocument(
            document_type="invoice",
            vendor_name="Fisher",
            items=[ExtractedItem(catalog_number="X1")],
            confidence=0.75,
        )
        data = original.model_dump()
        restored = ExtractedDocument(**data)
        assert restored == original

    def test_json_roundtrip(self):
        original = ExtractedDocument(
            document_type="quote",
            vendor_name="Bio-Rad",
            confidence=0.5,
        )
        json_str = original.model_dump_json()
        restored = ExtractedDocument.model_validate_json(json_str)
        assert restored.document_type == original.document_type
        assert restored.vendor_name == original.vendor_name
        assert restored.confidence == original.confidence


class TestValidDocTypesConstant:
    """Tests for the VALID_DOC_TYPES set."""

    def test_is_a_set(self):
        assert isinstance(VALID_DOC_TYPES, set)

    def test_contains_expected_types(self):
        expected = {
            "packing_list",
            "invoice",
            "certificate_of_analysis",
            "shipping_label",
            "quote",
            "receipt",
            "mta",
            "other",
        }
        assert VALID_DOC_TYPES == expected

    def test_has_eight_entries(self):
        assert len(VALID_DOC_TYPES) == 8
