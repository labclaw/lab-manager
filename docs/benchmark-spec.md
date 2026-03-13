# OCR benchmark spec

This benchmark is decision-grade only if it measures the fields the lab operations workflow actually depends on.

## Scope

Incoming document types in the current sample set:

- supplier packing lists
- package summaries
- invoices
- documents with handwritten receiving dates

## Primary metrics

These decide whether a model is usable:

- `field_recall`: does the OCR output preserve the exact business-critical string?
- `field_precision`: does it hallucinate or corrupt critical identifiers?
- `document_pass_rate`: can the document be archived without manual repair?
- `hard-case_recall`: handwritten dates, low-contrast scans, multi-line item descriptions

## Critical fields

- supplier / vendor
- document type
- order date / package date / invoice date
- PO / sales order / delivery / invoice references
- catalog number
- item description
- lot or batch
- quantity
- handwritten receiving date

## Failure slices

- low-contrast grayscale scans
- table or form layouts
- multi-item packing slips
- handwriting on top of printed text
- supplier template variation

## Acceptance gates

- Critical typed fields should be near-perfect on the current benchmark set.
- Handwritten receiving dates must be explicitly measured, not assumed.
- A model is not production-ready if it drops PO, catalog number, or lot / batch on any benchmark sample.
