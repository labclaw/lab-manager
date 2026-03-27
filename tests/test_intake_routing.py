"""Tests for cost-aware document routing."""

import pytest

from lab_manager.intake.routing import (
    COMPLEX_DOC_TYPES,
    COMPLEXITY_KEYWORDS,
    SIMPLE_DOC_TYPES,
    DocumentComplexity,
    RoutingDecision,
    route_document,
    score_complexity,
)


# ---------------------------------------------------------------------------
# score_complexity
# ---------------------------------------------------------------------------


class TestScoreComplexity:
    def test_empty_text_low_scores(self):
        scores = score_complexity("", document_type=None)
        assert scores["text_length"] == 0.1
        assert scores["keyword_density"] == 0.0
        assert scores["line_count"] == 0.1

    def test_simple_doc_type_scores_low(self):
        scores = score_complexity("some text", document_type="shipping_label")
        assert scores["doc_type"] == 0.1

    def test_complex_doc_type_scores_high(self):
        scores = score_complexity("some text", document_type="invoice")
        assert scores["doc_type"] == 0.9

    def test_unknown_doc_type_scores_medium(self):
        scores = score_complexity("some text", document_type="other")
        assert scores["doc_type"] == 0.5

    def test_long_text_scores_high(self):
        long_text = "line\n" * 500
        scores = score_complexity(long_text)
        assert scores["text_length"] == 0.9
        assert scores["line_count"] == 0.9

    def test_keyword_density(self):
        text = "catalog number qty lot number cas number unit price subtotal po number certificate purity"
        scores = score_complexity(text)
        assert scores["keyword_density"] > 0.5

    def test_item_count_hint(self):
        scores = score_complexity("text", num_items_hint=1)
        assert scores["item_count"] == 0.1
        scores = score_complexity("text", num_items_hint=10)
        assert scores["item_count"] == 0.9

    def test_no_item_count_hint_omits_key(self):
        scores = score_complexity("text")
        assert "item_count" not in scores


# ---------------------------------------------------------------------------
# route_document
# ---------------------------------------------------------------------------


class TestRouteDocument:
    def test_simple_shipping_label(self):
        decision = route_document(
            ocr_text="FedEx\nTracking: 1234",
            document_type="shipping_label",
        )
        assert decision.complexity == DocumentComplexity.low
        assert decision.num_models == 1
        assert decision.skip_review is True

    def test_complex_invoice_many_items(self):
        lines = [
            "INVOICE #12345",
            "Vendor: Sigma-Aldrich",
            "PO Number: PO-2026-001",
        ]
        for i in range(20):
            lines.append(
                f"Cat# A{i:04d}  Qty: {i + 1}  Lot Number: L{i:03d}  "
                f"Unit Price: ${10 * i:.2f}  CAS Number: 123-45-{i}"
            )
        lines.append("Subtotal: $5000.00")
        lines.append("Total: $5250.00")
        text = "\n".join(lines)

        decision = route_document(ocr_text=text, document_type="invoice")
        assert decision.complexity == DocumentComplexity.high
        assert decision.num_models == 3
        assert decision.skip_review is False

    def test_medium_complexity(self):
        text = (
            "Packing List\nOrder #456\n"
            "Item 1: Catalog ABC-123, Qty 2, Lot L001\n"
            "Item 2: Catalog DEF-456, Qty 1, Lot L002\n"
        )
        decision = route_document(ocr_text=text, document_type="quote")
        assert decision.complexity in (
            DocumentComplexity.low,
            DocumentComplexity.medium,
        )
        assert decision.num_models <= 2

    def test_force_complexity_overrides(self):
        decision = route_document(
            ocr_text="very short",
            document_type="shipping_label",
            force_complexity=DocumentComplexity.high,
        )
        assert decision.complexity == DocumentComplexity.high
        assert decision.num_models == 3
        assert "forced" in decision.reason

    def test_decision_has_scores(self):
        decision = route_document(ocr_text="some text")
        assert isinstance(decision.scores, dict)
        assert "text_length" in decision.scores

    def test_forced_decision_has_empty_scores(self):
        decision = route_document(
            ocr_text="text",
            force_complexity=DocumentComplexity.low,
        )
        assert decision.scores == {}


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestRoutingEdgeCases:
    def test_none_ocr_text_treated_as_empty(self):
        """Empty/None OCR should route to low complexity."""
        decision = route_document(ocr_text="")
        assert decision.complexity == DocumentComplexity.low

    def test_coa_always_high(self):
        """COA with decent text should always be high complexity."""
        text = (
            "Certificate of Analysis\n"
            "Product: Sodium Chloride\n"
            "Catalog Number: S7653\n"
            "Lot Number: SLCD1234\n"
            "CAS Number: 7647-14-5\n"
            "Purity: >=99.5%\n"
            "Assay (dry basis): 99.8%\n"
            "Specification: ACS reagent grade\n"
            "Heavy metals: <5 ppm\n"
            "Iron: <0.4 ppm\n"
        )
        decision = route_document(
            ocr_text=text, document_type="certificate_of_analysis"
        )
        assert decision.complexity == DocumentComplexity.high

    def test_receipt_is_simple(self):
        decision = route_document(
            ocr_text="Receipt\nAmount: $50\nThank you",
            document_type="receipt",
        )
        assert decision.complexity == DocumentComplexity.low


# ---------------------------------------------------------------------------
# DocumentComplexity enum
# ---------------------------------------------------------------------------


class TestDocumentComplexity:
    """Tests for the DocumentComplexity enum."""

    def test_enum_values(self):
        assert DocumentComplexity.low.value == "low"
        assert DocumentComplexity.medium.value == "medium"
        assert DocumentComplexity.high.value == "high"

    def test_enum_from_string(self):
        assert DocumentComplexity("low") == DocumentComplexity.low
        assert DocumentComplexity("medium") == DocumentComplexity.medium
        assert DocumentComplexity("high") == DocumentComplexity.high

    def test_enum_invalid_value_raises(self):
        with pytest.raises(ValueError):
            DocumentComplexity("extreme")

    def test_enum_is_string(self):
        assert isinstance(DocumentComplexity.low, str)
        assert DocumentComplexity.low == "low"


# ---------------------------------------------------------------------------
# RoutingDecision dataclass
# ---------------------------------------------------------------------------


class TestRoutingDecision:
    """Tests for the RoutingDecision dataclass."""

    def test_creation(self):
        rd = RoutingDecision(
            complexity=DocumentComplexity.low,
            num_models=1,
            skip_review=True,
            reason="test",
        )
        assert rd.complexity == DocumentComplexity.low
        assert rd.num_models == 1
        assert rd.skip_review is True
        assert rd.reason == "test"
        assert rd.scores == {}

    def test_default_scores_empty(self):
        rd = RoutingDecision(
            complexity=DocumentComplexity.high,
            num_models=3,
            skip_review=False,
            reason="complex",
        )
        assert rd.scores == {}

    def test_scores_populated(self):
        rd = RoutingDecision(
            complexity=DocumentComplexity.medium,
            num_models=2,
            skip_review=True,
            reason="moderate",
            scores={"doc_type": 0.5, "text_length": 0.3},
        )
        assert rd.scores["doc_type"] == 0.5
        assert rd.scores["text_length"] == 0.3


# ---------------------------------------------------------------------------
# Additional score_complexity coverage
# ---------------------------------------------------------------------------


class TestScoreComplexityAdditional:
    """Additional tests for score_complexity signal coverage."""

    def test_none_text_handled(self):
        scores = score_complexity(None)
        assert scores["text_length"] == 0.1
        assert scores["line_count"] == 0.1

    def test_all_simple_doc_types(self):
        for dt in SIMPLE_DOC_TYPES:
            scores = score_complexity("short text", document_type=dt)
            assert scores["doc_type"] == 0.1, f"{dt} should score 0.1"

    def test_all_complex_doc_types(self):
        for dt in COMPLEX_DOC_TYPES:
            scores = score_complexity("text", document_type=dt)
            assert scores["doc_type"] == 0.9, f"{dt} should score 0.9"

    def test_unknown_doc_type_string(self):
        scores = score_complexity("text", document_type="unknown_thing")
        assert scores["doc_type"] == 0.5

    def test_no_doc_type_mid_score(self):
        scores = score_complexity("text")
        assert scores["doc_type"] == 0.5

    def test_short_text_below_200(self):
        scores = score_complexity("a" * 100)
        assert scores["text_length"] == 0.1

    def test_medium_text_200_to_800(self):
        scores = score_complexity("a" * 500)
        assert scores["text_length"] == 0.3

    def test_long_text_800_to_2000(self):
        scores = score_complexity("a" * 1000)
        assert scores["text_length"] == 0.6

    def test_keyword_density_capped_at_one(self):
        text = " ".join(COMPLEXITY_KEYWORDS)
        scores = score_complexity(text)
        assert scores["keyword_density"] <= 1.0

    def test_line_count_moderate(self):
        text = "\n".join(["line"] * 20)
        scores = score_complexity(text)
        assert scores["line_count"] == 0.4

    def test_line_count_many(self):
        text = "\n".join(["line"] * 40)
        scores = score_complexity(text)
        assert scores["line_count"] == 0.7

    def test_line_count_very_many(self):
        text = "\n".join(["line"] * 80)
        scores = score_complexity(text)
        assert scores["line_count"] == 0.9

    def test_item_count_hint_few(self):
        scores = score_complexity("text", num_items_hint=3)
        assert scores["item_count"] == 0.5

    def test_item_count_hint_zero(self):
        scores = score_complexity("text", num_items_hint=0)
        assert scores["item_count"] == 0.1

    def test_all_signals_present(self):
        scores = score_complexity(
            "catalog qty lot number total\n" * 50,
            document_type="invoice",
            num_items_hint=8,
        )
        assert "doc_type" in scores
        assert "text_length" in scores
        assert "keyword_density" in scores
        assert "line_count" in scores
        assert "item_count" in scores


# ---------------------------------------------------------------------------
# Additional route_document coverage
# ---------------------------------------------------------------------------


class TestRouteDocumentAdditional:
    """Additional tests for route_document decisions."""

    def test_force_complexity_medium(self):
        rd = route_document(
            "text",
            force_complexity=DocumentComplexity.medium,
        )
        assert rd.complexity == DocumentComplexity.medium
        assert rd.num_models == 2
        assert rd.reason == "forced to medium"

    def test_force_complexity_high_skip_review_false(self):
        rd = route_document(
            "short",
            force_complexity=DocumentComplexity.high,
        )
        assert rd.skip_review is False

    def test_force_complexity_low_skip_review_true(self):
        rd = route_document(
            "huge complex text with lots of stuff",
            force_complexity=DocumentComplexity.low,
        )
        assert rd.skip_review is True

    def test_reason_includes_score_for_auto_routing(self):
        rd = route_document("sample text", document_type="mta")
        assert "score=" in rd.reason

    def test_returns_routing_decision_type(self):
        rd = route_document("text")
        assert isinstance(rd, RoutingDecision)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    def test_simple_doc_types_subset(self):
        assert SIMPLE_DOC_TYPES == {"shipping_label", "receipt", "mta"}

    def test_complex_doc_types_subset(self):
        assert COMPLEX_DOC_TYPES == {
            "invoice",
            "certificate_of_analysis",
            "packing_list",
        }

    def test_no_overlap_between_simple_and_complex(self):
        assert SIMPLE_DOC_TYPES.isdisjoint(COMPLEX_DOC_TYPES)

    def test_complexity_keywords_is_nonempty_list(self):
        assert isinstance(COMPLEXITY_KEYWORDS, list)
        assert len(COMPLEXITY_KEYWORDS) > 0

    def test_complexity_keywords_all_lowercase(self):
        for kw in COMPLEXITY_KEYWORDS:
            assert kw == kw.lower(), f"Keyword '{kw}' should be lowercase"
