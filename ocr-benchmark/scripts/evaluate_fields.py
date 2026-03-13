#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: Path):
    return json.loads(path.read_text())


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python evaluate_fields.py <gold_json> <ocr_json>")

    gold = load_json(Path(sys.argv[1]))
    ocr_payload = load_json(Path(sys.argv[2]))
    if isinstance(ocr_payload, dict):
        docs = ocr_payload.get("documents", [])
    else:
        docs = ocr_payload
    ocr_docs = {doc["file"]: doc for doc in docs}

    total = 0
    hits = 0
    for item in gold:
        file_name = item["file"]
        text = normalize(ocr_docs.get(file_name, {}).get("fullText", ""))
        print(file_name)
        for field in item["fields"]:
            total += 1
            expected = normalize(field["expected"])
            ok = expected in text
            if ok:
                hits += 1
            status = "PASS" if ok else "FAIL"
            print(f"  [{status}] {field['name']}: {field['expected']}")
        print()

    score = 100 * hits / total if total else 0.0
    print(f"field_recall={hits}/{total} ({score:.1f}%)")


if __name__ == "__main__":
    main()
