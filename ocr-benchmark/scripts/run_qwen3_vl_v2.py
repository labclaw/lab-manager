#!/usr/bin/env python3
"""Run Qwen3-VL with improved prompt for higher OCR recall."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

MODEL_ID = "Qwen/Qwen3-VL-4B-Instruct"
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


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: python run_qwen3_vl_v2.py <input_dir> <output_json> [model_id]")

    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    model_id = sys.argv[3] if len(sys.argv) > 3 else MODEL_ID

    print(f"[{time.strftime('%H:%M:%S')}] Loading {model_id}...", file=sys.stderr)
    t0 = time.time()
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    print(
        f"[{time.strftime('%H:%M:%S')}] Model loaded in {time.time() - t0:.1f}s",
        file=sys.stderr,
    )

    docs = []
    for image_path in sorted(input_dir.iterdir()):
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            continue
        print(
            f"[{time.strftime('%H:%M:%S')}] processing {image_path.name}",
            file=sys.stderr,
        )
        t0 = time.time()

        image = Image.open(image_path).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ]
        text_input = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(
            text=[text_input],
            images=[image],
            return_tensors="pt",
            padding=True,
        ).to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=4096,
                do_sample=False,
            )
        generated_ids = output_ids[:, inputs["input_ids"].shape[1] :]
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
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

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=False))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
