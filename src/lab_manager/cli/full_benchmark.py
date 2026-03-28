#!/usr/bin/env python3
"""Full model benchmark: ALL VLM + ALL extraction models × ALL 279 docs.

Saves per-model per-doc results as JSONL. Resumable — skips completed pairs.
Rate-limit aware with exponential backoff.

Usage:
    NVIDIA_BUILD_API_KEY=... uv run python scripts/full_benchmark.py [--phase ocr|extract|all]
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from lab_manager.intake.prompts import EXTRACTION_PROMPT, OCR_PROMPT  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("benchmark")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DOCS_DIR = Path(
    os.environ.get(
        "DOCS_DIR", str(Path(__file__).resolve().parent.parent / "data" / "resized")
    )
)
BENCH_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "full_benchmark"
BENCH_DIR.mkdir(parents=True, exist_ok=True)

NVIDIA_KEY = os.environ.get("NVIDIA_BUILD_API_KEY") or os.environ.get(
    "NVIDIA_API_KEY", ""
)
API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

MAX_RETRIES = 5
RETRY_DELAY = 10  # base delay for exponential backoff
INTER_CALL_DELAY = 5  # seconds between API calls (avoid NVIDIA rate limits)

# All VLM models that passed single-image test (4/4 or vision-capable)
VLM_MODELS = [
    ("llama-3.2-90b-vision", "meta/llama-3.2-90b-vision-instruct"),
    ("llama-3.2-11b-vision", "meta/llama-3.2-11b-vision-instruct"),
    ("llama-4-maverick", "meta/llama-4-maverick-17b-128e-instruct"),
    ("nemotron-nano-12b-vl", "nvidia/nemotron-nano-12b-v2-vl"),
    ("nemotron-nano-vl-8b", "nvidia/llama-3.1-nemotron-nano-vl-8b-v1"),
    ("phi-4-multimodal", "microsoft/phi-4-multimodal-instruct"),
    ("phi-3.5-vision", "microsoft/phi-3.5-vision-instruct"),
    ("kimi-k2.5", "moonshotai/kimi-k2.5"),
]

# All extraction models that passed single-doc test
EXTRACT_MODELS = [
    ("glm5", "z-ai/glm5"),
    ("glm4.7", "z-ai/glm4.7"),
    ("llama-3.3-70b", "meta/llama-3.3-70b-instruct"),
    ("llama-3.1-405b", "meta/llama-3.1-405b-instruct"),
    ("nemotron-ultra-253b", "nvidia/llama-3.1-nemotron-ultra-253b-v1"),
    ("nemotron-super-49b", "nvidia/llama-3.3-nemotron-super-49b-v1.5"),
    ("nemotron-51b", "nvidia/llama-3.1-nemotron-51b-instruct"),
    ("qwen3.5-397b", "qwen/qwen3.5-397b-a17b"),
    ("qwen3.5-122b", "qwen/qwen3.5-122b-a10b"),
    ("qwen3-next-80b", "qwen/qwen3-next-80b-a3b-instruct"),
    ("qwen2.5-coder-32b", "qwen/qwen2.5-coder-32b-instruct"),
    ("qwq-32b", "qwen/qwq-32b"),
    ("deepseek-v3.2", "deepseek-ai/deepseek-v3.2"),
    ("deepseek-v3.1", "deepseek-ai/deepseek-v3.1"),
    ("mistral-large-3-675b", "mistralai/mistral-large-3-675b-instruct-2512"),
    ("mistral-medium-3", "mistralai/mistral-medium-3-instruct"),
    ("mistral-small-4-119b", "mistralai/mistral-small-4-119b-2603"),
    ("gemma-3-27b", "google/gemma-3-27b-it"),
]


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


API_LOG = BENCH_DIR / "api_calls.jsonl"


def _nvidia_call(
    payload: dict, timeout: int = 180, call_meta: dict | None = None
) -> str:
    """Call NVIDIA NIM API with full logging of every request/response."""
    model = payload.get("model", "unknown")
    for attempt in range(MAX_RETRIES):
        t0 = time.time()
        record = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "attempt": attempt + 1,
            "timeout": timeout,
            **(call_meta or {}),
        }
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
            dt = time.time() - t0
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})

            record.update(
                {
                    "http_status": resp.status_code,
                    "latency_s": round(dt, 2),
                    "response_chars": len(content),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "success": True,
                }
            )
            with open(API_LOG, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")

            resp.raise_for_status()
            return content

        except httpx.HTTPStatusError as e:
            dt = time.time() - t0
            record.update(
                {
                    "http_status": e.response.status_code,
                    "latency_s": round(dt, 2),
                    "error": str(e)[:300],
                    "response_body": e.response.text[:500],
                    "success": False,
                }
            )
            with open(API_LOG, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")

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
            if e.response.status_code in (404, 400):
                raise
            raise

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            dt = time.time() - t0
            record.update(
                {
                    "http_status": "timeout"
                    if isinstance(e, httpx.TimeoutException)
                    else "conn_error",
                    "latency_s": round(dt, 2),
                    "error": str(e)[:300],
                    "success": False,
                }
            )
            with open(API_LOG, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")

            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2**attempt)
                log.warning("Connection error, retrying in %ds: %s", delay, e)
                time.sleep(delay)
                continue
            raise

    raise RuntimeError(f"API failed after {MAX_RETRIES} retries")


# ---------------------------------------------------------------------------
# OCR benchmark
# ---------------------------------------------------------------------------


def load_done(logfile: Path) -> set:
    """Load already-completed (model, file) pairs from JSONL."""
    done = set()
    if logfile.exists():
        for line in logfile.read_text().splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                done.add((d["model"], d["file"]))
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def benchmark_ocr():
    """Run all VLM models on all 279 docs."""
    images = sorted(DOCS_DIR.glob("*.jpg"))
    log.info(
        "OCR Benchmark: %d models × %d docs = %d calls",
        len(VLM_MODELS),
        len(images),
        len(VLM_MODELS) * len(images),
    )

    logfile = BENCH_DIR / "ocr_results.jsonl"
    done = load_done(logfile)
    log.info("Already completed: %d", len(done))

    total = len(VLM_MODELS) * len(images)
    completed = len(done)
    t_start = time.time()

    for model_name, model_id in VLM_MODELS:
        model_done = sum(1 for m, _ in done if m == model_name)
        model_todo = len(images) - model_done
        if model_todo == 0:
            log.info("[%s] All %d docs done, skipping", model_name, len(images))
            continue

        log.info("[%s] Starting: %d todo, %d done", model_name, model_todo, model_done)

        for img in images:
            if (model_name, img.name) in done:
                continue

            completed += 1
            elapsed = time.time() - t_start
            newly_done = completed - len(done)
            eta = (
                (elapsed / max(newly_done, 1)) * (total - completed)
                if newly_done > 0
                else 0
            )

            t0 = time.time()
            result = {
                "model": model_name,
                "model_id": model_id,
                "file": img.name,
                "timestamp": datetime.now().isoformat(),
            }

            try:
                b64 = base64.b64encode(img.read_bytes()).decode()
                img_size_kb = img.stat().st_size // 1024
                text = _nvidia_call(
                    {
                        "model": model_id,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{b64}"
                                        },
                                    },
                                    {"type": "text", "text": OCR_PROMPT},
                                ],
                            }
                        ],
                        "max_tokens": 4096,
                        "temperature": 0.1,
                    },
                    call_meta={
                        "phase": "ocr",
                        "file": img.name,
                        "file_size_kb": img_size_kb,
                    },
                )
                dt = time.time() - t0
                result["status"] = "ok"
                result["text"] = text
                result["file_size_kb"] = img_size_kb
                result["length"] = len(text)
                result["time"] = round(dt, 1)

                # Quick field checks (Millipore Sigma doc-specific, generalized)
                result["has_text"] = len(text) > 50

                log.info(
                    "  [%d/%d] %s %s %d chars %.1fs (ETA %dm)",
                    completed,
                    total,
                    model_name,
                    img.name,
                    len(text),
                    dt,
                    eta // 60,
                )

            except Exception as e:
                dt = time.time() - t0
                result["status"] = "fail"
                result["error"] = str(e)[:200]
                result["time"] = round(dt, 1)
                log.warning(
                    "  [%d/%d] %s %s FAIL %.1fs: %s",
                    completed,
                    total,
                    model_name,
                    img.name,
                    dt,
                    str(e)[:80],
                )

            with open(logfile, "a") as f:
                # Save text separately to keep log compact
                log_entry = {k: v for k, v in result.items() if k != "text"}
                log_entry["text_preview"] = (result.get("text", "") or "")[:200]
                f.write(json.dumps(log_entry, default=str) + "\n")

            # Save full OCR text in per-model directory
            text_dir = BENCH_DIR / "ocr_texts" / model_name
            text_dir.mkdir(parents=True, exist_ok=True)
            text_file = text_dir / f"{img.stem}.txt"
            text_file.write_text(result.get("text", ""))

            done.add((model_name, img.name))
            time.sleep(INTER_CALL_DELAY)

    log.info("OCR Benchmark complete. Results: %s", logfile)


# ---------------------------------------------------------------------------
# Extraction benchmark
# ---------------------------------------------------------------------------


def benchmark_extract():
    """Run all extraction models on OCR texts from best VLM."""
    # Use best OCR model's texts as input
    best_ocr = "llama-3.2-90b-vision"  # highest quality from our tests
    text_dir = BENCH_DIR / "ocr_texts" / best_ocr
    if not text_dir.exists():
        log.error("No OCR texts from %s. Run --phase ocr first.", best_ocr)
        sys.exit(1)

    text_files = sorted(text_dir.glob("*.txt"))
    log.info(
        "Extraction Benchmark: %d models × %d docs",
        len(EXTRACT_MODELS),
        len(text_files),
    )

    logfile = BENCH_DIR / "extract_results.jsonl"
    done = load_done(logfile)
    log.info("Already completed: %d", len(done))

    total = len(EXTRACT_MODELS) * len(text_files)
    completed = len(done)
    t_start = time.time()

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

    for model_name, model_id in EXTRACT_MODELS:
        model_done = sum(1 for m, _ in done if m == model_name)
        model_todo = len(text_files) - model_done
        if model_todo == 0:
            log.info("[%s] All %d docs done, skipping", model_name, len(text_files))
            continue

        log.info("[%s] Starting: %d todo, %d done", model_name, model_todo, model_done)

        for tf in text_files:
            doc_name = tf.stem + ".jpg"
            if (model_name, doc_name) in done:
                continue

            completed += 1
            elapsed = time.time() - t_start
            newly_done = completed - len(done)
            eta = (
                (elapsed / max(newly_done, 1)) * (total - completed)
                if newly_done > 0
                else 0
            )

            ocr_text = tf.read_text()
            if not ocr_text or len(ocr_text) < 20:
                log.warning(
                    "  [%d/%d] %s %s: empty OCR text, skipping",
                    completed,
                    total,
                    model_name,
                    doc_name,
                )
                continue

            t0 = time.time()
            result = {
                "model": model_name,
                "model_id": model_id,
                "file": doc_name,
                "ocr_source": best_ocr,
                "timestamp": datetime.now().isoformat(),
            }

            prompt = f"""{EXTRACTION_PROMPT}

Return ONLY valid JSON matching this schema (no markdown, no extra text):
{extraction_schema}

---
OCR TEXT:
{ocr_text[:3000]}"""

            try:
                raw = _nvidia_call(
                    {
                        "model": model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2048,
                        "temperature": 0.1,
                    },
                    timeout=90,
                )

                dt = time.time() - t0

                # Parse JSON
                text = raw.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()

                parsed = None
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        try:
                            parsed = json.loads(text[start:end])
                        except json.JSONDecodeError:
                            pass

                if parsed:
                    result["status"] = "ok"
                    result["data"] = parsed
                    result["time"] = round(dt, 1)
                    result["vendor"] = parsed.get("vendor_name")
                    result["doc_type"] = parsed.get("document_type")
                    result["po"] = parsed.get("po_number")
                    result["item_count"] = len(parsed.get("items", []))
                    result["confidence"] = parsed.get("confidence")
                    log.info(
                        "  [%d/%d] %s %s OK %.1fs vendor=%s (ETA %dm)",
                        completed,
                        total,
                        model_name,
                        doc_name,
                        dt,
                        str(result["vendor"])[:20],
                        eta // 60,
                    )
                else:
                    result["status"] = "parse_fail"
                    result["raw"] = raw[:500]
                    result["time"] = round(dt, 1)
                    log.warning(
                        "  [%d/%d] %s %s PARSE_FAIL %.1fs",
                        completed,
                        total,
                        model_name,
                        doc_name,
                        dt,
                    )

            except Exception as e:
                dt = time.time() - t0
                result["status"] = "fail"
                result["error"] = str(e)[:200]
                result["time"] = round(dt, 1)
                log.warning(
                    "  [%d/%d] %s %s FAIL %.1fs: %s",
                    completed,
                    total,
                    model_name,
                    doc_name,
                    dt,
                    str(e)[:80],
                )

            with open(logfile, "a") as f:
                log_entry = {k: v for k, v in result.items() if k != "data"}
                if "data" in result:
                    log_entry["vendor"] = result.get("vendor")
                    log_entry["doc_type"] = result.get("doc_type")
                    log_entry["po"] = result.get("po")
                    log_entry["item_count"] = result.get("item_count")
                    log_entry["confidence"] = result.get("confidence")
                f.write(json.dumps(log_entry, default=str) + "\n")

            # Save full extraction in per-model directory
            ext_dir = BENCH_DIR / "extractions" / model_name
            ext_dir.mkdir(parents=True, exist_ok=True)
            ext_file = ext_dir / f"{tf.stem}.json"
            ext_file.write_text(
                json.dumps(result.get("data", {}), indent=2, default=str)
            )

            done.add((model_name, doc_name))
            time.sleep(INTER_CALL_DELAY)

    log.info("Extraction Benchmark complete. Results: %s", logfile)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def generate_report():
    """Generate summary report from benchmark results."""
    report = []
    report.append("=" * 80)
    report.append("OCR+VLM FULL BENCHMARK REPORT")
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append("=" * 80)

    # OCR results
    ocr_file = BENCH_DIR / "ocr_results.jsonl"
    if ocr_file.exists():
        from collections import defaultdict

        model_stats = defaultdict(
            lambda: {"ok": 0, "fail": 0, "total_chars": 0, "total_time": 0, "times": []}
        )

        for line in ocr_file.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            m = d["model"]
            s = model_stats[m]
            if d["status"] == "ok":
                s["ok"] += 1
                s["total_chars"] += d.get("length", 0)
                s["total_time"] += d.get("time", 0)
                s["times"].append(d.get("time", 0))
            else:
                s["fail"] += 1

        report.append("\nOCR MODEL RESULTS:")
        report.append(
            f"{'Model':<30} {'OK':>5} {'Fail':>5} {'Avg Chars':>10} {'Avg Time':>10} {'Total':>10}"
        )
        report.append("-" * 75)
        for m, s in sorted(model_stats.items(), key=lambda x: -x[1]["ok"]):
            avg_chars = int(s["total_chars"] / max(s["ok"], 1))
            avg_time = s["total_time"] / max(s["ok"], 1)
            total = s["ok"] + s["fail"]
            report.append(
                f"{m:<30} {s['ok']:>5} {s['fail']:>5} {avg_chars:>10} {avg_time:>9.1f}s {total:>10}"
            )

    # Extraction results
    ext_file = BENCH_DIR / "extract_results.jsonl"
    if ext_file.exists():
        from collections import defaultdict

        model_stats = defaultdict(
            lambda: {
                "ok": 0,
                "fail": 0,
                "parse_fail": 0,
                "total_time": 0,
                "vendors": 0,
                "pos": 0,
                "items": 0,
            }
        )

        for line in ext_file.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            m = d["model"]
            s = model_stats[m]
            if d["status"] == "ok":
                s["ok"] += 1
                s["total_time"] += d.get("time", 0)
                if d.get("vendor"):
                    s["vendors"] += 1
                if d.get("po"):
                    s["pos"] += 1
                s["items"] += d.get("item_count", 0)
            elif d["status"] == "parse_fail":
                s["parse_fail"] += 1
            else:
                s["fail"] += 1

        report.append("\nEXTRACTION MODEL RESULTS:")
        report.append(
            f"{'Model':<25} {'OK':>5} {'Parse':>5} {'Fail':>5} {'Vendor%':>8} {'PO%':>6} {'Avg Time':>9}"
        )
        report.append("-" * 70)
        for m, s in sorted(model_stats.items(), key=lambda x: -x[1]["ok"]):
            total_ok = max(s["ok"], 1)
            vendor_pct = 100 * s["vendors"] / total_ok
            po_pct = 100 * s["pos"] / total_ok
            avg_time = s["total_time"] / total_ok
            report.append(
                f"{m:<25} {s['ok']:>5} {s['parse_fail']:>5} {s['fail']:>5} {vendor_pct:>7.0f}% {po_pct:>5.0f}% {avg_time:>8.1f}s"
            )

    report_text = "\n".join(report)
    report_file = BENCH_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    report_file.write_text(report_text)
    print(report_text)
    log.info("Report saved: %s", report_file)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Full model benchmark")
    parser.add_argument(
        "--phase", choices=["ocr", "extract", "report", "all"], default="all"
    )
    args = parser.parse_args()

    if not NVIDIA_KEY:
        print("ERROR: Set NVIDIA_BUILD_API_KEY or NVIDIA_API_KEY")
        sys.exit(1)

    images = sorted(DOCS_DIR.glob("*.jpg"))
    if not images:
        print(f"ERROR: No images in {DOCS_DIR}")
        sys.exit(1)
    log.info("Found %d images in %s", len(images), DOCS_DIR)

    if args.phase in ("ocr", "all"):
        benchmark_ocr()

    if args.phase in ("extract", "all"):
        benchmark_extract()

    if args.phase in ("report", "all"):
        generate_report()


if __name__ == "__main__":
    main()
