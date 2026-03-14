"""Pydantic schemas for structured extraction from OCR text."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    """A single line item from a packing list / invoice."""

    catalog_number: Optional[str] = Field(
        None, description="Product catalog or item number"
    )
    description: Optional[str] = Field(None, description="Product description")
    quantity: Optional[float] = Field(None, description="Quantity ordered/shipped")
    unit: Optional[str] = Field(None, description="Unit of measure (EA, UL, MG, etc.)")
    lot_number: Optional[str] = Field(None, description="Lot or batch number")
    batch_number: Optional[str] = Field(
        None, description="Batch number if different from lot"
    )
    cas_number: Optional[str] = Field(None, description="CAS registry number")
    storage_temp: Optional[str] = Field(
        None, description="Storage temperature requirement"
    )
    unit_price: Optional[float] = Field(None, description="Price per unit")


class ExtractedDocument(BaseModel):
    """Structured data extracted from a scanned lab document."""

    vendor_name: str = Field(description="Supplier / vendor company name")
    document_type: str = Field(
        description="Type: packing_list, invoice, package, shipping_label"
    )
    po_number: Optional[str] = Field(None, description="Purchase order number")
    order_number: Optional[str] = Field(None, description="Sales or order number")
    invoice_number: Optional[str] = Field(None, description="Invoice number")
    delivery_number: Optional[str] = Field(
        None, description="Delivery or shipment number"
    )
    order_date: Optional[str] = Field(None, description="Order date in ISO format")
    ship_date: Optional[str] = Field(None, description="Shipping date")
    received_date: Optional[str] = Field(None, description="Handwritten receiving date")
    received_by: Optional[str] = Field(
        None, description="Person who received the package"
    )
    ship_to_address: Optional[str] = Field(
        None, description="Shipping destination address"
    )
    bill_to_address: Optional[str] = Field(None, description="Billing address")
    items: list[ExtractedItem] = Field(default_factory=list, description="Line items")
    confidence: Optional[float] = Field(None, description="Extraction confidence 0-1")
