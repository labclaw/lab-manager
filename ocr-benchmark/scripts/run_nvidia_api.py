#!/usr/bin/env python3
"""Run NVIDIA NIM API models on rendered document images for OCR."""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

MODELS = {
    "nemotron-nano-vl": "nvidia/nemotron-nano-12b-v2-vl",
    "nemoretriever-parse": "nvidia/nemoretriever-parse",
}

PROMPT = """You are performing OCR on a scanned lab supply document (packing list, invoice, or shipping label).
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


def image_to_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def call_vlm(api_key: str, model_id: str, image_path: Path) -> str:
    """Call a VLM model via chat completions API."""
    b64 = image_to_b64(image_path)
    suffix = image_path.suffix.lower().lstrip(".")
    if suffix in ("jpg", "jpeg"):
        mime = "image/jpeg"
    else:
        mime = f"image/{suffix}"

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.0,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_parse(api_key: str, image_path: Path) -> str:
    """Call nemoretriever-parse using image_url content + tools."""
    b64 = image_to_b64(image_path)
    suffix = image_path.suffix.lower().lstrip(".")
    if suffix in ("jpg", "jpeg"):
        mime = "image/jpeg"
    else:
        mime = f"image/{suffix}"

    payload = {
        "model": "nvidia/nemoretriever-parse",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    }
                ],
            }
        ],
        "tools": [{"type": "function", "function": {"name": "markdown_no_bbox"}}],
        "max_tokens": 3500,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        print(f"  Parse API error: {resp.text[:500]}", file=sys.stderr)
    resp.raise_for_status()
    data = resp.json()
    msg = data["choices"][0]["message"]
    # Parse returns tool_calls with structured markdown
    tool_calls = msg.get("tool_calls", [])
    if tool_calls:
        texts = []
        for tc in tool_calls:
            args = json.loads(tc["function"]["arguments"])
            if isinstance(args, list):
                for item in args:
                    if isinstance(item, dict) and "text" in item:
                        texts.append(item["text"])
            elif isinstance(args, dict) and "text" in args:
                texts.append(args["text"])
        if texts:
            return "\n".join(texts)
    return msg.get("content", "")


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: python run_nvidia_api.py <input_dir> <output_dir> [model_key]")

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    model_key = sys.argv[3] if len(sys.argv) > 3 else None

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY environment variable not set")

    models_to_run = {}
    if model_key:
        if model_key not in MODELS:
            raise SystemExit(f"Unknown model key: {model_key}. Choose from: {list(MODELS.keys())}")
        models_to_run[model_key] = MODELS[model_key]
    else:
        models_to_run = MODELS

    output_dir.mkdir(parents=True, exist_ok=True)

    for key, model_id in models_to_run.items():
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"[{time.strftime('%H:%M:%S')}] Running {model_id}", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)

        docs = []
        for image_path in sorted(input_dir.iterdir()):
            if image_path.suffix.lower() not in {
                ".png",
                ".jpg",
                ".jpeg",
                ".tif",
                ".tiff",
            }:
                continue
            print(
                f"[{time.strftime('%H:%M:%S')}] processing {image_path.name}",
                file=sys.stderr,
            )
            t0 = time.time()

            try:
                if key == "nemoretriever-parse":
                    text = call_parse(api_key, image_path)
                else:
                    text = call_vlm(api_key, model_id, image_path)
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                text = ""

            elapsed = time.time() - t0

            docs.append(
                {
                    "file": image_path.name,
                    "fullText": text.strip(),
                    "lines": [],
                    "model": model_id,
                    "elapsed_s": round(elapsed, 2),
                }
            )
            print(f"  -> {len(text)} chars, {elapsed:.2f}s", file=sys.stderr)

        out_path = output_dir / f"nvidia_{key}.json"
        out_path.write_text(json.dumps(docs, indent=2, ensure_ascii=False))
        print(f"wrote {len(docs)} docs to {out_path}")


if __name__ == "__main__":
    main()
