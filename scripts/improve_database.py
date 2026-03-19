#!/usr/bin/env python3
"""Improve Shen Lab database using best available OCR + SOTA extraction.

Uses:
- Gemini 2.5 Flash API OCR results from benchmark (270/279 docs, 0.911 Jaccard)
- Gemini 2.5 Pro API for structured extraction on all 279 images
- Validation rules to catch errors
- Updates documents, then rebuilds orders/vendors/products/inventory

Usage:
    uv run python scripts/improve_database.py
    uv run python scripts/improve_database.py --dry-run        # preview only
    uv run python scripts/improve_database.py --start 0 --end 10  # subset
    uv run python scripts/improve_database.py --skip-extraction    # only update OCR text
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y%m%d_%H%M%S",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
SHENLAB_DIR = PROJECT_ROOT / "shenlab-docs"
RESIZED_DIR = SHENLAB_DIR / "resized"
BENCHMARKS_DIR = PROJECT_ROOT / "benchmarks"
OUTPUT_DIR = PROJECT_ROOT / "pipeline_v2_output"

# Best OCR benchmark results (Gemini 2.5 Flash API)
OCR_DETAIL_FILE = BENCHMARKS_DIR / "ocr_bench_detail_20260314_102147_partial.json"
OCR_GEMINI_API_FILE = BENCHMARKS_DIR / "ocr_bench_gemini_api_20260314_102147_partial.json"

# Also load SOTA benchmark if available (has Gemini Pro results)
SOTA_DETAIL_FILE = BENCHMARKS_DIR / "ocr_bench_detail_20260314_120849_partial.json"
SOTA_GEMINI_PRO_FILE = BENCHMARKS_DIR / "ocr_bench_gemini_pro_20260314_120849_partial.json"

EXTRACTION_PROMPT = """You are extracting structured data from a scanned lab supply document image.

Look at the image carefully and extract ALL fields into this EXACT JSON format:
{
  "vendor_name": "company that sent/sold the item (the SUPPLIER, NOT the buyer, NOT the shipping carrier)",
  "document_type": "one of: packing_list, invoice, certificate_of_analysis, shipping_label, quote, receipt, mta, other",
  "po_number": "purchase order number (starts with PO- or is labeled PO/Purchase Order) or null",
  "order_number": "sales/order number from the vendor or null",
  "invoice_number": "invoice number if present or null",
  "delivery_number": "delivery/shipment tracking number or null",
  "order_date": "YYYY-MM-DD format or null",
  "ship_date": "YYYY-MM-DD format or null",
  "received_date": "handwritten date if visible, YYYY-MM-DD or null",
  "received_by": "handwritten name if visible or null",
  "items": [
    {
      "catalog_number": "exact product/catalog number",
      "description": "product name/description",
      "quantity": numeric_value_or_null,
      "unit": "EA/UL/MG/ML/BOX/PK/CS/KIT/SET/etc or null",
      "lot_number": "lot number (NOT tracking numbers, NOT VCAT codes, NOT dates) or null",
      "batch_number": "batch number if different from lot or null",
      "cas_number": "CAS registry number if present or null",
      "storage_temp": "storage temperature requirement or null",
      "unit_price": numeric_value_or_null
    }
  ],
  "confidence": 0.0-1.0
}

CRITICAL RULES:
- vendor_name: the SUPPLIER company. NOT FedEx/UPS (shipping carrier). NOT Harvard/MGH (buyer).
- document_type: COA = certificate_of_analysis. Packing slip = packing_list. Bill = invoice.
- po_number: ONLY Purchase Order numbers. NOT tracking numbers, NOT vendor order/reference numbers.
- lot_number: ONLY actual lot/batch identifiers. NOT VCAT codes, NOT dates, NOT catalog numbers.
- quantity: the actual count. "1,000" on Bio-Rad/European forms often means 1.000 (one), not 1000.
- unit_price: exact price per unit if shown. Include decimals.
- dates: use YYYY-MM-DD format. For ambiguous US dates (07-06-24), prefer MM-DD-YY.
- Do NOT guess. If a field is not clearly visible, use null.
- Output ONLY valid JSON, no markdown fences, no explanation text.
"""

# OCR prompt (simpler - just transcribe)
OCR_PROMPT = """Transcribe ALL text visible in this scanned document image.
Include every word, number, and symbol exactly as printed or handwritten.
Preserve the general layout with line breaks.
Do NOT add any commentary, headers, or formatting — just the raw text."""


def load_benchmark_ocr() -> dict[str, str]:
    """Load best OCR text from benchmark results.
    Returns {filename: ocr_text} dict.
    """
    ocr_map = {}

    # Load detail file for file names
    if OCR_DETAIL_FILE.exists() and OCR_GEMINI_API_FILE.exists():
        detail = json.loads(OCR_DETAIL_FILE.read_text())
        gemini_api = json.loads(OCR_GEMINI_API_FILE.read_text())

        for i, entry in enumerate(detail):
            fname = entry["file_name"]
            if i < len(gemini_api):
                ga = gemini_api[i]
                if ga.get("success") and ga.get("text"):
                    ocr_map[fname] = ga["text"]

    log.info("Loaded %d OCR results from Gemini Flash benchmark", len(ocr_map))

    # Also check if SOTA benchmark has Gemini Pro OCR for docs not in Flash
    if SOTA_DETAIL_FILE.exists() and SOTA_GEMINI_PRO_FILE.exists():
        sota_detail = json.loads(SOTA_DETAIL_FILE.read_text())
        sota_pro = json.loads(SOTA_GEMINI_PRO_FILE.read_text())

        added = 0
        for i, entry in enumerate(sota_detail):
            fname = entry["file_name"]
            if fname not in ocr_map and i < len(sota_pro):
                gp = sota_pro[i]
                if gp.get("success") and gp.get("text"):
                    ocr_map[fname] = gp["text"]
                    added += 1
        if added:
            log.info("Added %d OCR results from Gemini Pro SOTA benchmark", added)

    return ocr_map


def get_gemini_client():
    """Create Gemini API client."""
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("EXTRACTION_API_KEY")
    if not api_key:
        log.error("No GEMINI_API_KEY or EXTRACTION_API_KEY found")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def run_gemini_ocr(client, image_path: str) -> str | None:
    """Run OCR on an image using Gemini 2.5 Flash API."""
    from google.genai import types

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                        types.Part.from_text(text=OCR_PROMPT),
                    ]
                )
            ],
        )
        text = response.text.strip() if response.text else ""
        return text if text else None
    except Exception as e:
        log.warning("OCR failed for %s: %s", image_path, e)
        return None


def run_gemini_extraction(client, image_path: str) -> dict | None:
    """Extract structured data from image using Gemini 2.5 Pro API."""
    from google.genai import types

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                        types.Part.from_text(text=EXTRACTION_PROMPT),
                    ]
                )
            ],
        )
        text = response.text.strip() if response.text else ""
        if not text:
            return None

        # Parse JSON from response (may have markdown fences)
        return parse_json_response(text)
    except Exception as e:
        log.warning("Extraction failed for %s: %s", image_path, e)
        return None


def parse_json_response(text: str) -> dict | None:
    """Parse JSON from model response, handling markdown fences."""
    # Strip markdown code fences
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def validate_extraction(data: dict) -> list[dict]:
    """Validate extracted data. Returns list of issues."""
    from lab_manager.intake.validator import validate

    return validate(data)


def normalize_vendor_name(name: str | None) -> str | None:
    """Normalize vendor name for deduplication."""
    if not name:
        return None

    name = name.strip()

    # Canonical vendor name mapping (case-insensitive key -> canonical name)
    VENDOR_MAP = {
        "millipore sigma": "MilliporeSigma",
        "milliporesigma": "MilliporeSigma",
        "sigma-aldrich": "MilliporeSigma",
        "sigma-aldrich, inc.": "MilliporeSigma",
        "sigma-aldrich, inc": "MilliporeSigma",
        "sigma aldrich": "MilliporeSigma",
        "sigmaaldrich": "MilliporeSigma",
        "emd millipore": "MilliporeSigma",
        "emd millipore corporation": "MilliporeSigma",
        "merck millipore": "MilliporeSigma",
        "fisher scientific": "Thermo Fisher Scientific",
        "fisher sci": "Thermo Fisher Scientific",
        "thermo fisher scientific": "Thermo Fisher Scientific",
        "thermo fisher": "Thermo Fisher Scientific",
        "thermo scientific": "Thermo Fisher Scientific",
        "thermo fisher scientific chemicals inc.": "Thermo Fisher Scientific",
        "life technologies": "Thermo Fisher Scientific",
        "life technologies corporation": "Thermo Fisher Scientific",
        "invitrogen": "Thermo Fisher Scientific",
        "invitrogen by life technologies": "Thermo Fisher Scientific",
        "gibco": "Thermo Fisher Scientific",
        "bio-rad": "Bio-Rad Laboratories",
        "bio-rad laboratories": "Bio-Rad Laboratories",
        "bio-rad laboratories, inc.": "Bio-Rad Laboratories",
        "bio-rad laboratories, inc": "Bio-Rad Laboratories",
        "biorad": "Bio-Rad Laboratories",
        "biolegend": "BioLegend",
        "biolegend inc": "BioLegend",
        "biolegend, inc.": "BioLegend",
        "biolegend inc.": "BioLegend",
        "abcam": "Abcam",
        "addgene": "Addgene",
        "cell signaling technology": "Cell Signaling Technology",
        "cell signaling": "Cell Signaling Technology",
        "cst": "Cell Signaling Technology",
        "vwr": "VWR International",
        "vwr international": "VWR International",
        "corning": "Corning",
        "corning incorporated": "Corning",
        "corning life sciences": "Corning",
        "new england biolabs": "New England Biolabs",
        "neb": "New England Biolabs",
        "jackson immunoresearch": "Jackson ImmunoResearch",
        "jackson immunoresearch laboratories": "Jackson ImmunoResearch",
        "vector laboratories": "Vector Laboratories",
        "vector labs": "Vector Laboratories",
        "stemcell technologies": "STEMCELL Technologies",
        "r&d systems": "R&D Systems",
        "tocris": "Tocris Bioscience",
        "tocris bioscience": "Tocris Bioscience",
        "santa cruz biotechnology": "Santa Cruz Biotechnology",
        "santa cruz": "Santa Cruz Biotechnology",
        "targetmol": "TargetMol",
        "targetmol chemicals inc.": "TargetMol",
        "targetmol chemicals inc": "TargetMol",
        "medchemexpress": "MedChemExpress",
        "mce": "MedChemExpress",
        "idtdna": "IDT",
        "integrated dna technologies": "IDT",
        "idt": "IDT",
        "genscript": "GenScript",
        "takara bio": "Takara Bio",
        "takara": "Takara Bio",
        "agilent": "Agilent Technologies",
        "agilent technologies": "Agilent Technologies",
        "promega": "Promega",
        "qiagen": "QIAGEN",
        "bd biosciences": "BD Biosciences",
        "bd": "BD Biosciences",
        "beckman coulter": "Beckman Coulter",
        "eppendorf": "Eppendorf",
        "sartorius": "Sartorius",
        "olympus": "Olympus",
        "leica": "Leica Microsystems",
        "leica microsystems": "Leica Microsystems",
    }

    canonical = VENDOR_MAP.get(name.lower())
    if canonical:
        return canonical

    # No match — title-case and strip common suffixes for consistency
    return name


def normalize_doc_type(doc_type: str | None) -> str:
    """Normalize document type to valid enum."""
    if not doc_type:
        return "other"

    valid = {
        "packing_list",
        "invoice",
        "certificate_of_analysis",
        "shipping_label",
        "quote",
        "receipt",
        "mta",
        "other",
    }

    dt = doc_type.lower().strip()
    if dt in valid:
        return dt

    # Common aliases
    aliases = {
        "packing_slip": "packing_list",
        "packing slip": "packing_list",
        "pack_list": "packing_list",
        "package": "packing_list",
        "bill": "invoice",
        "coa": "certificate_of_analysis",
        "certificate": "certificate_of_analysis",
        "cert_of_analysis": "certificate_of_analysis",
        "label": "shipping_label",
        "shipping": "shipping_label",
        "quotation": "quote",
        "material_transfer": "mta",
    }

    return aliases.get(dt, "other")


def update_database(results: list[dict], dry_run: bool = False):
    """Update the database with improved extraction results."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from lab_manager.config import Settings

    settings = Settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Step 1: Update documents with improved OCR + extraction
        updated = 0
        for r in results:
            fname = r["file_name"]
            ocr_text = r.get("ocr_text")
            extraction = r.get("extraction")
            status = r.get("status", "needs_review")

            if not extraction:
                continue

            # Normalize document type
            if "document_type" in extraction:
                extraction["document_type"] = normalize_doc_type(extraction.get("document_type"))

            if dry_run:
                log.info(
                    "[DRY RUN] Would update %s: vendor=%s, type=%s, items=%d",
                    fname,
                    extraction.get("vendor_name", "?"),
                    extraction.get("document_type", "?"),
                    len(extraction.get("items", [])),
                )
                continue

            # Find document by file_name
            row = db.execute(
                text("SELECT id FROM documents WHERE file_name = :fn"),
                {"fn": fname},
            ).fetchone()

            if not row:
                log.warning("Document not found in DB: %s", fname)
                continue

            doc_id = row[0]

            # Update document
            update_fields = {
                "ocr_text": ocr_text,
                "extracted_data": json.dumps(extraction, ensure_ascii=False),
                "extraction_model": "gemini-2.5-pro",
                "extraction_confidence": extraction.get("confidence"),
                "vendor_name": (extraction.get("vendor_name") or "")[:255] or None,
                "document_type": extraction.get("document_type"),
                "status": status,
            }

            set_clause = ", ".join(f"{k} = :{k}" for k in update_fields)
            update_fields["doc_id"] = doc_id

            db.execute(
                text(f"UPDATE documents SET {set_clause} WHERE id = :doc_id"),
                update_fields,
            )
            updated += 1

        if not dry_run:
            db.commit()
            log.info("Updated %d documents in database", updated)

        # Step 2: Rebuild derived tables
        if not dry_run:
            rebuild_derived_tables(db)

    finally:
        db.close()


def rebuild_derived_tables(db):
    """Clear and rebuild orders, items, vendors, products, inventory from documents."""
    from sqlalchemy import text

    log.info("=" * 60)
    log.info("REBUILDING DERIVED TABLES")

    # Count existing records
    for table in ["inventory", "order_items", "orders", "products"]:
        count = db.execute(text(f"SELECT count(*) FROM {table}")).scalar()
        log.info("  %s: %d existing records", table, count)

    # Clear derived tables (order matters for FK constraints)
    log.info("Clearing derived tables...")
    db.execute(text("DELETE FROM consumption_log"))
    db.execute(text("DELETE FROM inventory"))
    db.execute(text("DELETE FROM order_items"))
    db.execute(text("DELETE FROM orders"))
    db.execute(text("DELETE FROM products"))
    # Also clear vendors — rebuild from scratch with normalization
    db.execute(text("DELETE FROM vendors"))
    db.commit()
    log.info("Cleared: consumption_log, inventory, order_items, orders, products, vendors")

    # Get all documents with extracted_data
    docs = db.execute(
        text("""
            SELECT id, file_name, extracted_data, vendor_name
            FROM documents
            WHERE extracted_data IS NOT NULL
            ORDER BY id
        """)
    ).fetchall()

    log.info("Processing %d documents with extracted data", len(docs))

    def trunc(val, maxlen):
        """Truncate string to maxlen if needed."""
        if val and isinstance(val, str) and len(val) > maxlen:
            return val[:maxlen]
        return val

    # Track vendor normalization
    vendor_map: dict[str, int] = {}  # lowercase name -> vendor_id
    product_map: dict[str, int] = {}  # catalog_number -> product_id
    orders_created = 0
    items_created = 0
    inventory_created = 0

    # Load existing vendors
    existing_vendors = db.execute(text("SELECT id, name FROM vendors")).fetchall()
    for vid, vname in existing_vendors:
        vendor_map[vname.strip().lower()] = vid

    # Default location (Room Temperature Shelf)
    default_location = db.execute(text("SELECT id FROM locations WHERE name LIKE '%Room Temp%' LIMIT 1")).scalar()
    if not default_location:
        default_location = db.execute(text("SELECT id FROM locations LIMIT 1")).scalar()

    for doc_id, file_name, extracted_data_raw, doc_vendor_name in docs:
        try:
            data = extracted_data_raw if isinstance(extracted_data_raw, dict) else json.loads(extracted_data_raw)
        except (json.JSONDecodeError, TypeError):
            log.warning("Invalid JSON for doc %d (%s)", doc_id, file_name)
            continue

        if not data:
            continue

        # Resolve vendor (with normalization)
        raw_vendor = data.get("vendor_name") or doc_vendor_name
        vendor_name = normalize_vendor_name(raw_vendor)
        vendor_id = None
        if vendor_name:
            vn_lower = vendor_name.strip().lower()
            if vn_lower in vendor_map:
                vendor_id = vendor_map[vn_lower]
            else:
                # Create new vendor
                new_vid = db.execute(
                    text(
                        "INSERT INTO vendors (name, created_at, updated_at) VALUES (:name, now(), now()) RETURNING id"
                    ),
                    {"name": vendor_name.strip()},
                ).scalar()
                db.flush()
                vendor_map[vn_lower] = new_vid
                vendor_id = new_vid

        # Parse dates safely
        def safe_date(val):
            if not val:
                return None
            try:
                return date.fromisoformat(val)
            except (ValueError, TypeError):
                return None

        # Create order
        order_date = safe_date(data.get("order_date"))
        ship_date = safe_date(data.get("ship_date"))
        received_date = safe_date(data.get("received_date"))

        db.execute(
            text("""
                INSERT INTO orders (
                    po_number, vendor_id, order_date, ship_date,
                    received_date, received_by, status,
                    delivery_number, invoice_number, document_id,
                    created_at, updated_at
                ) VALUES (
                    :po, :vid, :od, :sd,
                    :rd, :rb, :status,
                    :dn, :inv, :did,
                    now(), now()
                )
            """),
            {
                "po": trunc(data.get("po_number"), 100),
                "vid": vendor_id,
                "od": order_date,
                "sd": ship_date,
                "rd": received_date,
                "rb": trunc(data.get("received_by"), 200),
                "status": "received",
                "dn": trunc(data.get("delivery_number"), 100),
                "inv": trunc(data.get("invoice_number"), 100),
                "did": doc_id,
            },
        )
        order_id = db.execute(
            text("""
                SELECT id FROM orders WHERE document_id = :did
                ORDER BY id DESC LIMIT 1
            """),
            {"did": doc_id},
        ).scalar()
        orders_created += 1

        # Create order items + products + inventory
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue

            cat_num = item.get("catalog_number")
            description = item.get("description")
            quantity = item.get("quantity")
            if quantity is None:
                quantity = 1
            unit = item.get("unit")
            lot_number = item.get("lot_number")
            batch_number = item.get("batch_number")
            unit_price = item.get("unit_price")

            # Resolve or create product
            product_id = None
            if cat_num:
                cat_key = cat_num.strip().upper()
                if cat_key in product_map:
                    product_id = product_map[cat_key]
                else:
                    # Create product
                    new_pid = db.execute(
                        text("""
                            INSERT INTO products (
                                catalog_number, name, vendor_id,
                                cas_number, storage_temp, unit,
                                created_at, updated_at
                            ) VALUES (
                                :cn, :name, :vid,
                                :cas, :temp, :unit,
                                now(), now()
                            )
                            RETURNING id
                        """),
                        {
                            "cn": trunc(cat_num.strip(), 100),
                            "name": trunc(description or cat_num.strip(), 500),
                            "vid": vendor_id,
                            "cas": trunc(item.get("cas_number"), 30),
                            "temp": trunc(item.get("storage_temp"), 50),
                            "unit": trunc(unit, 50),
                        },
                    ).scalar()
                    db.flush()
                    product_map[cat_key] = new_pid
                    product_id = new_pid

            # Create order item
            oi_id = db.execute(
                text("""
                    INSERT INTO order_items (
                        order_id, catalog_number, description,
                        quantity, unit, lot_number, batch_number,
                        unit_price, product_id,
                        created_at, updated_at
                    ) VALUES (
                        :oid, :cn, :desc,
                        :qty, :unit, :lot, :batch,
                        :price, :pid,
                        now(), now()
                    )
                    RETURNING id
                """),
                {
                    "oid": order_id,
                    "cn": trunc(cat_num, 100),
                    "desc": trunc(description, 1000),
                    "qty": quantity,
                    "unit": trunc(unit, 50),
                    "lot": trunc(lot_number, 100),
                    "batch": trunc(batch_number, 100),
                    "price": unit_price,
                    "pid": product_id,
                },
            ).scalar()
            db.flush()
            items_created += 1

            # Create inventory record
            if product_id and default_location:
                db.execute(
                    text("""
                        INSERT INTO inventory (
                            product_id, location_id, lot_number,
                            quantity_on_hand, unit, status,
                            received_by, order_item_id,
                            created_at, updated_at
                        ) VALUES (
                            :pid, :lid, :lot,
                            :qty, :unit, :status,
                            :rb, :oiid,
                            now(), now()
                        )
                    """),
                    {
                        "pid": product_id,
                        "lid": default_location,
                        "lot": trunc(lot_number, 100),
                        "qty": quantity,
                        "unit": unit,
                        "status": "available",
                        "rb": data.get("received_by"),
                        "oiid": oi_id,
                    },
                )
                inventory_created += 1

    db.commit()

    log.info("=" * 60)
    log.info("REBUILD COMPLETE")
    log.info("  Orders: %d", orders_created)
    log.info("  Order items: %d", items_created)
    log.info("  Products: %d (deduplicated)", len(product_map))
    log.info("  Vendors: %d total", len(vendor_map))
    log.info("  Inventory: %d", inventory_created)

    # Final counts
    for table in [
        "vendors",
        "products",
        "orders",
        "order_items",
        "inventory",
        "documents",
        "staff",
        "locations",
    ]:
        count = db.execute(text(f"SELECT count(*) FROM {table}")).scalar()
        log.info("  DB %s: %d", table, count)


def main():
    parser = argparse.ArgumentParser(description="Improve Shen Lab database")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--end", type=int, default=None, help="End index")
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Only update OCR text, skip extraction",
    )
    parser.add_argument(
        "--extraction-model",
        default="gemini-2.5-pro",
        help="Model for extraction (default: gemini-2.5-pro)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Concurrent API calls (default: 3)",
    )
    parser.add_argument(
        "--rebuild-only",
        type=str,
        default=None,
        help="Skip extraction, rebuild DB from existing results JSON file",
    )
    args = parser.parse_args()

    # Fast path: rebuild DB from existing extraction results
    if args.rebuild_only:
        log.info("REBUILD-ONLY mode from %s", args.rebuild_only)
        results = json.loads(Path(args.rebuild_only).read_text())
        log.info("Loaded %d results", len(results))
        update_database(results, dry_run=args.dry_run)
        return

    log.info("=" * 60)
    log.info("SHEN LAB DATABASE IMPROVEMENT")
    log.info("  Extraction model: %s", args.extraction_model)
    log.info("  Dry run: %s", args.dry_run)
    log.info("=" * 60)

    # Step 1: Load benchmark OCR results
    ocr_map = load_benchmark_ocr()

    # Step 2: Get list of all document images
    all_images = sorted(SHENLAB_DIR.glob("*.jpg"))
    log.info("Found %d images in shenlab-docs/", len(all_images))

    subset = all_images[args.start : args.end]
    log.info(
        "Processing %d images (index %d-%d)",
        len(subset),
        args.start,
        args.start + len(subset),
    )

    # Step 3: Initialize Gemini client
    client = get_gemini_client()

    # Step 4: Process each image
    results = []
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / f"improve_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    stats = {
        "total": len(subset),
        "ocr_from_benchmark": 0,
        "ocr_fresh": 0,
        "ocr_failed": 0,
        "extraction_ok": 0,
        "extraction_failed": 0,
        "validation_clean": 0,
        "validation_issues": 0,
    }

    for i, img_path in enumerate(subset):
        fname = img_path.name
        idx = args.start + i + 1
        t0 = time.time()
        log.info("[%d/%d] %s", idx, len(all_images), fname)

        result = {"file_name": fname, "image_path": str(img_path)}

        # Get OCR text (prefer benchmark, fallback to fresh API call)
        ocr_text = ocr_map.get(fname)
        if ocr_text:
            result["ocr_source"] = "benchmark_gemini_flash"
            stats["ocr_from_benchmark"] += 1
        else:
            # Use resized image for OCR
            resized = RESIZED_DIR / fname
            img_for_ocr = str(resized) if resized.exists() else str(img_path)
            log.info("  OCR: no benchmark result, running Gemini Flash...")
            ocr_text = run_gemini_ocr(client, img_for_ocr)
            if ocr_text:
                result["ocr_source"] = "fresh_gemini_flash"
                stats["ocr_fresh"] += 1
            else:
                result["ocr_source"] = "failed"
                stats["ocr_failed"] += 1

        result["ocr_text"] = ocr_text
        result["ocr_length"] = len(ocr_text) if ocr_text else 0

        # Extract structured data
        if not args.skip_extraction:
            resized = RESIZED_DIR / fname
            img_for_extract = str(resized) if resized.exists() else str(img_path)
            log.info("  Extracting with %s...", args.extraction_model)

            extraction = run_gemini_extraction(client, img_for_extract)

            if extraction:
                # Validate
                issues = validate_extraction(extraction)
                critical = [i for i in issues if i["severity"] == "critical"]

                result["extraction"] = extraction
                result["validation_issues"] = issues
                result["status"] = "needs_review" if critical else "extracted"
                stats["extraction_ok"] += 1

                if critical:
                    stats["validation_issues"] += 1
                    log.info(
                        "  Extracted: vendor=%s, type=%s, items=%d, ISSUES=%d",
                        extraction.get("vendor_name", "?"),
                        extraction.get("document_type", "?"),
                        len(extraction.get("items", [])),
                        len(critical),
                    )
                else:
                    stats["validation_clean"] += 1
                    log.info(
                        "  Extracted: vendor=%s, type=%s, items=%d ✓",
                        extraction.get("vendor_name", "?"),
                        extraction.get("document_type", "?"),
                        len(extraction.get("items", [])),
                    )
            else:
                result["extraction"] = None
                result["status"] = "needs_review"
                stats["extraction_failed"] += 1
                log.warning("  Extraction FAILED")

            # Rate limit - be nice to API
            elapsed = time.time() - t0
            if elapsed < 2.0:
                time.sleep(2.0 - elapsed)
        else:
            result["status"] = "pending"

        result["elapsed_s"] = round(time.time() - t0, 1)
        results.append(result)

        # Save incrementally (append single result to avoid O(n²) rewrites)
        if len(results) == 1:
            output_file.write_text("[\n" + json.dumps(result, indent=2, default=str, ensure_ascii=False))
        else:
            with open(output_file, "a") as f:
                f.write(",\n" + json.dumps(result, indent=2, default=str, ensure_ascii=False))

        # Progress log every 20 docs
        if (i + 1) % 20 == 0:
            log.info(
                "--- Progress: %d/%d | OK: %d | Fail: %d | Issues: %d ---",
                i + 1,
                len(subset),
                stats["extraction_ok"],
                stats["extraction_failed"],
                stats["validation_issues"],
            )

    # Summary
    total_time = sum(r.get("elapsed_s", 0) for r in results)
    log.info("=" * 60)
    log.info("EXTRACTION COMPLETE in %.0fs (%.1f min)", total_time, total_time / 60)
    log.info("  OCR from benchmark: %d", stats["ocr_from_benchmark"])
    log.info("  OCR fresh calls: %d", stats["ocr_fresh"])
    log.info("  OCR failed: %d", stats["ocr_failed"])
    log.info("  Extraction OK: %d", stats["extraction_ok"])
    log.info("  Extraction failed: %d", stats["extraction_failed"])
    log.info("  Validation clean: %d", stats["validation_clean"])
    log.info("  Validation issues: %d", stats["validation_issues"])

    # Close the JSON array
    if results:
        with open(output_file, "a") as f:
            f.write("\n]")

    # Step 5: Update database
    if results and not args.skip_extraction:
        log.info("=" * 60)
        log.info("UPDATING DATABASE...")
        update_database(results, dry_run=args.dry_run)

    # Save final summary
    summary = {
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "extraction_model": args.extraction_model,
        "stats": stats,
        "total_elapsed_s": round(total_time, 1),
    }
    summary_file = OUTPUT_DIR / f"improve_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary_file.write_text(json.dumps(summary, indent=2))
    log.info("Results saved to %s", output_file)
    log.info("Summary saved to %s", summary_file)


if __name__ == "__main__":
    main()
