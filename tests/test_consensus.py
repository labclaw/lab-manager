"""Tests for multi-model consensus merge."""

from lab_manager.intake.consensus import consensus_merge


def test_unanimous_agreement():
    extractions = {
        "opus": {"vendor_name": "Sigma", "po_number": "PO-123"},
        "gemini": {"vendor_name": "Sigma", "po_number": "PO-123"},
        "codex": {"vendor_name": "Sigma", "po_number": "PO-123"},
    }
    result = consensus_merge(extractions)
    assert result["vendor_name"] == "Sigma"
    assert result["po_number"] == "PO-123"
    assert result["_consensus"]["vendor_name"]["agreement"] == "unanimous"
    assert result["_needs_human"] is False


def test_majority_two_of_three():
    extractions = {
        "opus": {"vendor_name": "Sigma-Aldrich"},
        "gemini": {"vendor_name": "Sigma-Aldrich"},
        "codex": {"vendor_name": "Sigma"},
    }
    result = consensus_merge(extractions)
    assert result["vendor_name"] == "Sigma-Aldrich"
    assert result["_consensus"]["vendor_name"]["agreement"] == "majority"


def test_majority_records_dissenter():
    extractions = {
        "opus": {"vendor_name": "Sigma-Aldrich"},
        "gemini": {"vendor_name": "Sigma-Aldrich"},
        "codex": {"vendor_name": "Sigma"},
    }
    result = consensus_merge(extractions)
    details = result["_consensus"]["vendor_name"]
    assert "codex" in details["dissenting"]
    assert details["dissenting"]["codex"] == "Sigma"


def test_all_disagree_prefers_opus():
    extractions = {
        "codex_gpt": {"vendor_name": "Vendor-C"},
        "opus_4_6": {"vendor_name": "Vendor-A"},
        "gemini_pro": {"vendor_name": "Vendor-B"},
    }
    result = consensus_merge(extractions)
    assert result["vendor_name"] == "Vendor-A"
    assert result["_consensus"]["vendor_name"]["agreement"] == "none"
    assert result["_needs_human"] is True


def test_all_disagree_prefers_gemini_over_codex():
    extractions = {
        "codex_gpt": {"vendor_name": "Vendor-C"},
        "gemini_pro": {"vendor_name": "Vendor-B"},
        "other_model": {"vendor_name": "Vendor-D"},
    }
    result = consensus_merge(extractions)
    assert result["vendor_name"] == "Vendor-B"


def test_tie_detection():
    extractions = {
        "opus": {"vendor_name": "Sigma"},
        "gemini": {"vendor_name": "Aldrich"},
        "codex": {"vendor_name": "Sigma"},
        "gpt": {"vendor_name": "Aldrich"},
    }
    result = consensus_merge(extractions)
    details = result["_consensus"]["vendor_name"]
    assert details["agreement"] == "tied"
    assert details["needs_human"] is True
    assert result["_needs_human"] is True


def test_single_model():
    extractions = {
        "opus": {"vendor_name": "Sigma", "po_number": "PO-1"},
        "gemini": None,
        "codex": None,
    }
    result = consensus_merge(extractions)
    assert result["vendor_name"] == "Sigma"
    assert result["_consensus"]["method"] == "single_model"
    assert result["_needs_human"] is True


def test_all_models_failed():
    extractions = {
        "opus": None,
        "gemini": None,
        "codex": None,
    }
    result = consensus_merge(extractions)
    assert result["_error"] == "all_models_failed"
    assert result["_needs_human"] is True


def test_none_values_skipped():
    extractions = {
        "opus": {"vendor_name": "Sigma", "po_number": None},
        "gemini": {"vendor_name": "Sigma", "po_number": "PO-1"},
        "codex": {"vendor_name": "Sigma", "po_number": "PO-1"},
    }
    result = consensus_merge(extractions)
    assert result["vendor_name"] == "Sigma"
    assert result["po_number"] == "PO-1"


def test_field_level_independence():
    extractions = {
        "opus": {"vendor_name": "Sigma", "po_number": "PO-1"},
        "gemini": {"vendor_name": "Sigma", "po_number": "PO-2"},
        "codex": {"vendor_name": "Sigma", "po_number": "PO-3"},
    }
    result = consensus_merge(extractions)
    assert result["_consensus"]["vendor_name"]["agreement"] == "unanimous"
    assert result["_consensus"]["po_number"]["agreement"] == "none"
    assert result["_consensus"]["po_number"]["needs_human"] is True


def test_needs_human_propagation():
    extractions = {
        "opus": {"vendor_name": "Sigma", "po_number": "PO-1"},
        "gemini": {"vendor_name": "Sigma", "po_number": "PO-2"},
        "codex": {"vendor_name": "Sigma", "po_number": "PO-3"},
    }
    result = consensus_merge(extractions)
    assert result["_needs_human"] is True


def test_consensus_merge_returns_dict():
    extractions = {
        "opus": {"vendor_name": "Sigma"},
        "gemini": {"vendor_name": "Sigma"},
    }
    result = consensus_merge(extractions)
    assert isinstance(result, dict)
    assert "_consensus" in result
    assert "_needs_human" in result
    assert "_model_count" in result


def test_empty_extractions():
    extractions = {
        "opus": {},
        "gemini": {},
        "codex": {},
    }
    result = consensus_merge(extractions)
    assert isinstance(result, dict)
    assert result["_needs_human"] is False
    assert result["_model_count"] == 3


def test_model_priority_exact_name_wins():
    """Exact model names should take priority over partial matches."""
    extractions = {
        "opus_4_6": {"vendor_name": "A"},
        "gemini_3_1_pro": {"vendor_name": "B"},
        "gpt_5_4": {"vendor_name": "C"},
    }
    result = consensus_merge(extractions)
    # All disagree -> priority fallback picks opus_4_6 (index 0 in MODEL_PRIORITY)
    assert result["vendor_name"] == "A"
    assert result["_consensus"]["vendor_name"]["agreement"] == "none"


def test_model_priority_no_false_substring_match():
    """'opus_review_bot' should NOT get opus priority -- it's not the real opus."""
    extractions = {
        "opus_review_bot": {"vendor_name": "A"},
        "gemini_3_1_pro": {"vendor_name": "B"},
        "random_model": {"vendor_name": "C"},
    }
    result = consensus_merge(extractions)
    # gemini_3_1_pro should win (real model match), not opus_review_bot
    assert result["vendor_name"] == "B"
