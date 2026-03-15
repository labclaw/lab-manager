#!/usr/bin/env python3
"""Run DocTR on rendered document images."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from doctr.io import DocumentFile
from doctr.models import ocr_predictor


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python run_doctr.py <input_dir> <output_json>")

    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])

    print(f"[{time.strftime('%H:%M:%S')}] Loading DocTR...", file=sys.stderr)
    predictor = ocr_predictor(pretrained=True)

    docs = []
    for image_path in sorted(input_dir.iterdir()):
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            continue
        print(
            f"[{time.strftime('%H:%M:%S')}] processing {image_path.name}",
            file=sys.stderr,
        )
        t0 = time.time()
        doc = DocumentFile.from_images(str(image_path))
        result = predictor(doc)
        elapsed = time.time() - t0

        lines = []
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    line_text = " ".join(w.value for w in line.words)
                    lines.append(line_text)
        full_text = "\n".join(lines)
        docs.append(
            {
                "file": image_path.name,
                "fullText": full_text,
                "lines": lines,
                "model": "DocTR",
                "elapsed_s": round(elapsed, 2),
            }
        )
        print(f"  -> {len(lines)} lines, {elapsed:.2f}s", file=sys.stderr)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=False))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
