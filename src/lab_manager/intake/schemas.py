"""Pydantic schemas for structured extraction from OCR text."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

VALID_DOC_TYPES = {
    "packing_list",
    "invoice",
    "certificate_of_analysis",
    "shipping_label",
    "quote",
    "receipt",
    "mta",
    "other",
}


class ExtractedItem(BaseModel):
    """A single line item from a packing list / invoice."""

    catalog_number: str | None = Field(
        None, description="Product catalog or item number"
    )
    description: str | None = Field(None, description="Product description")
    quantity: float | None = Field(None, description="Quantity ordered/shipped")
    unit: str | None = Field(None, description="Unit of measure (EA, UL, MG, etc.)")
    lot_number: str | None = Field(None, description="Lot or batch number")
    batch_number: str | None = Field(
        None, description="Batch number if different from lot"
    )
    cas_number: str | None = Field(None, description="CAS registry number")
    storage_temp: str | None = Field(
        None, description="Storage temperature requirement"
    )
    unit_price: float | None = Field(None, description="Price per unit")


class ExtractedDocument(BaseModel):
    """Structured data extracted from a scanned lab document."""

    vendor_name: str = Field(description="Supplier / vendor company name")
    document_type: str = Field(
        description="Type: packing_list, invoice, certificate_of_analysis, shipping_label, quote, receipt, mta, other"
    )
    po_number: str | None = Field(None, description="Purchase order number")
    order_number: str | None = Field(None, description="Sales or order number")
    invoice_number: str | None = Field(None, description="Invoice number")
    delivery_number: str | None = Field(None, description="Delivery or shipment number")
    order_date: str | None = Field(None, description="Order date in ISO format")
    ship_date: str | None = Field(None, description="Shipping date")
    received_date: str | None = Field(None, description="Handwritten receiving date")
    received_by: str | None = Field(None, description="Person who received the package")
    ship_to_address: str | None = Field(
        None, description="Shipping destination address"
    )
    bill_to_address: str | None = Field(None, description="Billing address")
    items: list[ExtractedItem] = Field(default_factory=list, description="Line items")
    confidence: float | None = Field(None, description="Extraction confidence 0-1")

    @field_validator("document_type")
    @classmethod
    def check_document_type(cls, v: str) -> str:
        if v not in VALID_DOC_TYPES:
            raise ValueError(
                f"invalid document_type: {v!r}, must be one of {VALID_DOC_TYPES}"
            )
        return v
