"""Centralized prompts for document extraction and OCR."""

OCR_PROMPT = """You are performing OCR on a scanned lab supply document (packing list, invoice, or shipping label).
Transcribe ALL visible text as faithfully as possible, character by character.

Critical rules:
- Output plain text only.
- Preserve reading order from top to bottom, left to right.
- Keep line breaks where they appear on the document.
- Pay extra attention to:
  * Catalog/part numbers (e.g., AB2251-1, MAB5406) — distinguish digit 1 from letter I carefully.
  * Batch/lot numbers (e.g., SDBB4556, 4361991) — include ALL batch numbers even if partially visible.
  * Handwritten text and dates (e.g., 3/9/26, 2026.3.07) — transcribe handwritten notes exactly as written.
  * PO numbers, delivery numbers, order numbers.
- Include ALL text including fine print, footer text, and handwritten annotations.
- Do not summarize or explain. Do not add any commentary.
- Do not skip any text region.
"""

EXTRACTION_PROMPT = """You are extracting structured data from a scanned lab supply document image.

Look at the image carefully and extract ALL fields into this EXACT JSON format:
{
  "vendor_name": "company that sent/sold the item",
  "document_type": "one of: packing_list, invoice, certificate_of_analysis, shipping_label, quote, receipt, mta, other",
  "po_number": "purchase order number (starts with PO- or is labeled PO/Purchase Order)",
  "order_number": "sales/order number from the vendor",
  "invoice_number": "invoice number if present",
  "delivery_number": "delivery/shipment tracking number",
  "order_date": "YYYY-MM-DD format",
  "ship_date": "YYYY-MM-DD format",
  "received_date": "handwritten date if visible, YYYY-MM-DD",
  "received_by": "handwritten name if visible",
  "items": [
    {
      "catalog_number": "exact product/catalog number",
      "description": "product name/description",
      "quantity": numeric_value,
      "unit": "EA/UL/MG/ML/etc",
      "lot_number": "lot number (NOT tracking, NOT VCAT, NOT dates)",
      "batch_number": "batch number if different from lot",
      "unit_price": numeric_or_null
    }
  ],
  "confidence": 0.0-1.0
}

CRITICAL RULES:
- vendor_name: the SUPPLIER company (not the shipping carrier, not the buyer's address)
- document_type: COA = certificate_of_analysis, NOT packing_list or invoice
- po_number: ONLY the Purchase Order number. NOT tracking numbers, NOT vendor order numbers
- lot_number: ONLY actual lot/batch identifiers. NOT VCAT codes, NOT dates, NOT catalog numbers
- quantity: the actual count ordered/shipped. "1,000" on Bio-Rad forms means 1.000 (one), not 1000
- dates: use YYYY-MM-DD. For ambiguous formats (07-06-24), prefer MM-DD-YY for US documents
- Do NOT guess. If a field is not visible, use null.
- Output ONLY valid JSON, no markdown, no explanation.
"""
