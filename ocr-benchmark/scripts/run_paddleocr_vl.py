#!/usr/bin/env python3
"""Run PaddleOCR-VL-1.5 (vision-language model) on rendered document images."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from paddleocr import PaddleOCRVL


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python run_paddleocr_vl.py <input_dir> <output_json>")

    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])

    ocr = PaddleOCRVL(pipeline_version="v1.5")

    docs = []
    for image_path in sorted(input_dir.iterdir()):
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            continue
        print(
            f"[{time.strftime('%H:%M:%S')}] processing {image_path.name}",
            file=sys.stderr,
        )
        t0 = time.time()
        result = ocr.predict(str(image_path))
        elapsed = time.time() - t0

        full_text = ""
        for item in result:
            if hasattr(item, "markdown"):
                full_text = item.markdown
            elif hasattr(item, "text"):
                full_text = item.text
            elif isinstance(item, dict):
                full_text = item.get("markdown", item.get("text", ""))
        docs.append(
            {
                "file": image_path.name,
                "fullText": full_text.strip() if full_text else "",
                "lines": [],
                "model": "PaddleOCR-VL-1.5",
                "elapsed_s": round(elapsed, 2),
            }
        )
        print(f"  -> {len(full_text)} chars, {elapsed:.2f}s", file=sys.stderr)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=False))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
