#!/usr/bin/env python3
"""Batch ingest documents: OCR → 3-model extraction → consensus → DB.

Usage:
    DATABASE_URL=... NVIDIA_BUILD_API_KEY=... uv run python scripts/batch_ingest.py

Quality-first pipeline:
1. OCR: NVIDIA Llama-3.2-90b-vision (best quality, 4/4 field accuracy)
2. Extraction: 3 models in sequence (GLM-5, Qwen3.5-397b, Llama-3.3-70b)
3. Consensus merge: 2/3 agree = auto, all disagree = human review
4. Validation: rule-based checks (vendor name, doc type, quantities, lot numbers)
5. DB insert: document + extracted data + consensus metadata
6. JSON log: per-document results for benchmark analysis
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lab_manager.intake.prompts import EXTRACTION_PROMPT, OCR_PROMPT  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("batch_ingest")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DOCS_DIR = Path(
    os.environ.get(
        "DOCS_DIR", str(Path(__file__).resolve().parent.parent / "data" / "resized")
    )
)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "batch_ingest"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NVIDIA_KEY = os.environ.get("NVIDIA_BUILD_API_KEY") or os.environ.get(
    "NVIDIA_API_KEY", ""
)
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

OCR_MODEL = "meta/llama-3.2-90b-vision-instruct"
EXTRACT_MODELS = [
    ("glm5", "z-ai/glm5"),
    ("qwen3.5", "qwen/qwen3.5-397b-a17b"),
    ("llama3.3", "meta/llama-3.3-70b-instruct"),
]

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds base delay (exponential backoff)
RATE_LIMIT_DELAY = 10  # seconds between docs to avoid 429


# ---------------------------------------------------------------------------
# NVIDIA API helpers
# ---------------------------------------------------------------------------


def _nvidia_call(payload: dict, timeout: int = 120) -> str:
    """Call NVIDIA NIM API with retry and backoff."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {NVIDIA_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                delay = RETRY_DELAY * (2**attempt)
                log.warning(
                    "Rate limited, waiting %ds (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
                continue
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2**attempt)
                log.warning("Connection error, retrying in %ds: %s", delay, e)
                time.sleep(delay)
                continue
            raise
    raise RuntimeError(f"NVIDIA API failed after {MAX_RETRIES} retries")


MAX_IMAGE_SIZE_MB = 50


def ocr_image(image_path: Path) -> str:
    """OCR a document image using NVIDIA vision model."""
    file_size = image_path.stat().st_size
    if file_size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise RuntimeError(
            f"Image too large: {file_size / 1024 / 1024:.0f}MB > {MAX_IMAGE_SIZE_MB}MB limit"
        )
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    suffix = image_path.suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

    return _nvidia_call(
        {
            "model": OCR_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                        {"type": "text", "text": OCR_PROMPT},
                    ],
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        },
        timeout=180,
    )


def extract_text(model_id: str, ocr_text: str) -> dict | None:
    """Extract structured data from OCR text using a text model."""
    extraction_schema = json.dumps(
        {
            "vendor_name": "string|null",
            "document_type": "packing_list|invoice|certificate_of_analysis|shipping_label|quote|receipt|mta|other",
            "po_number": "string|null",
            "order_number": "string|null",
            "invoice_number": "string|null",
            "delivery_number": "string|null",
            "order_date": "YYYY-MM-DD|null",
            "ship_date": "YYYY-MM-DD|null",
            "received_date": "YYYY-MM-DD|null",
            "received_by": "string|null",
            "items": [
                {
                    "catalog_number": "string|null",
                    "description": "string",
                    "quantity": "number|null",
                    "unit": "string|null",
                    "lot_number": "string|null",
                    "batch_number": "string|null",
                    "unit_price": "number|null",
                }
            ],
            "confidence": "0.0-1.0",
        },
        indent=2,
    )

    prompt = f"""{EXTRACTION_PROMPT}

Return ONLY valid JSON matching this schema (no markdown, no extra text):
{extraction_schema}

---
OCR TEXT:
{ocr_text}"""

    try:
        raw = _nvidia_call(
            {
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2048,
                "temperature": 0.1,
            },
            timeout=60,
        )

        # Parse JSON from response
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
        log.warning("Failed to parse JSON from %s", model_id)
        return None
    except Exception as e:
        log.warning("Extraction failed (%s): %s", model_id, e)
        return None


# ---------------------------------------------------------------------------
# Consensus (simplified from consensus.py for text-only models)
# ---------------------------------------------------------------------------


def consensus_merge(extractions: dict[str, dict | None]) -> dict:
    """Merge 3 model extractions using majority voting."""
    valid = {k: v for k, v in extractions.items() if v is not None}
    if not valid:
        return {"_error": "all_models_failed", "_needs_human": True}

    if len(valid) == 1:
        model, data = next(iter(valid.items()))
        result = dict(data)
        result["_consensus"] = "single_model"
        result["_needs_human"] = True
        return result

    # Collect all fields
    all_fields = set()
    for data in valid.values():
        all_fields.update(data.keys())

    merged = {}
    agreements = {}

    for field in sorted(all_fields):
        if field.startswith("_"):
            continue

        values = {m: d.get(field) for m, d in valid.items()}
        unique = {}
        for m, v in values.items():
            key = (
                json.dumps(v, sort_keys=True, default=str) if v is not None else "null"
            )
            unique.setdefault(key, []).append(m)

        if len(unique) == 1:
            # All agree
            merged[field] = next(iter(values.values()))
            agreements[field] = "unanimous"
        else:
            # Find majority
            best_key = max(unique, key=lambda k: len(unique[k]))
            best_models = unique[best_key]
            if len(best_models) >= 2:
                merged[field] = values[best_models[0]]
                agreements[field] = f"majority({','.join(best_models)})"
            else:
                # No majority — use first valid model (priority: glm5 > qwen > llama)
                for m in ["glm5", "qwen3.5", "llama3.3"]:
                    if m in values and values[m] is not None:
                        merged[field] = values[m]
                        break
                agreements[field] = "no_consensus"

    needs_human = any(a == "no_consensus" for a in agreements.values())
    merged["_agreements"] = agreements
    merged["_needs_human"] = needs_human
    merged["_model_count"] = len(valid)
    merged["_models"] = list(valid.keys())
    return merged


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate(data: dict) -> list[str]:
    """Quick validation checks on extracted data."""
    issues = []
    vendor = data.get("vendor_name", "")
    if vendor and len(vendor) > 100:
        issues.append(f"vendor_name too long ({len(vendor)} chars)")
    if vendor and any(
        w in vendor.lower()
        for w in ["blvd", "street", "suite", "avenue", "dr.", "road"]
    ):
        issues.append("vendor_name looks like an address")

    doc_type = data.get("document_type", "")
    valid_types = {
        "packing_list",
        "invoice",
        "certificate_of_analysis",
        "shipping_label",
        "quote",
        "receipt",
        "mta",
        "other",
    }
    if doc_type and doc_type not in valid_types:
        issues.append(f"invalid document_type: {doc_type}")

    for item in data.get("items", []):
        qty = item.get("quantity")
        if qty is not None and qty < 0:
            issues.append(f"negative quantity: {qty}")
        lot = item.get("lot_number", "")
        if lot and lot.upper().startswith("VCAT"):
            issues.append(f"lot_number looks like VCAT code: {lot}")

    return issues


# ---------------------------------------------------------------------------
# DB insert
# ---------------------------------------------------------------------------


def insert_document(
    image_path: Path, ocr_text: str, merged: dict, issues: list[str]
) -> int | None:
    """Insert document into the database."""
    try:
        from lab_manager.database import get_session_factory
        from lab_manager.models.document import Document, DocumentStatus

        factory = get_session_factory()
        db = factory()

        # Determine status
        needs_human = merged.get("_needs_human", False)
        has_issues = len(issues) > 0
        status = (
            DocumentStatus.needs_review
            if (needs_human or has_issues)
            else DocumentStatus.processed
        )

        # Clean merged data for storage (remove _ prefixed keys)
        extracted_data = {k: v for k, v in merged.items() if not k.startswith("_")}

        doc = Document(
            file_path=str(image_path),
            file_name=image_path.name,
            ocr_text=ocr_text,
            extracted_data=extracted_data,
            vendor_name=merged.get("vendor_name"),
            document_type=merged.get("document_type"),
            extraction_model=f"consensus({','.join(merged.get('_models', []))})",
            extraction_confidence=merged.get("confidence"),
            status=status,
            review_notes="; ".join(issues) if issues else None,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id
        db.close()
        return doc_id
    except Exception as e:
        log.error("DB insert failed for %s: %s", image_path.name, e)
        db.close()
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def process_one(image_path: Path) -> dict:
    """Process a single document through full pipeline."""
    result: dict[str, Any] = {
        "file": image_path.name,
        "timestamp": datetime.now().isoformat(),
        "ocr_model": OCR_MODEL,
        "ocr_text": "",
        "ocr_length": 0,
        "extractions": {},
        "consensus": {},
        "validation_issues": [],
        "db_id": None,
        "status": "pending",
    }

    # Step 1: OCR
    t0 = time.time()
    try:
        ocr_text = ocr_image(image_path)
        result["ocr_text"] = ocr_text
        result["ocr_length"] = len(ocr_text)
        result["ocr_time"] = round(time.time() - t0, 1)
    except Exception as e:
        result["status"] = "ocr_failed"
        result["error"] = str(e)[:200]
        result["ocr_time"] = round(time.time() - t0, 1)
        return result

    if not ocr_text or len(ocr_text) < 20:
        result["status"] = "ocr_empty"
        return result

    # Step 2: Multi-model extraction (sequential to avoid rate limits)
    extractions = {}
    for model_name, model_id in EXTRACT_MODELS:
        t1 = time.time()
        extracted = extract_text(model_id, ocr_text)
        extractions[model_name] = extracted
        result["extractions"][model_name] = {
            "data": extracted,
            "time": round(time.time() - t1, 1),
            "success": extracted is not None,
        }
        time.sleep(1)  # Small delay between models

    # Step 3: Consensus merge
    merged = consensus_merge(extractions)
    result["consensus"] = {k: v for k, v in merged.items() if k.startswith("_")}

    # Step 4: Validation
    issues = validate(merged)
    result["validation_issues"] = issues

    # Step 5: DB insert
    doc_id = insert_document(image_path, ocr_text, merged, issues)
    result["db_id"] = doc_id
    result["status"] = "ok" if doc_id else "db_failed"
    result["total_time"] = round(time.time() - t0, 1)

    return result


def main():
    if not NVIDIA_KEY:
        print("ERROR: Set NVIDIA_BUILD_API_KEY or NVIDIA_API_KEY")
        sys.exit(1)

    # Collect all images
    images = sorted(DOCS_DIR.glob("*.jpg"))
    if not images:
        print(f"ERROR: No images found in {DOCS_DIR}")
        sys.exit(1)

    # Check which are already in DB
    already_done = set()
    try:
        from lab_manager.database import get_session_factory
        from lab_manager.models.document import Document
        from sqlmodel import select

        factory = get_session_factory()
        db = factory()
        existing = db.scalars(select(Document.file_name)).all()
        already_done = set(existing)
        db.close()
        log.info("Found %d documents already in DB", len(already_done))
    except Exception as e:
        log.warning("Could not check existing docs: %s", e)

    # Filter out already processed
    todo = [img for img in images if img.name not in already_done]
    log.info(
        "Total images: %d, already done: %d, to process: %d",
        len(images),
        len(already_done),
        len(todo),
    )

    if not todo:
        log.info("All documents already processed!")
        return

    # Process
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = OUTPUT_DIR / f"ingest_{timestamp}.jsonl"
    summary = {
        "total": len(todo),
        "ok": 0,
        "ocr_failed": 0,
        "db_failed": 0,
        "errors": [],
    }

    log.info("Starting batch ingest: %d docs → %s", len(todo), log_file)
    log.info("OCR: %s | Extract: %s", OCR_MODEL, [m[0] for m in EXTRACT_MODELS])

    t_start = time.time()
    for i, img in enumerate(todo):
        elapsed = time.time() - t_start
        eta = (elapsed / max(i, 1)) * (len(todo) - i)
        log.info(
            "[%d/%d] Processing %s (ETA: %dm%ds)",
            i + 1,
            len(todo),
            img.name,
            int(eta // 60),
            int(eta % 60),
        )

        result = process_one(img)

        # Write to JSONL log
        with open(log_file, "a") as f:
            # Don't write full OCR text to log (too large)
            log_entry = {k: v for k, v in result.items() if k != "ocr_text"}
            log_entry["ocr_preview"] = (result.get("ocr_text", "") or "")[:200]
            f.write(json.dumps(log_entry, default=str) + "\n")

        # Update summary
        summary[result["status"]] = summary.get(result["status"], 0) + 1
        if result["status"] == "ok":
            summary["ok"] += 1
            log.info(
                "  → OK (db=%s, vendor=%s, type=%s, consensus=%d models)",
                result["db_id"],
                (
                    result.get("extractions", {}).get("glm5", {}).get("data", {}) or {}
                ).get("vendor_name", "?"),
                (
                    result.get("extractions", {}).get("glm5", {}).get("data", {}) or {}
                ).get("document_type", "?"),
                result.get("consensus", {}).get("_model_count", 0),
            )
        else:
            log.warning("  → %s: %s", result["status"], result.get("error", "")[:100])

        # Rate limit protection
        time.sleep(RATE_LIMIT_DELAY)

    # Final summary
    total_time = time.time() - t_start
    summary["total_time"] = f"{int(total_time // 60)}m{int(total_time % 60)}s"

    log.info("=" * 60)
    log.info("BATCH INGEST COMPLETE")
    log.info("=" * 60)
    log.info(
        "Total: %d | OK: %d | OCR failed: %d | DB failed: %d",
        summary["total"],
        summary["ok"],
        summary.get("ocr_failed", 0),
        summary.get("db_failed", 0),
    )
    log.info("Time: %s | Log: %s", summary["total_time"], log_file)

    # Write summary
    with open(OUTPUT_DIR / f"summary_{timestamp}.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
