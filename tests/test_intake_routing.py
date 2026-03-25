"""Tests for cost-aware document routing."""

from lab_manager.intake.routing import (
    DocumentComplexity,
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
