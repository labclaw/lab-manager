#!/usr/bin/env python3
"""LabClaw Pipeline v2: OCR → 3 VLM CLI reviews → Consensus → Human.

Stage 0: OCR (Qwen3-VL / Gemini Flash / etc — configurable)
Stage 1: 3 SOTA VLMs extract from images in parallel
         - Claude Code (Opus 4.6)
         - Gemini CLI (3.1 Pro)
         - Codex (GPT-5.4)
Stage 2: Consensus merge (3/3→done, 2/3→majority auto-fix, 0/3→human)
Stage 3: Cross-model review — each model checks merged result
Stage 4: Validation rules
Stage 5: Human review queue (only unresolved conflicts)

Usage:
    # Full pipeline on first 5 docs
    python scripts/pipeline_v2.py data/ocr-output/all_scans.json --end 5

    # Skip cross-model review (faster)
    python scripts/pipeline_v2.py data/ocr-output/all_scans.json --no-review --end 10

    # Use different VLM providers
    python scripts/pipeline_v2.py ... --vlms opus_4_6,gemini_3_1_pro
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Set up path for imports before importing lab_manager
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from lab_manager.intake.prompts import EXTRACTION_PROMPT  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y%m%d_%H%M%S",
)
log = logging.getLogger(__name__)

OUTPUT_DIR = PROJECT_ROOT / "pipeline_v2_output"


def get_default_vlm_providers():
    """Get the 3 SOTA VLM providers."""
    from lab_manager.intake.providers.claude import ClaudeProvider
    from lab_manager.intake.providers.gemini import GeminiProvider
    from lab_manager.intake.providers.codex import CodexProvider

    return [ClaudeProvider(), GeminiProvider(), CodexProvider()]


def get_vlm_providers(names: list[str]):
    """Get VLM providers by name."""
    from lab_manager.intake.providers.more_ocr import get_provider, VLM_PROVIDERS

    return [get_provider(n, VLM_PROVIDERS) for n in names]


def process_one(
    entry: dict,
    doc_index: int,
    total: int,
    vlm_providers: list,
    do_review: bool = True,
) -> dict:
    """Process a single document through the full v2 pipeline."""
    from lab_manager.intake.consensus import (
        extract_parallel,
        consensus_merge,
        cross_model_review,
    )
    from lab_manager.intake.validator import validate

    file_name = entry["file"]
    ocr_text = entry.get("fullText", "")
    image_path = str(PROJECT_ROOT / "data" / file_name)

    result = {
        "file_name": file_name,
        "image_path": image_path,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "stages": {},
    }

    log.info("[%d/%d] %s", doc_index, total, file_name)

    if not Path(image_path).exists():
        log.warning("  Image not found: %s", image_path)
        result["status"] = "image_not_found"
        return result

    # Stage 0: OCR (already done, from JSON)
    result["stages"]["ocr"] = {
        "model": entry.get("model", "unknown"),
        "text_length": len(ocr_text),
        "elapsed_s": entry.get("elapsed_s"),
    }

    if not ocr_text or ocr_text.strip() == "(No text detected)":
        result["status"] = "empty"
        return result

    # Stage 1: Multi-VLM extraction (parallel)
    t0 = time.time()
    log.info("  Stage 1: %d VLMs extracting...", len(vlm_providers))
    extractions = extract_parallel(vlm_providers, image_path, EXTRACTION_PROMPT)
    stage1_time = time.time() - t0

    success_count = sum(1 for v in extractions.values() if v is not None)
    result["stages"]["extraction"] = {
        "elapsed_s": round(stage1_time, 1),
        "models_succeeded": success_count,
        "models_total": len(vlm_providers),
        "per_model": {
            model: {"success": data is not None} for model, data in extractions.items()
        },
    }
    log.info(
        "  Stage 1: %d/%d succeeded (%.1fs)",
        success_count,
        len(vlm_providers),
        stage1_time,
    )

    # Stage 2: Consensus merge
    t0 = time.time()
    merged = consensus_merge(extractions)
    stage2_time = time.time() - t0

    result["stages"]["consensus"] = {
        "elapsed_s": round(stage2_time, 2),
        "needs_human": merged.get("_needs_human", False),
        "model_count": merged.get("_model_count", 0),
    }

    # Stage 3: Cross-model review
    if do_review and success_count >= 2:
        t0 = time.time()
        log.info("  Stage 3: Cross-model review...")
        reviewed = cross_model_review(vlm_providers, image_path, merged, ocr_text)
        stage3_time = time.time() - t0

        corrections = reviewed.get("_review_round", {}).get("corrections_applied", [])
        result["stages"]["review"] = {
            "elapsed_s": round(stage3_time, 1),
            "corrections": corrections,
        }
        log.info("  Stage 3: %d corrections (%.1fs)", len(corrections), stage3_time)
        merged = reviewed
    else:
        result["stages"]["review"] = {"skipped": True}

    # Stage 4: Validation
    clean_data = {k: v for k, v in merged.items() if not k.startswith("_")}
    issues = validate(clean_data)

    result["stages"]["validation"] = {
        "issues": issues,
        "critical_count": sum(1 for i in issues if i["severity"] == "critical"),
    }

    # Final status
    needs_human = merged.get("_needs_human", False) or any(
        i["severity"] == "critical" for i in issues
    )
    result["final_extraction"] = clean_data
    result["needs_human"] = needs_human
    # Document status: needs_review if _needs_human, else extracted
    result["document_status"] = "needs_review" if needs_human else "extracted"
    result["status"] = "needs_human" if needs_human else "auto_resolved"
    result["_consensus_details"] = merged.get("_consensus", {})

    log.info("  -> %s", result["status"])
    return result


def main():
    parser = argparse.ArgumentParser(description="LabClaw Pipeline v2")
    parser.add_argument("ocr_json", help="Path to OCR results JSON")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument(
        "--no-review", action="store_true", help="Skip cross-model review"
    )
    parser.add_argument(
        "--vlms",
        default=None,
        help="Comma-separated VLM names (default: opus_4_6,gemini_3_1_pro,gpt_5_4)",
    )
    args = parser.parse_args()

    # Load VLM providers
    if args.vlms:
        vlm_names = [n.strip() for n in args.vlms.split(",")]
        vlm_providers = get_vlm_providers(vlm_names)
    else:
        vlm_providers = get_default_vlm_providers()

    log.info("VLM providers: %s", [p.name for p in vlm_providers])

    # Load OCR data
    results_path = Path(args.ocr_json)
    all_entries = json.loads(results_path.read_text())
    subset = all_entries[args.start : args.end]
    total = len(all_entries)

    log.info("Processing %d/%d documents", len(subset), total)
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_results = []
    stats = {"auto_resolved": 0, "needs_human": 0, "empty": 0, "image_not_found": 0}
    t_start = time.time()

    for i, entry in enumerate(subset, args.start + 1):
        t0 = time.time()
        result = process_one(
            entry, i, total, vlm_providers, do_review=not args.no_review
        )
        result["total_elapsed_s"] = round(time.time() - t0, 1)

        stats[result["status"]] = stats.get(result["status"], 0) + 1
        all_results.append(result)

        # Save incrementally
        out_path = OUTPUT_DIR / f"results_{args.start}_{args.start + len(subset)}.json"
        out_path.write_text(
            json.dumps(all_results, indent=2, default=str, ensure_ascii=False)
        )

    total_time = time.time() - t_start

    log.info("=" * 60)
    log.info("PIPELINE V2 COMPLETE in %.0fs (%.1f min)", total_time, total_time / 60)
    log.info("Results: %s", json.dumps(stats, indent=2))
    log.info(
        "Human review: %d/%d (%.1f%%)",
        stats.get("needs_human", 0),
        len(subset),
        stats.get("needs_human", 0) / max(len(subset), 1) * 100,
    )

    # Save summary
    summary = {
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "pipeline": "v2",
        "vlm_models": [p.model_id for p in vlm_providers],
        "total_docs": len(subset),
        "stats": stats,
        "elapsed_s": round(total_time, 1),
    }
    (OUTPUT_DIR / f"summary_{args.start}_{args.start + len(subset)}.json").write_text(
        json.dumps(summary, indent=2)
    )


if __name__ == "__main__":
    main()
