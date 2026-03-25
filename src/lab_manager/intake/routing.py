"""Cost-aware model routing for document intake pipeline.

Inspired by OpenClaw's intelligent cost router: simple documents use a single
high-quality model, while complex documents go through the full multi-model
consensus pipeline.  This avoids wasting 3x VLM calls on straightforward
shipping labels while maintaining accuracy for dense invoices and COAs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from lab_manager.intake.schemas import VALID_DOC_TYPES

log = logging.getLogger(__name__)


class DocumentComplexity(str, Enum):
    """Complexity tier that determines the extraction strategy."""

    low = "low"  # single model, auto-approve if confident
    medium = "medium"  # two models, majority vote
    high = "high"  # full 3-model consensus + cross-review


@dataclass
class RoutingDecision:
    """Result of the routing decision for a document."""

    complexity: DocumentComplexity
    num_models: int
    skip_review: bool
    reason: str
    scores: dict[str, float] = field(default_factory=dict)


# ---- Complexity scoring signals ----

# Document types known to be simple (short, few fields)
SIMPLE_DOC_TYPES = {"shipping_label", "receipt", "mta"}

# Document types known to be complex (many line items, critical data)
COMPLEX_DOC_TYPES = {"invoice", "certificate_of_analysis", "packing_list"}

# Keywords that signal complex / multi-item documents
COMPLEXITY_KEYWORDS = [
    "catalog",
    "cat#",
    "cat no",
    "item no",
    "qty",
    "quantity",
    "lot number",
    "batch",
    "cas number",
    "unit price",
    "subtotal",
    "total",
    "po number",
    "purchase order",
    "certificate",
    "specification",
    "purity",
    "assay",
    "grade",
]


def score_complexity(
    ocr_text: str,
    document_type: Optional[str] = None,
    num_items_hint: Optional[int] = None,
) -> dict[str, float]:
    """Score document complexity on multiple signals.

    Returns a dict of signal names to scores (0.0-1.0).
    """
    scores: dict[str, float] = {}

    # Signal 1: Document type
    if document_type:
        dt = document_type.lower().strip()
        if dt in SIMPLE_DOC_TYPES:
            scores["doc_type"] = 0.1
        elif dt in COMPLEX_DOC_TYPES:
            scores["doc_type"] = 0.9
        elif dt in VALID_DOC_TYPES:
            scores["doc_type"] = 0.5
        else:
            scores["doc_type"] = 0.5
    else:
        scores["doc_type"] = 0.5

    # Signal 2: OCR text length (longer = more complex)
    text_len = len(ocr_text) if ocr_text else 0
    if text_len < 200:
        scores["text_length"] = 0.1
    elif text_len < 800:
        scores["text_length"] = 0.3
    elif text_len < 2000:
        scores["text_length"] = 0.6
    else:
        scores["text_length"] = 0.9

    # Signal 3: Keyword density
    lower_text = ocr_text.lower() if ocr_text else ""
    hits = sum(1 for kw in COMPLEXITY_KEYWORDS if kw in lower_text)
    scores["keyword_density"] = min(hits / 8, 1.0)

    # Signal 4: Line count (proxy for tabular data / many items)
    line_count = ocr_text.count("\n") + 1 if ocr_text else 0
    if line_count < 10:
        scores["line_count"] = 0.1
    elif line_count < 30:
        scores["line_count"] = 0.4
    elif line_count < 60:
        scores["line_count"] = 0.7
    else:
        scores["line_count"] = 0.9

    # Signal 5: Explicit item count hint (from pre-scan or metadata)
    if num_items_hint is not None:
        if num_items_hint <= 1:
            scores["item_count"] = 0.1
        elif num_items_hint <= 5:
            scores["item_count"] = 0.5
        else:
            scores["item_count"] = 0.9

    return scores


def route_document(
    ocr_text: str,
    document_type: Optional[str] = None,
    num_items_hint: Optional[int] = None,
    force_complexity: Optional[DocumentComplexity] = None,
) -> RoutingDecision:
    """Decide extraction strategy based on document complexity.

    Parameters
    ----------
    ocr_text : str
        Raw OCR text for the document.
    document_type : str, optional
        Pre-classified document type (from filename or metadata).
    num_items_hint : int, optional
        Number of line items expected (e.g., from a quick regex scan).
    force_complexity : DocumentComplexity, optional
        Override automatic routing (for testing or manual control).
    """
    if force_complexity is not None:
        return RoutingDecision(
            complexity=force_complexity,
            num_models={"low": 1, "medium": 2, "high": 3}[force_complexity.value],
            skip_review=force_complexity != DocumentComplexity.high,
            reason=f"forced to {force_complexity.value}",
            scores={},
        )

    scores = score_complexity(ocr_text, document_type, num_items_hint)

    # Weighted average — doc_type and keyword_density matter most
    weights = {
        "doc_type": 0.30,
        "text_length": 0.15,
        "keyword_density": 0.30,
        "line_count": 0.15,
        "item_count": 0.10,
    }
    total_weight = sum(weights.get(k, 0.1) for k in scores)
    weighted = sum(scores[k] * weights.get(k, 0.1) for k in scores)
    composite = weighted / total_weight if total_weight > 0 else 0.5

    # Tier thresholds
    if composite < 0.30:
        complexity = DocumentComplexity.low
        num_models = 1
        skip_review = True
        reason = f"simple document (score={composite:.2f})"
    elif composite < 0.60:
        complexity = DocumentComplexity.medium
        num_models = 2
        skip_review = True
        reason = f"moderate complexity (score={composite:.2f})"
    else:
        complexity = DocumentComplexity.high
        num_models = 3
        skip_review = False
        reason = f"complex document (score={composite:.2f})"

    log.info(
        "Routing decision: %s (score=%.2f, models=%d)",
        complexity.value,
        composite,
        num_models,
    )
    return RoutingDecision(
        complexity=complexity,
        num_models=num_models,
        skip_review=skip_review,
        reason=reason,
        scores=scores,
    )
