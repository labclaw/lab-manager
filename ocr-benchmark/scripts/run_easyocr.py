#!/usr/bin/env python3
"""Run EasyOCR on rendered document images."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import easyocr


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python run_easyocr.py <input_dir> <output_json>")

    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])

    print(f"[{time.strftime('%H:%M:%S')}] Loading EasyOCR...", file=sys.stderr)
    reader = easyocr.Reader(["en"], gpu=True)

    docs = []
    for image_path in sorted(input_dir.iterdir()):
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            continue
        print(
            f"[{time.strftime('%H:%M:%S')}] processing {image_path.name}",
            file=sys.stderr,
        )
        t0 = time.time()
        results = reader.readtext(str(image_path))
        elapsed = time.time() - t0

        lines = [text for _, text, _ in results]
        full_text = "\n".join(lines)
        docs.append(
            {
                "file": image_path.name,
                "fullText": full_text,
                "lines": lines,
                "model": "EasyOCR",
                "elapsed_s": round(elapsed, 2),
            }
        )
        print(f"  -> {len(lines)} lines, {elapsed:.2f}s", file=sys.stderr)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=False))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
