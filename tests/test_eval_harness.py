"""Tests for the extraction evaluation harness."""

from __future__ import annotations

import json


from benchmarks.extraction_eval.evaluate import (
    _normalize_value,
    _values_match,
    evaluate,
    save_result,
    score_document,
    score_items,
)


class TestNormalizeValue:
    def test_none_returns_none(self):
        assert _normalize_value(None) is None

    def test_empty_string_returns_none(self):
        assert _normalize_value("") is None

    def test_whitespace_returns_none(self):
        assert _normalize_value("  ") is None

    def test_none_string_returns_none(self):
        assert _normalize_value("None") is None

    def test_null_string_returns_none(self):
        assert _normalize_value("null") is None

    def test_strips_and_lowercases(self):
        assert _normalize_value("  Sigma-Aldrich  ") == "sigma-aldrich"

    def test_numeric(self):
        assert _normalize_value(42) == "42"

    def test_float(self):
        assert _normalize_value(3.14) == "3.14"


class TestValuesMatch:
    def test_both_none(self):
        assert _values_match(None, None) is True

    def test_truth_none_pred_value(self):
        assert _values_match(None, "Sigma") is False

    def test_truth_value_pred_none(self):
        assert _values_match("Sigma", None) is False

    def test_exact_match(self):
        assert _values_match("Sigma-Aldrich", "Sigma-Aldrich") is True

    def test_case_insensitive(self):
        assert _values_match("sigma-aldrich", "SIGMA-ALDRICH") is True

    def test_numeric_match(self):
        assert _values_match("10.5", "10.50") is True

    def test_numeric_mismatch(self):
        assert _values_match("10.5", "11.0") is False

    def test_substring_containment(self):
        assert _values_match("Sigma-Aldrich", "Sigma-Aldrich Inc.") is True

    def test_different_values(self):
        assert _values_match("Sigma", "Fisher") is False

    def test_int_and_float_match(self):
        assert _values_match(5, 5.0) is True


class TestScoreDocument:
    def test_perfect_match(self):
        truth = {
            "vendor_name": "Sigma-Aldrich",
            "document_type": "packing_list",
            "po_number": "PO-123",
        }
        predicted = {
            "vendor_name": "Sigma-Aldrich",
            "document_type": "packing_list",
            "po_number": "PO-123",
        }
        score = score_document(truth, predicted, doc_id="1")
        assert score.accuracy == 1.0
        assert score.total_fields == 3
        assert score.correct_fields == 3
        assert score.field_errors == {}

    def test_partial_match(self):
        truth = {
            "vendor_name": "Sigma-Aldrich",
            "document_type": "packing_list",
            "po_number": "PO-123",
        }
        predicted = {
            "vendor_name": "Fisher Scientific",
            "document_type": "packing_list",
            "po_number": "PO-123",
        }
        score = score_document(truth, predicted, doc_id="2")
        assert score.total_fields == 3
        assert score.correct_fields == 2
        assert "vendor_name" in score.field_errors

    def test_missing_predicted_field(self):
        truth = {
            "vendor_name": "Sigma-Aldrich",
            "po_number": "PO-123",
        }
        predicted = {
            "vendor_name": "Sigma-Aldrich",
            "po_number": None,
        }
        score = score_document(truth, predicted, doc_id="3")
        assert score.total_fields == 2
        assert score.correct_fields == 1

    def test_skips_null_truth_fields(self):
        truth = {
            "vendor_name": "Sigma",
            "po_number": None,
        }
        predicted = {
            "vendor_name": "Sigma",
            "po_number": "PO-999",
        }
        score = score_document(truth, predicted, doc_id="4")
        # po_number is None in truth, so not scored
        assert score.total_fields == 1
        assert score.correct_fields == 1


class TestScoreItems:
    def test_matching_items(self):
        truth = [
            {"catalog_number": "S1234", "quantity": 5, "unit": "EA"},
        ]
        predicted = [
            {"catalog_number": "S1234", "quantity": 5.0, "unit": "EA"},
        ]
        scores = score_items(truth, predicted)
        assert scores["catalog_number"].accuracy == 1.0
        assert scores["quantity"].accuracy == 1.0
        assert scores["unit"].accuracy == 1.0

    def test_missing_predicted_item(self):
        truth = [
            {"catalog_number": "S1234", "quantity": 5},
            {"catalog_number": "S5678", "quantity": 3},
        ]
        predicted = [
            {"catalog_number": "S1234", "quantity": 5},
        ]
        scores = score_items(truth, predicted)
        assert scores["catalog_number"].total == 2
        assert scores["catalog_number"].correct == 1
        assert scores["catalog_number"].missing == 1

    def test_empty_truth_items(self):
        scores = score_items([], [{"catalog_number": "X"}])
        assert scores["catalog_number"].total == 0


class TestEvaluate:
    def test_full_evaluation(self):
        ground_truth = [
            {
                "id": 1,
                "extracted_data": {
                    "vendor_name": "Sigma-Aldrich",
                    "document_type": "packing_list",
                    "po_number": "PO-100",
                    "items": [
                        {"catalog_number": "A1234", "quantity": 10},
                    ],
                },
            },
            {
                "id": 2,
                "extracted_data": {
                    "vendor_name": "Fisher Scientific",
                    "document_type": "invoice",
                    "po_number": "PO-200",
                    "items": [],
                },
            },
        ]
        predictions = [
            {
                "id": 1,
                "extracted_data": {
                    "vendor_name": "Sigma-Aldrich",
                    "document_type": "packing_list",
                    "po_number": "PO-100",
                    "items": [
                        {"catalog_number": "A1234", "quantity": 10},
                    ],
                },
            },
            {
                "id": 2,
                "extracted_data": {
                    "vendor_name": "Fisher",
                    "document_type": "invoice",
                    "po_number": "PO-200",
                    "items": [],
                },
            },
        ]
        result = evaluate(ground_truth, predictions, model="test-model")
        assert result.num_documents == 2
        assert result.model == "test-model"
        # vendor_name: 2/2 (Fisher contains in Fisher Scientific)
        # document_type: 2/2, po_number: 2/2
        assert result.overall_accuracy > 0.8

    def test_missing_prediction_skipped(self):
        ground_truth = [
            {
                "id": 1,
                "extracted_data": {"vendor_name": "Sigma", "document_type": "other"},
            },
        ]
        predictions = []  # no predictions
        result = evaluate(ground_truth, predictions, model="test")
        assert result.num_documents == 0

    def test_summary_output(self):
        ground_truth = [
            {
                "id": 1,
                "extracted_data": {"vendor_name": "Sigma", "document_type": "other"},
            },
        ]
        predictions = [
            {
                "id": 1,
                "extracted_data": {"vendor_name": "Sigma", "document_type": "other"},
            },
        ]
        result = evaluate(ground_truth, predictions, model="test")
        summary = result.summary()
        assert "test" in summary
        assert "100.0%" in summary


class TestSaveResult:
    def test_saves_json(self, tmp_path):
        ground_truth = [
            {
                "id": 1,
                "extracted_data": {"vendor_name": "Sigma", "document_type": "other"},
            },
        ]
        predictions = [
            {
                "id": 1,
                "extracted_data": {"vendor_name": "Sigma", "document_type": "other"},
            },
        ]
        result = evaluate(ground_truth, predictions, model="test-save")
        path = save_result(result, tmp_path / "results")
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["model"] == "test-save"
        assert "field_scores" in data
        assert "per_document" in data
