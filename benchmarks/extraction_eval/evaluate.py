"""Extraction quality evaluation harness.

Compares AI extraction results against human-approved ground truth.
Measures per-field accuracy, precision, recall across documents.

Usage:
    # Export ground truth from DB (approved documents)
    python -m benchmarks.extraction-eval.export_ground_truth

    # Run evaluation against current model
    python -m benchmarks.extraction-eval.evaluate

    # Run evaluation with a specific model override
    EXTRACTION_MODEL=nvidia_nim/z-ai/glm5 python -m benchmarks.extraction-eval.evaluate
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Fields to evaluate (matches ExtractedDocument schema)
SCALAR_FIELDS = [
    "vendor_name",
    "document_type",
    "po_number",
    "order_number",
    "invoice_number",
    "delivery_number",
    "order_date",
    "ship_date",
    "received_date",
    "received_by",
]

ITEM_FIELDS = [
    "catalog_number",
    "description",
    "quantity",
    "unit",
    "lot_number",
    "batch_number",
    "cas_number",
    "storage_temp",
    "unit_price",
]


@dataclass
class FieldScore:
    """Score for a single field across all documents."""

    field_name: str
    total: int = 0  # documents where ground truth has this field
    correct: int = 0  # exact match
    present: int = 0  # model produced a value (even if wrong)
    missing: int = 0  # model returned None when truth has value
    wrong: int = 0  # model returned different value

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0

    @property
    def precision(self) -> float:
        """Of values the model produced, how many were correct."""
        return self.correct / self.present if self.present > 0 else 0.0

    @property
    def recall(self) -> float:
        """Of ground truth values, how many did the model find."""
        return self.correct / self.total if self.total > 0 else 0.0


@dataclass
class DocumentScore:
    """Score for a single document."""

    doc_id: str
    total_fields: int = 0
    correct_fields: int = 0
    field_errors: dict = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        return self.correct_fields / self.total_fields if self.total_fields > 0 else 0.0


@dataclass
class EvalResult:
    """Complete evaluation result."""

    timestamp: str
    model: str
    num_documents: int
    overall_accuracy: float
    field_scores: dict[str, FieldScore]
    document_scores: list[DocumentScore]
    item_field_scores: dict[str, FieldScore]

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Extraction Evaluation — {self.timestamp}",
            f"Model: {self.model}",
            f"Documents: {self.num_documents}",
            f"Overall accuracy: {self.overall_accuracy:.1%}",
            "",
            "Per-field accuracy:",
        ]
        for name, score in sorted(
            self.field_scores.items(), key=lambda x: x[1].accuracy
        ):
            if score.total > 0:
                lines.append(
                    f"  {name:25s}  {score.accuracy:6.1%}  "
                    f"({score.correct}/{score.total})"
                )
        if any(s.total > 0 for s in self.item_field_scores.values()):
            lines.append("")
            lines.append("Per-item-field accuracy:")
            for name, score in sorted(
                self.item_field_scores.items(), key=lambda x: x[1].accuracy
            ):
                if score.total > 0:
                    lines.append(
                        f"  {name:25s}  {score.accuracy:6.1%}  "
                        f"({score.correct}/{score.total})"
                    )
        return "\n".join(lines)


def _normalize_value(val: object) -> Optional[str]:
    """Normalize a value for comparison. Returns None for empty/null values."""
    if val is None:
        return None
    s = str(val).strip().lower()
    if not s or s == "none" or s == "null":
        return None
    return s


def _values_match(truth: object, predicted: object) -> bool:
    """Compare two field values with normalization."""
    t = _normalize_value(truth)
    p = _normalize_value(predicted)
    if t is None and p is None:
        return True
    if t is None or p is None:
        return False
    # Exact match after normalization
    if t == p:
        return True
    # Numeric comparison for quantities/prices
    try:
        return abs(float(t) - float(p)) < 0.01
    except (ValueError, TypeError):
        pass
    # Substring containment (e.g., vendor names with extra suffixes)
    if t in p or p in t:
        return True
    return False


def score_document(
    truth: dict,
    predicted: dict,
    doc_id: str = "",
) -> DocumentScore:
    """Score a single document extraction against ground truth."""
    doc_score = DocumentScore(doc_id=doc_id)

    for f in SCALAR_FIELDS:
        t_val = truth.get(f)
        if _normalize_value(t_val) is None:
            continue  # skip fields not in ground truth
        doc_score.total_fields += 1
        p_val = predicted.get(f)
        if _values_match(t_val, p_val):
            doc_score.correct_fields += 1
        else:
            doc_score.field_errors[f] = {
                "truth": t_val,
                "predicted": p_val,
            }

    return doc_score


def score_items(
    truth_items: list[dict],
    predicted_items: list[dict],
) -> dict[str, FieldScore]:
    """Score line item fields using positional alignment."""
    scores: dict[str, FieldScore] = {f: FieldScore(field_name=f) for f in ITEM_FIELDS}

    for i, t_item in enumerate(truth_items):
        p_item = predicted_items[i] if i < len(predicted_items) else {}
        for f in ITEM_FIELDS:
            t_val = t_item.get(f)
            if _normalize_value(t_val) is None:
                continue
            scores[f].total += 1
            p_val = p_item.get(f)
            if _normalize_value(p_val) is not None:
                scores[f].present += 1
            else:
                scores[f].missing += 1
            if _values_match(t_val, p_val):
                scores[f].correct += 1
            elif _normalize_value(p_val) is not None:
                scores[f].wrong += 1

    return scores


def evaluate(
    ground_truth: list[dict],
    predictions: list[dict],
    model: str = "unknown",
) -> EvalResult:
    """Run full evaluation of predictions against ground truth.

    Args:
        ground_truth: List of dicts with 'id' and 'extracted_data' keys.
        predictions: List of dicts with 'id' and 'extracted_data' keys.
        model: Model name for reporting.

    Returns:
        EvalResult with per-field and per-document scores.
    """
    pred_by_id = {str(p["id"]): p["extracted_data"] for p in predictions}

    field_scores: dict[str, FieldScore] = {
        f: FieldScore(field_name=f) for f in SCALAR_FIELDS
    }
    all_item_scores: dict[str, FieldScore] = {
        f: FieldScore(field_name=f) for f in ITEM_FIELDS
    }
    doc_scores: list[DocumentScore] = []

    for gt in ground_truth:
        doc_id = str(gt["id"])
        truth_data = gt["extracted_data"]
        pred_data = pred_by_id.get(doc_id, {})

        if not pred_data:
            logger.warning("No prediction for document %s, skipping", doc_id)
            continue

        # Score scalar fields
        ds = score_document(truth_data, pred_data, doc_id=doc_id)
        doc_scores.append(ds)

        for f in SCALAR_FIELDS:
            t_val = truth_data.get(f)
            if _normalize_value(t_val) is None:
                continue
            field_scores[f].total += 1
            p_val = pred_data.get(f)
            if _normalize_value(p_val) is not None:
                field_scores[f].present += 1
            else:
                field_scores[f].missing += 1
            if _values_match(t_val, p_val):
                field_scores[f].correct += 1
            elif _normalize_value(p_val) is not None:
                field_scores[f].wrong += 1

        # Score items
        truth_items = truth_data.get("items", [])
        pred_items = pred_data.get("items", [])
        if truth_items:
            item_scores = score_items(truth_items, pred_items)
            for f, s in item_scores.items():
                all_item_scores[f].total += s.total
                all_item_scores[f].correct += s.correct
                all_item_scores[f].present += s.present
                all_item_scores[f].missing += s.missing
                all_item_scores[f].wrong += s.wrong

    total_fields = sum(ds.total_fields for ds in doc_scores)
    total_correct = sum(ds.correct_fields for ds in doc_scores)
    overall = total_correct / total_fields if total_fields > 0 else 0.0

    return EvalResult(
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
        model=model,
        num_documents=len(doc_scores),
        overall_accuracy=overall,
        field_scores=field_scores,
        document_scores=doc_scores,
        item_field_scores=all_item_scores,
    )


def save_result(result: EvalResult, output_dir: Path) -> Path:
    """Save evaluation result to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"eval-{result.model.replace('/', '-')}-{result.timestamp}.json"
    path = output_dir / filename

    data = {
        "timestamp": result.timestamp,
        "model": result.model,
        "num_documents": result.num_documents,
        "overall_accuracy": result.overall_accuracy,
        "field_scores": {
            name: {
                "accuracy": s.accuracy,
                "precision": s.precision,
                "recall": s.recall,
                "total": s.total,
                "correct": s.correct,
                "present": s.present,
                "missing": s.missing,
                "wrong": s.wrong,
            }
            for name, s in result.field_scores.items()
        },
        "item_field_scores": {
            name: {
                "accuracy": s.accuracy,
                "precision": s.precision,
                "recall": s.recall,
                "total": s.total,
                "correct": s.correct,
            }
            for name, s in result.item_field_scores.items()
        },
        "per_document": [
            {
                "id": ds.doc_id,
                "accuracy": ds.accuracy,
                "total_fields": ds.total_fields,
                "correct_fields": ds.correct_fields,
                "errors": ds.field_errors,
            }
            for ds in result.document_scores
        ],
    }

    path.write_text(json.dumps(data, indent=2))
    logger.info("Saved evaluation to %s", path)
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    gt_path = Path(__file__).parent / "ground_truth.json"
    if not gt_path.exists():
        print(f"Ground truth not found at {gt_path}")
        print("Run: python -m benchmarks.extraction-eval.export_ground_truth")
        sys.exit(1)

    ground_truth = json.loads(gt_path.read_text())
    print(f"Loaded {len(ground_truth)} ground truth documents")

    # Re-extract each document with current model
    from lab_manager.config import get_settings
    from lab_manager.intake.extractor import extract_from_text

    settings = get_settings()
    model = settings.extraction_model
    print(f"Extracting with model: {model}")

    predictions = []
    for gt in ground_truth:
        ocr_text = gt.get("ocr_text", "")
        if not ocr_text:
            continue
        result = extract_from_text(ocr_text)
        if result:
            predictions.append(
                {
                    "id": gt["id"],
                    "extracted_data": result.model_dump(),
                }
            )

    eval_result = evaluate(ground_truth, predictions, model=model)
    print(eval_result.summary())

    output_dir = Path(__file__).parent / "results"
    save_result(eval_result, output_dir)
