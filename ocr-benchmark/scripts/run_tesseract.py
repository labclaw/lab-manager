#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_tesseract(image_path: Path) -> dict[str, str]:
    proc = subprocess.run(
        ["tesseract", str(image_path), "stdout", "--psm", "6"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {"file": image_path.name, "fullText": proc.stdout.strip(), "lines": []}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python run_tesseract.py <input_dir> <output_json>")
    input_dir = Path(sys.argv[1])
    output_json = Path(sys.argv[2])
    docs = []
    for image_path in sorted(input_dir.iterdir()):
        if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
            continue
        docs.append(run_tesseract(image_path))
    output_json.write_text(json.dumps(docs, indent=2, ensure_ascii=True))
    print(f"wrote {len(docs)} docs to {output_json}")


if __name__ == "__main__":
    main()
