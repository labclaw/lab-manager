#!/usr/bin/env python3
"""Run Surya OCR on rendered document images."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PIL import Image
from surya.detection import DetectionPredictor
from surya.foundation import FoundationPredictor
from surya.recognition import RecognitionPredictor


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python run_surya.py <input_dir> <output_json>")

    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])

    print(f"[{time.strftime('%H:%M:%S')}] Loading Surya models...", file=sys.stderr)
    t0 = time.time()
    foundation = FoundationPredictor()
    det_predictor = DetectionPredictor()
    rec_predictor = RecognitionPredictor(foundation)
    print(
        f"[{time.strftime('%H:%M:%S')}] Models loaded in {time.time() - t0:.1f}s",
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
        det_results = det_predictor([image])
        rec_results = rec_predictor([image], det_results)
        elapsed = time.time() - t0

        lines = []
        for page in rec_results:
            for line in page.text_lines:
                lines.append(line.text)
        full_text = "\n".join(lines)

        docs.append(
            {
                "file": image_path.name,
                "fullText": full_text,
                "lines": lines,
                "model": "Surya-OCR",
                "elapsed_s": round(elapsed, 2),
            }
        )
        print(f"  -> {len(lines)} lines, {elapsed:.2f}s", file=sys.stderr)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=False))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
