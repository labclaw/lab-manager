#!/usr/bin/env python3
"""Full OCR Benchmark: compare OCR models on all 279 lab document scans.

Models tested:
  1. claude_sonnet  — Claude Sonnet 4.6 via Claude Code CLI
  2. gemini_cli     — Gemini (default model) via Gemini CLI
  3. gemini_api     — Gemini 3.1 Flash via Google GenAI API
  4. codex_gpt      — GPT-5.4 via Codex CLI (slow, web-verified)
  5. qwen3_vl       — Qwen3-VL-4B baseline (from existing OCR JSON)

Records per-image:
  - raw OCR text from each model
  - text length, line count
  - elapsed time
  - word-level similarity to baseline (Qwen3-VL)
  - character-level edit distance

Usage:
    python scripts/run_ocr_benchmark.py                          # all 279 docs, 3 fast models
    python scripts/run_ocr_benchmark.py --sample 10              # first 10 docs
    python scripts/run_ocr_benchmark.py --models claude,gemini   # specific models
    python scripts/run_ocr_benchmark.py --models all             # include codex (slow)
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import subprocess
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
OCR_JSON = PROJECT_ROOT / "shenlab-docs" / "ocr-output" / "all_scans_qwen3_vl_v2.json"
OUTPUT_DIR = PROJECT_ROOT / "benchmarks"

OCR_PROMPT = """Transcribe ALL visible text from this scanned lab document faithfully, character by character.

Rules:
- Output plain text only. Preserve reading order top-to-bottom, left-to-right.
- Keep line breaks where they appear on the document.
- Pay extra attention to catalog/part numbers, batch/lot numbers, PO numbers, dates.
- Include ALL text: fine print, footer, handwritten annotations.
- Do NOT summarize, explain, or skip any text region.
"""


# ─── OCR Model Functions ────────────────────────────────────────


def ocr_opus(image_path: str) -> str:
    """Claude Opus 4.6 via Claude Code CLI."""
    prompt = f"Read the image at {image_path} and:\n\n{OCR_PROMPT}"
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=300,
        env={**os.environ, "CLAUDE_MODEL": "claude-opus-4-6"},
    )
    if result.returncode == 0:
        return result.stdout.strip()
    raise RuntimeError(f"Opus failed: {result.stderr[:200]}")


def ocr_gemini_pro(image_path: str) -> str:
    """Gemini 2.5 Pro via Google GenAI API (best Gemini available via API)."""
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get(
        "EXTRACTION_API_KEY", ""
    )
    client = genai.Client(api_key=api_key)

    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    suffix = Path(image_path).suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": b64}},
                    {"text": OCR_PROMPT},
                ],
            }
        ],
    )
    text = response.text
    if text is None:
        raise RuntimeError("Gemini Pro API returned None (no candidates)")
    return text


def ocr_gemini_cli(image_path: str) -> str:
    """Gemini 3.1 Pro via Gemini CLI (latest model)."""
    prompt = f"Read the file {image_path} and:\n\n{OCR_PROMPT}"
    result = subprocess.run(
        ["gemini", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    raise RuntimeError(f"Gemini CLI failed: {result.stderr[:200]}")


def ocr_codex_gpt(image_path: str) -> str:
    """GPT-5.4 via Codex CLI."""
    result = subprocess.run(
        ["codex", "exec", "-i", image_path, OCR_PROMPT],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")
        text_lines = [
            line
            for line in lines
            if not line.startswith("codex")
            and not line.startswith("🌐")
            and not line.startswith("mcp:")
            and not line.startswith("deprecated:")
            and not line.startswith("mcp startup:")
        ]
        return "\n".join(text_lines).strip()
    raise RuntimeError(f"Codex failed: {result.stderr[:200]}")


MODEL_REGISTRY = {
    "opus": ("Claude Opus 4.6", "claude-opus-4-6", ocr_opus),
    "gemini_pro": ("Gemini 2.5 Pro API", "gemini-2.5-pro", ocr_gemini_pro),
    "gemini_cli": ("Gemini 3.1 Pro CLI", "gemini-3.1-pro", ocr_gemini_cli),
    "codex": ("GPT-5.4 Codex", "gpt-5.4", ocr_codex_gpt),
}


# ─── Metrics ────────────────────────────────────────────────────


def word_jaccard(a: str, b: str) -> float:
    """Word-level Jaccard similarity."""
    if not a and not b:
        return 1.0
    wa, wb = set(a.lower().split()), set(b.lower().split())
    if not wa and not wb:
        return 1.0
    return len(wa & wb) / len(wa | wb) if (wa | wb) else 0.0


def char_edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (truncated to first 5000 chars for speed)."""
    a, b = a[:5000], b[:5000]
    if len(a) > len(b):
        a, b = b, a
    distances = range(len(a) + 1)
    for i2, c2 in enumerate(b):
        new_distances = [i2 + 1]
        for i1, c1 in enumerate(a):
            if c1 == c2:
                new_distances.append(distances[i1])
            else:
                new_distances.append(
                    1 + min(distances[i1], distances[i1 + 1], new_distances[-1])
                )
        distances = new_distances
    return distances[-1]


def compute_metrics(text: str, reference: str) -> dict:
    """Compute all comparison metrics."""
    return {
        "text_length": len(text),
        "line_count": len(text.split("\n")) if text else 0,
        "word_count": len(text.split()) if text else 0,
        "jaccard_similarity": round(word_jaccard(text, reference), 4),
        "edit_distance": char_edit_distance(text, reference),
        "ref_length": len(reference),
    }


# ─── Main ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="OCR Model Benchmark")
    parser.add_argument(
        "--models",
        default="opus,gemini_pro,gemini_cli,codex",
        help="Comma-separated: opus,gemini_pro,gemini_cli,codex,all",
    )
    parser.add_argument("--sample", type=int, default=0, help="0=all 279")
    args = parser.parse_args()

    # Load baseline (Qwen3-VL)
    baseline = json.loads(OCR_JSON.read_text())
    baseline_map = {e["file"]: e.get("fullText", "") for e in baseline}
    all_files = sorted(baseline_map.keys())

    if args.sample > 0:
        step = max(1, len(all_files) // args.sample)
        test_files = all_files[::step][: args.sample]
    else:
        test_files = all_files

    # Resolve models
    if args.models == "all":
        model_names = list(MODEL_REGISTRY.keys())
    else:
        model_names = [m.strip() for m in args.models.split(",")]

    models = {}
    for name in model_names:
        if name in MODEL_REGISTRY:
            models[name] = MODEL_REGISTRY[name]
        else:
            log.warning(
                "Unknown model: %s (available: %s)", name, list(MODEL_REGISTRY.keys())
            )

    log.info("=" * 70)
    log.info("OCR BENCHMARK: %d models x %d documents", len(models), len(test_files))
    for name, (desc, model_id, _) in models.items():
        log.info("  %s: %s (%s)", name, desc, model_id)
    log.info("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Results storage
    results = {name: [] for name in models}
    all_detail = []

    for i, file_name in enumerate(test_files, 1):
        resized_path = str(RESIZED_DIR / file_name)
        if not Path(resized_path).exists():
            log.warning(
                "[%d/%d] SKIP %s (no resized image)", i, len(test_files), file_name
            )
            continue

        ref_text = baseline_map.get(file_name, "")
        log.info(
            "[%d/%d] %s (ref: %d chars)", i, len(test_files), file_name, len(ref_text)
        )

        doc_result = {
            "file_name": file_name,
            "ref_text_length": len(ref_text),
            "models": {},
        }

        for name, (desc, model_id, ocr_fn) in models.items():
            t0 = time.time()
            try:
                text = ocr_fn(resized_path)
                elapsed = time.time() - t0
                success = True
                error = None
            except Exception as e:
                text = ""
                elapsed = time.time() - t0
                success = False
                error = str(e)[:200]

            text = text or ""
            metrics = compute_metrics(text, ref_text)
            entry = {
                "model": name,
                "model_id": model_id,
                "success": success,
                "error": error,
                "elapsed_s": round(elapsed, 2),
                "text": text,
                **metrics,
            }
            results[name].append(entry)
            doc_result["models"][name] = {k: v for k, v in entry.items() if k != "text"}

            status = "OK" if success else "FAIL"
            log.info(
                "  %-15s %s %5d chars  %5.1fs  sim=%.3f  edit=%d",
                name,
                status,
                metrics["text_length"],
                elapsed,
                metrics["jaccard_similarity"],
                metrics["edit_distance"],
            )

        all_detail.append(doc_result)

        # Save incrementally
        if i % 10 == 0:
            _save_results(
                OUTPUT_DIR, ts, results, all_detail, models, test_files, partial=True
            )

    # Final save
    _save_results(
        OUTPUT_DIR, ts, results, all_detail, models, test_files, partial=False
    )


def _save_results(
    output_dir, ts, results, all_detail, models, test_files, partial=False
):
    """Save benchmark results and print summary."""
    suffix = "_partial" if partial else ""

    # Per-doc detail (without full text, to keep file small)
    detail_path = output_dir / f"ocr_bench_detail_{ts}{suffix}.json"
    detail_path.write_text(json.dumps(all_detail, indent=2, ensure_ascii=False))

    # Full text outputs per model
    for name, entries in results.items():
        text_path = output_dir / f"ocr_bench_{name}_{ts}{suffix}.json"
        text_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False))

    # Summary
    summary = {
        "generated_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "total_docs": len(all_detail),
        "target_docs": len(test_files),
        "models": {},
    }

    for name, entries in results.items():
        if not entries:
            continue
        successes = [e for e in entries if e["success"]]
        n = max(len(successes), 1)
        desc, model_id, _ = models[name]

        summary["models"][name] = {
            "description": desc,
            "model_id": model_id,
            "total": len(entries),
            "success": len(successes),
            "fail": len(entries) - len(successes),
            "avg_text_length": round(sum(e["text_length"] for e in successes) / n),
            "avg_line_count": round(sum(e["line_count"] for e in successes) / n),
            "avg_word_count": round(sum(e["word_count"] for e in successes) / n),
            "avg_elapsed_s": round(sum(e["elapsed_s"] for e in successes) / n, 2),
            "avg_jaccard_sim": round(
                sum(e["jaccard_similarity"] for e in successes) / n, 4
            ),
            "avg_edit_distance": round(sum(e["edit_distance"] for e in successes) / n),
            "total_elapsed_s": round(sum(e["elapsed_s"] for e in entries), 1),
        }

    summary_path = output_dir / f"ocr_bench_summary_{ts}{suffix}.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    if not partial:
        log.info("=" * 70)
        log.info("BENCHMARK COMPLETE — %d docs", len(all_detail))
        log.info(
            "%-15s %6s %8s %8s %10s %8s",
            "Model",
            "OK",
            "AvgLen",
            "AvgTime",
            "Jaccard",
            "EditDist",
        )
        log.info("-" * 70)
        for name, stats in sorted(
            summary["models"].items(), key=lambda x: -x[1]["avg_jaccard_sim"]
        ):
            log.info(
                "%-15s %5d %8d %7.1fs %9.4f %8d",
                name,
                stats["success"],
                stats["avg_text_length"],
                stats["avg_elapsed_s"],
                stats["avg_jaccard_sim"],
                stats["avg_edit_distance"],
            )
        log.info("-" * 70)
        log.info("Qwen3-VL baseline: already in OCR JSON (not re-run)")
        log.info("Output: %s", summary_path)


if __name__ == "__main__":
    main()
