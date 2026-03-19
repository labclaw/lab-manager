#!/usr/bin/env python3

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
from pathlib import Path

from openai import OpenAI

PROMPT = """You are performing OCR on a lab supply document.
Transcribe visible text as faithfully as possible.
Rules:
- Output plain text only.
- Preserve reading order from top to bottom.
- Keep line breaks where possible.
- Include table rows, part numbers, PO numbers, dates,
  lot or batch numbers, addresses, and handwritten notes.
- Do not summarize.
- Do not explain.
"""


def image_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if not mime:
        mime = "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def run_model(client: OpenAI, model: str, image_path: Path) -> dict[str, str]:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url(image_path)},
                    },
                ],
            }
        ],
    )
    text = response.choices[0].message.content or ""
    return {
        "file": image_path.name,
        "fullText": text.strip(),
        "lines": [],
        "model": model,
    }


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: python run_openrouter_vision.py <model> <input_dir> <output_json>")

    model = sys.argv[1]
    input_dir = Path(sys.argv[2])
    output_json = Path(sys.argv[3])

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY is required")

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    docs = []
    for image_path in sorted(input_dir.iterdir()):
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            continue
        print(f"processing {image_path.name}", file=sys.stderr)
        docs.append(run_model(client, model, image_path))

    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=True))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
