"""Tests for cross-model review."""

from lab_manager.intake.consensus import cross_model_review


class FakeProvider:
    def __init__(self, name, response):
        self.name = name
        self._response = response

    def extract(self, image_path, prompt):
        # Verify the prompt does NOT contain the raw file path
        assert "/home/" not in prompt, "Prompt should not contain local file paths"
        assert "/tmp/" not in prompt, "Prompt should not contain local file paths"
        return self._response


def test_cross_review_no_file_path_in_prompt():
    """cross_model_review should not embed local file paths in API prompts."""
    providers = [
        FakeProvider("opus", {"vendor_name": "Sigma", "review_notes": "looks good"}),
        FakeProvider("gemini", {"vendor_name": "Sigma", "review_notes": "ok"}),
    ]
    merged = {"vendor_name": "Sigma", "_consensus": {}, "_needs_human": False}
    result = cross_model_review(
        providers, "/home/user/scans/doc001.pdf", merged, ocr_text="OCR text here"
    )
    assert result["vendor_name"] == "Sigma"


def test_cross_review_applies_majority_correction():
    """Majority review corrections should be applied."""
    providers = [
        FakeProvider("opus", {"vendor_name": "Sigma-Aldrich"}),
        FakeProvider("gemini", {"vendor_name": "Sigma-Aldrich"}),
        FakeProvider("codex", {"vendor_name": "Sigma"}),
    ]
    merged = {"vendor_name": "Sigma", "_consensus": {}, "_needs_human": False}
    result = cross_model_review(
        providers, "/path/to/doc.pdf", merged, ocr_text="Sigma-Aldrich"
    )
    assert result["vendor_name"] == "Sigma-Aldrich"
    assert "vendor_name" in result["_review_round"]["corrections_applied"]


def test_cross_review_no_correction_without_majority():
    """Without majority agreement, original value should be kept."""
    providers = [
        FakeProvider("opus", {"vendor_name": "A"}),
        FakeProvider("gemini", {"vendor_name": "B"}),
        FakeProvider("codex", {"vendor_name": "C"}),
    ]
    merged = {"vendor_name": "Original", "_consensus": {}, "_needs_human": False}
    result = cross_model_review(providers, "/path/to/doc.pdf", merged, ocr_text="text")
    assert result["vendor_name"] == "Original"


def test_cross_review_no_providers():
    """With no valid reviews, should return merged unchanged."""
    providers = []
    merged = {"vendor_name": "Sigma", "_consensus": {}, "_needs_human": False}
    result = cross_model_review(providers, "/path/to/doc.pdf", merged)
    assert result["vendor_name"] == "Sigma"
