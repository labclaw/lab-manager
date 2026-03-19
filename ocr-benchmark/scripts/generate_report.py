#!/usr/bin/env python3
"""Generate a full OCR benchmark report from all results."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def evaluate(gold: list[dict], ocr_docs: dict[str, dict]) -> dict:
    total = 0
    hits = 0
    per_doc = []
    for item in gold:
        file_name = item["file"]
        text = normalize(ocr_docs.get(file_name, {}).get("fullText", ""))
        doc_total = 0
        doc_hits = 0
        field_results = []
        for field in item["fields"]:
            total += 1
            doc_total += 1
            expected = normalize(field["expected"])
            ok = expected in text
            if ok:
                hits += 1
                doc_hits += 1
            field_results.append(
                {
                    "name": field["name"],
                    "expected": field["expected"],
                    "found": ok,
                }
            )
        per_doc.append(
            {
                "file": file_name,
                "recall": f"{doc_hits}/{doc_total}",
                "score": round(100 * doc_hits / doc_total, 1) if doc_total else 0,
                "fields": field_results,
            }
        )
    return {
        "total": total,
        "hits": hits,
        "recall_pct": round(100 * hits / total, 1) if total else 0,
        "per_doc": per_doc,
    }


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: python generate_report.py <gold_json> <result1.json> [result2.json ...]")

    gold = json.loads(Path(sys.argv[1]).read_text())
    result_files = [Path(p) for p in sys.argv[2:]]

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_lines = []
    report_lines.append(f"# OCR Benchmark Report — {ts}")
    report_lines.append("")
    report_lines.append(f"Gold standard: {len(gold)} documents, {sum(len(d['fields']) for d in gold)} fields total")
    report_lines.append("")

    summary_rows = []
    all_evals = {}

    for rf in result_files:
        ocr_payload = json.loads(rf.read_text())
        if isinstance(ocr_payload, dict):
            docs = ocr_payload.get("documents", [])
        else:
            docs = ocr_payload
        ocr_docs = {doc["file"]: doc for doc in docs}

        model_name = docs[0].get("model", rf.stem) if docs else rf.stem
        avg_time = sum(d.get("elapsed_s", 0) for d in docs) / len(docs) if docs else 0

        ev = evaluate(gold, ocr_docs)
        all_evals[model_name] = ev

        summary_rows.append(
            {
                "model": model_name,
                "recall": f"{ev['hits']}/{ev['total']}",
                "score": ev["recall_pct"],
                "avg_time": round(avg_time, 2),
            }
        )

    summary_rows.sort(key=lambda r: r["score"], reverse=True)

    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append("| Rank | Model | Field Recall | Score | Avg Time/Doc |")
    report_lines.append("|------|-------|-------------|-------|-------------|")
    for i, row in enumerate(summary_rows, 1):
        report_lines.append(f"| {i} | {row['model']} | {row['recall']} | {row['score']}% | {row['avg_time']}s |")
    report_lines.append("")

    for model_name, ev in all_evals.items():
        report_lines.append(f"## {model_name}")
        report_lines.append("")
        report_lines.append(f"Overall field recall: **{ev['hits']}/{ev['total']} ({ev['recall_pct']}%)**")
        report_lines.append("")
        for doc in ev["per_doc"]:
            report_lines.append(f"### {doc['file']} — {doc['recall']} ({doc['score']}%)")
            report_lines.append("")
            for f in doc["fields"]:
                status = "PASS" if f["found"] else "FAIL"
                report_lines.append(f"- [{status}] **{f['name']}**: {f['expected']}")
            report_lines.append("")

    report_text = "\n".join(report_lines)

    report_dir = Path(sys.argv[1]).parent.parent / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"benchmark_report_{ts}.md"
    report_path.write_text(report_text)
    print(report_text)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
