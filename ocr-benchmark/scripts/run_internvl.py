#!/usr/bin/env python3
"""Run InternVL2.5 on rendered document images for OCR."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModel, AutoTokenizer

MODEL_ID = "OpenGVLab/InternVL2_5-4B"
PROMPT = """You are performing OCR on a lab supply document.
Transcribe visible text as faithfully as possible.
Rules:
- Output plain text only.
- Preserve reading order from top to bottom.
- Keep line breaks where possible.
- Include table rows, part numbers, PO numbers, dates, lot or batch numbers, addresses, and handwritten notes.
- Do not summarize.
- Do not explain.
"""


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: python run_internvl.py <input_dir> <output_json> [model_id]")

    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    model_id = sys.argv[3] if len(sys.argv) > 3 else MODEL_ID

    print(f"[{time.strftime('%H:%M:%S')}] Loading {model_id}...", file=sys.stderr)
    t0 = time.time()
    model = AutoModel.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    ).eval()
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
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
        pixel_values = model.image_processor(images=[image], return_tensors="pt")["pixel_values"]
        pixel_values = pixel_values.to(model.device, dtype=torch.bfloat16)

        generation_config = {"max_new_tokens": 4096, "do_sample": False}
        question = f"<image>\n{PROMPT}"
        with torch.no_grad():
            text = model.chat(tokenizer, pixel_values, question, generation_config)
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
