#!/usr/bin/env python3
"""Re-extract the 5 docs still using Qwen3-VL + run Flash OCR on 10 missing docs.

Tasks:
1. Gemini 2.5 Pro extraction for 5 Qwen docs (rate-limit failures from improve_database.py)
2. Gemini 2.5 Flash OCR for 10 docs missing benchmark OCR text
3. Update documents table with new ocr_text, extracted_data, extraction_model, status

Usage:
    uv run python scripts/reextract_remaining.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y%m%d_%H%M%S",
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
RESIZED_DIR = PROJECT_ROOT / "shenlab-docs" / "resized"
BENCHMARKS_DIR = PROJECT_ROOT / "benchmarks"
OUTPUT_DIR = PROJECT_ROOT / "pipeline_v2_output"

# --- Prompts (same as improve_database.py) ---

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

OCR_PROMPT = """Transcribe ALL text visible in this scanned document image.
Include every word, number, and symbol exactly as printed or handwritten.
Preserve the general layout with line breaks.
Do NOT add any commentary, headers, or formatting — just the raw text."""


def get_gemini_client():
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("EXTRACTION_API_KEY")
    if not api_key:
        log.error("No GEMINI_API_KEY or EXTRACTION_API_KEY found")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def parse_json_response(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def run_gemini_extraction(client, image_path: str, max_retries: int = 3) -> dict | None:
    from google.genai import types

    for attempt in range(max_retries):
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
                log.warning("  Empty response on attempt %d", attempt + 1)
                continue
            result = parse_json_response(text)
            if result:
                return result
            log.warning("  Failed to parse JSON on attempt %d", attempt + 1)
        except Exception as e:
            log.warning("  Extraction attempt %d failed: %s", attempt + 1, e)
            if "rate" in str(e).lower() or "429" in str(e):
                wait = 30 * (attempt + 1)
                log.info("  Rate limited, waiting %ds...", wait)
                time.sleep(wait)
            else:
                time.sleep(5)
    return None


def run_gemini_ocr(client, image_path: str, max_retries: int = 3) -> str | None:
    from google.genai import types

    for attempt in range(max_retries):
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
            log.warning("  OCR attempt %d failed: %s", attempt + 1, e)
            if "rate" in str(e).lower() or "429" in str(e):
                wait = 30 * (attempt + 1)
                log.info("  Rate limited, waiting %ds...", wait)
                time.sleep(wait)
            else:
                time.sleep(5)
    return None


def normalize_doc_type(doc_type: str | None) -> str:
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
    aliases = {
        "packing_slip": "packing_list",
        "packing slip": "packing_list",
        "bill": "invoice",
        "coa": "certificate_of_analysis",
        "certificate": "certificate_of_analysis",
        "label": "shipping_label",
        "shipping": "shipping_label",
        "quotation": "quote",
        "material_transfer": "mta",
    }
    return aliases.get(dt, "other")


def load_benchmark_ocr_for_files(target_files: set[str]) -> dict[str, str]:
    """Load benchmark OCR text for specific files."""
    ocr_map = {}

    # Flash benchmark
    detail_file = BENCHMARKS_DIR / "ocr_bench_detail_20260314_102147_partial.json"
    api_file = BENCHMARKS_DIR / "ocr_bench_gemini_api_20260314_102147_partial.json"
    if detail_file.exists() and api_file.exists():
        detail = json.loads(detail_file.read_text())
        api_data = json.loads(api_file.read_text())
        for i, entry in enumerate(detail):
            if entry["file_name"] in target_files and i < len(api_data):
                ga = api_data[i]
                if ga.get("success") and ga.get("text"):
                    ocr_map[entry["file_name"]] = ga["text"]

    # Pro benchmark (for any still missing)
    sota_detail_file = BENCHMARKS_DIR / "ocr_bench_detail_20260314_120849_partial.json"
    sota_pro_file = BENCHMARKS_DIR / "ocr_bench_gemini_pro_20260314_120849_partial.json"
    if sota_detail_file.exists() and sota_pro_file.exists():
        detail = json.loads(sota_detail_file.read_text())
        pro_data = json.loads(sota_pro_file.read_text())
        for i, entry in enumerate(detail):
            fn = entry["file_name"]
            if fn in target_files and fn not in ocr_map and i < len(pro_data):
                gp = pro_data[i]
                if gp.get("success") and gp.get("text"):
                    ocr_map[fn] = gp["text"]

    return ocr_map


def main():
    from sqlalchemy import create_engine, text

    from lab_manager.config import Settings

    settings = Settings()
    engine = create_engine(settings.database_url)

    log.info("=" * 60)
    log.info("RE-EXTRACTION OF REMAINING DOCUMENTS")
    log.info("=" * 60)

    # ── Step 1: Find the 5 Qwen docs needing re-extraction ──
    with engine.connect() as conn:
        qwen_rows = conn.execute(
            text("""
            SELECT id, file_name, ocr_text
            FROM documents
            WHERE extraction_model = 'Qwen/Qwen3-VL-4B-Instruct'
            ORDER BY file_name
        """)
        ).fetchall()

    qwen_docs = [(r[0], r[1], r[2]) for r in qwen_rows]
    log.info("Found %d Qwen docs needing Gemini 2.5 Pro extraction", len(qwen_docs))
    for doc_id, fname, _ in qwen_docs:
        log.info("  id=%d %s", doc_id, fname)

    # ── Step 2: Find docs missing benchmark OCR ──
    with engine.connect() as conn:
        all_rows = conn.execute(
            text("""
            SELECT id, file_name, ocr_text
            FROM documents
            ORDER BY file_name
        """)
        ).fetchall()

    all_files = {r[1] for r in all_rows}
    all_file_map = {r[1]: (r[0], r[2]) for r in all_rows}

    # Load benchmark OCR for all files to find which are missing
    benchmark_ocr = load_benchmark_ocr_for_files(all_files)
    missing_ocr_files = all_files - set(benchmark_ocr.keys())
    log.info("Found %d docs missing benchmark OCR text", len(missing_ocr_files))
    for fn in sorted(missing_ocr_files):
        log.info("  %s (id=%d)", fn, all_file_map[fn][0])

    # ── Step 3: Initialize Gemini client ──
    client = get_gemini_client()

    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = OUTPUT_DIR / f"reextract_{ts}.json"
    results = []

    # ── Step 4: Run Gemini Flash OCR on the 10 missing docs ──
    log.info("=" * 60)
    log.info("PHASE 1: Gemini Flash OCR for %d missing docs", len(missing_ocr_files))
    log.info("=" * 60)

    ocr_updates = {}  # file_name -> ocr_text (fresh)
    for i, fname in enumerate(sorted(missing_ocr_files)):
        doc_id = all_file_map[fname][0]
        resized_path = RESIZED_DIR / fname
        if not resized_path.exists():
            log.warning("  Resized image not found: %s", resized_path)
            continue

        log.info("[OCR %d/%d] %s (id=%d)", i + 1, len(missing_ocr_files), fname, doc_id)
        t0 = time.time()
        ocr_text = run_gemini_ocr(client, str(resized_path))
        elapsed = time.time() - t0

        if ocr_text:
            ocr_updates[fname] = ocr_text
            log.info("  OK: %d chars in %.1fs", len(ocr_text), elapsed)
        else:
            log.warning("  FAILED after retries")

        # Rate limit
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

    log.info("OCR complete: %d/%d successful", len(ocr_updates), len(missing_ocr_files))

    # Update OCR text in DB for the 10 missing docs
    if ocr_updates:
        with engine.begin() as conn:
            for fname, ocr_text in ocr_updates.items():
                doc_id = all_file_map[fname][0]
                conn.execute(
                    text("""
                    UPDATE documents SET ocr_text = :ocr, updated_at = now()
                    WHERE id = :did
                """),
                    {"ocr": ocr_text, "did": doc_id},
                )
                log.info(
                    "  Updated OCR for id=%d %s (%d chars)",
                    doc_id,
                    fname,
                    len(ocr_text),
                )
        log.info("OCR text updated in DB for %d docs", len(ocr_updates))

    # ── Step 5: Run Gemini 2.5 Pro extraction on the 5 Qwen docs ──
    log.info("=" * 60)
    log.info("PHASE 2: Gemini 2.5 Pro extraction for %d Qwen docs", len(qwen_docs))
    log.info("=" * 60)

    # Also load benchmark OCR for these 5 to replace Qwen OCR
    qwen_fnames = {d[1] for d in qwen_docs}
    qwen_benchmark_ocr = load_benchmark_ocr_for_files(qwen_fnames)

    extraction_results = []
    for i, (doc_id, fname, old_ocr) in enumerate(qwen_docs):
        resized_path = RESIZED_DIR / fname
        if not resized_path.exists():
            log.warning("  Resized image not found: %s", resized_path)
            continue

        log.info("[Extract %d/%d] %s (id=%d)", i + 1, len(qwen_docs), fname, doc_id)
        t0 = time.time()

        extraction = run_gemini_extraction(client, str(resized_path))
        elapsed = time.time() - t0

        # Get best available OCR text
        ocr_text = qwen_benchmark_ocr.get(fname) or ocr_updates.get(fname) or old_ocr

        if extraction:
            # Normalize document type
            if "document_type" in extraction:
                extraction["document_type"] = normalize_doc_type(extraction.get("document_type"))

            # Validate
            try:
                from lab_manager.intake.validator import validate

                issues = validate(extraction)
                critical = [iss for iss in issues if iss["severity"] == "critical"]
            except Exception:
                issues = []
                critical = []

            status = "needs_review" if critical else "extracted"

            result = {
                "doc_id": doc_id,
                "file_name": fname,
                "extraction": extraction,
                "ocr_text_len": len(ocr_text) if ocr_text else 0,
                "ocr_source": "benchmark" if fname in qwen_benchmark_ocr else "existing",
                "validation_issues": len(issues),
                "critical_issues": len(critical),
                "status": status,
                "elapsed_s": round(elapsed, 1),
            }
            extraction_results.append(result)
            results.append(result)

            log.info(
                "  OK: vendor=%s, type=%s, items=%d, status=%s in %.1fs",
                extraction.get("vendor_name", "?"),
                extraction.get("document_type", "?"),
                len(extraction.get("items", [])),
                status,
                elapsed,
            )

            # Update DB immediately
            with engine.begin() as conn:
                conn.execute(
                    text("""
                    UPDATE documents SET
                        ocr_text = :ocr,
                        extracted_data = :ext,
                        extraction_model = 'gemini-2.5-pro',
                        extraction_confidence = :conf,
                        vendor_name = :vendor,
                        document_type = :dtype,
                        status = :status,
                        updated_at = now()
                    WHERE id = :did
                """),
                    {
                        "ocr": ocr_text,
                        "ext": json.dumps(extraction, ensure_ascii=False),
                        "conf": extraction.get("confidence"),
                        "vendor": extraction.get("vendor_name"),
                        "dtype": extraction.get("document_type"),
                        "status": status,
                        "did": doc_id,
                    },
                )
            log.info("  DB updated for id=%d", doc_id)
        else:
            log.error("  EXTRACTION FAILED for %s after all retries", fname)
            results.append(
                {
                    "doc_id": doc_id,
                    "file_name": fname,
                    "extraction": None,
                    "status": "needs_review",
                    "elapsed_s": round(elapsed, 1),
                }
            )

        # Rate limit between extractions
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)

    # Save results
    results_file.write_text(json.dumps(results, indent=2, default=str, ensure_ascii=False))
    log.info("Results saved to %s", results_file)

    # ── Step 6: Final verification ──
    log.info("=" * 60)
    log.info("VERIFICATION")
    log.info("=" * 60)

    with engine.connect() as conn:
        # Check Qwen docs are gone
        qwen_count = conn.execute(
            text("SELECT count(*) FROM documents WHERE extraction_model = 'Qwen/Qwen3-VL-4B-Instruct'")
        ).scalar()
        log.info("Remaining Qwen docs: %d (should be 0)", qwen_count)

        # Check NULL OCR text
        null_ocr = conn.execute(text("SELECT count(*) FROM documents WHERE ocr_text IS NULL")).scalar()
        log.info("Docs with NULL OCR text: %d", null_ocr)

        # Status distribution
        rows = conn.execute(
            text("""
            SELECT status, extraction_model, count(*)
            FROM documents
            GROUP BY status, extraction_model
            ORDER BY status, extraction_model
        """)
        ).fetchall()
        log.info("Status distribution:")
        for r in rows:
            log.info("  status=%s model=%s count=%d", r[0], r[1], r[2])

        # Total
        total = conn.execute(text("SELECT count(*) FROM documents")).scalar()
        log.info("Total documents: %d", total)

    log.info("=" * 60)
    log.info("DONE")


if __name__ == "__main__":
    main()
