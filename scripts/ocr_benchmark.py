#!/usr/bin/env python3
"""OCR Model Benchmark: compare multiple OCR models on our scan dataset.

Tests each OCR provider on a sample (or all) of the 279 scanned documents.
Measures: text quality, extraction accuracy, speed, and cost.

Usage:
    # Compare 3 CLI-based models on first 10 docs
    python scripts/ocr_benchmark.py --models claude_sonnet,gemini_flash,codex_gpt --sample 10

    # Compare all available models on full dataset
    python scripts/ocr_benchmark.py --models all --sample 0

    # Compare specific vLLM models (must have server running)
    python scripts/ocr_benchmark.py --models qwen3_vl,deepseek_vl,glm_4v --sample 20
"""

from __future__ import annotations

import argparse
import json
import logging
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
SCANS_DIR = PROJECT_ROOT / "shenlab-docs"
OCR_JSON = PROJECT_ROOT / "shenlab-docs" / "ocr-output" / "all_scans_qwen3_vl_v2.json"
OUTPUT_DIR = PROJECT_ROOT / "benchmarks"


def get_available_models() -> dict:
    """Return dict of model_name -> description for available OCR models."""
    return {
        # CLI-based (no server needed)
        "claude_sonnet": "Claude Sonnet 4.6 via CLI",
        "gemini_flash": "Gemini 3.1 Flash via CLI",
        "codex_gpt": "GPT-5.4 via Codex CLI",
        # API-based
        "gemini_api": "Gemini 3.1 Flash via API",
        "mistral_pixtral": "Mistral Pixtral Large via API",
        # Local vLLM (need running server)
        "qwen3_vl": "Qwen3-VL-4B via vLLM",
        "deepseek_vl": "DeepSeek-VL2 via vLLM",
        "glm_4v": "GLM-4V via vLLM",
        # Local standalone
        "paddleocr": "PaddleOCR (local)",
    }


def load_ground_truth() -> dict[str, dict]:
    """Load existing OCR + extraction as reference baseline."""
    data = json.loads(OCR_JSON.read_text())
    return {entry["file"]: entry for entry in data}


def run_single_ocr(provider, image_path: str) -> dict:
    """Run one OCR model on one image and measure results."""
    t0 = time.time()
    try:
        text = provider.extract_text(image_path)
        elapsed = time.time() - t0
        return {
            "success": True,
            "text": text,
            "text_length": len(text) if text else 0,
            "line_count": len(text.split("\n")) if text else 0,
            "elapsed_s": round(elapsed, 2),
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "success": False,
            "error": str(e),
            "text": "",
            "text_length": 0,
            "elapsed_s": round(elapsed, 2),
        }


def compute_similarity(text_a: str, text_b: str) -> float:
    """Compute word-level Jaccard similarity between two texts."""
    if not text_a or not text_b:
        return 0.0
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a and not words_b:
        return 1.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


def main():
    parser = argparse.ArgumentParser(description="OCR Model Benchmark")
    parser.add_argument(
        "--models",
        default="claude_sonnet,gemini_flash,codex_gpt",
        help="Comma-separated model names, or 'all'",
    )
    parser.add_argument(
        "--sample", type=int, default=10, help="Number of docs to test (0=all)"
    )
    parser.add_argument(
        "--parallel", type=int, default=1, help="Parallel docs per model"
    )
    args = parser.parse_args()

    available = get_available_models()

    if args.models == "all":
        model_names = list(available.keys())
    else:
        model_names = [m.strip() for m in args.models.split(",")]

    # Load reference data
    ground_truth = load_ground_truth()
    all_files = sorted(ground_truth.keys())

    if args.sample > 0:
        # Sample evenly across dataset
        step = max(1, len(all_files) // args.sample)
        test_files = all_files[::step][: args.sample]
    else:
        test_files = all_files

    log.info(
        "Benchmarking %d models on %d documents", len(model_names), len(test_files)
    )
    log.info("Models: %s", model_names)

    # Instantiate providers
    from lab_manager.intake.providers.more_ocr import get_provider, OCR_PROVIDERS

    providers = {}
    for name in model_names:
        try:
            providers[name] = get_provider(name, OCR_PROVIDERS)
            log.info("  Loaded: %s (%s)", name, available.get(name, "unknown"))
        except Exception as e:
            log.warning("  SKIP %s: %s", name, e)

    if not providers:
        log.error("No providers available!")
        return

    # Run benchmark
    results = {name: [] for name in providers}
    OUTPUT_DIR.mkdir(exist_ok=True)

    for i, file_name in enumerate(test_files, 1):
        image_path = str(SCANS_DIR / file_name)
        if not Path(image_path).exists():
            log.warning("[%d/%d] Image not found: %s", i, len(test_files), file_name)
            continue

        log.info("[%d/%d] %s", i, len(test_files), file_name)
        ref_text = ground_truth[file_name].get("fullText", "")

        for name, provider in providers.items():
            log.info("  %s...", name)
            result = run_single_ocr(provider, image_path)
            result["file_name"] = file_name
            result["similarity_to_qwen"] = compute_similarity(result["text"], ref_text)
            results[name].append(result)
            log.info(
                "    -> %s, %d chars, %.2fs, sim=%.2f",
                "OK" if result["success"] else "FAIL",
                result["text_length"],
                result["elapsed_s"],
                result["similarity_to_qwen"],
            )

    # Aggregate stats
    summary = {
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "test_files": len(test_files),
        "models": {},
    }

    for name, model_results in results.items():
        successes = [r for r in model_results if r["success"]]
        summary["models"][name] = {
            "model_id": providers[name].model_id,
            "total": len(model_results),
            "success": len(successes),
            "fail": len(model_results) - len(successes),
            "avg_text_length": round(
                sum(r["text_length"] for r in successes) / max(len(successes), 1)
            ),
            "avg_elapsed_s": round(
                sum(r["elapsed_s"] for r in successes) / max(len(successes), 1), 2
            ),
            "avg_similarity_to_qwen": round(
                sum(r["similarity_to_qwen"] for r in successes)
                / max(len(successes), 1),
                3,
            ),
            "total_elapsed_s": round(sum(r["elapsed_s"] for r in model_results), 1),
        }

    # Print leaderboard
    log.info("=" * 70)
    log.info("OCR BENCHMARK RESULTS (%d docs)", len(test_files))
    log.info("%-20s %6s %8s %8s %10s", "Model", "OK", "AvgLen", "AvgTime", "Similarity")
    log.info("-" * 70)
    for name, stats in sorted(
        summary["models"].items(), key=lambda x: -x[1]["avg_similarity_to_qwen"]
    ):
        log.info(
            "%-20s %5d %8d %7.2fs %9.3f",
            name,
            stats["success"],
            stats["avg_text_length"],
            stats["avg_elapsed_s"],
            stats["avg_similarity_to_qwen"],
        )

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = OUTPUT_DIR / f"ocr_benchmark_{ts}.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    detail_path = OUTPUT_DIR / f"ocr_benchmark_detail_{ts}.json"
    detail_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    log.info("Summary: %s", summary_path)
    log.info("Details: %s", detail_path)


if __name__ == "__main__":
    main()
