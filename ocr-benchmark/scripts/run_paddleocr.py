#!/usr/bin/env python3
"""Run PaddleOCR (PP-OCRv5) on rendered document images."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from paddleocr import PaddleOCR


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python run_paddleocr.py <input_dir> <output_json>")

    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])

    ocr = PaddleOCR(
        lang="en",
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
        result = ocr.predict(str(image_path))
        elapsed = time.time() - t0

        lines = []
        for item in result:
            if hasattr(item, "rec_texts"):
                lines.extend(item.rec_texts)
            elif isinstance(item, dict) and "rec_texts" in item:
                lines.extend(item["rec_texts"])
        full_text = "\n".join(lines)
        docs.append(
            {
                "file": image_path.name,
                "fullText": full_text,
                "lines": lines,
                "model": "PaddleOCR-PP-OCRv5",
                "elapsed_s": round(elapsed, 2),
            }
        )
        print(f"  -> {len(lines)} lines, {elapsed:.2f}s", file=sys.stderr)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=False))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
