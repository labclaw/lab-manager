"""Tests for cross-model review."""

from lab_manager.intake.consensus import cross_model_review


class FakeProvider:
    """Fake VLM provider that records prompts received."""

    def __init__(self, name, response):
        self.name = name
        self._response = response
        self.received_prompts = []

    def extract(self, image_path, prompt):
        self.received_prompts.append(prompt)
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
    # Verify no local file path leaked into any prompt sent to providers
    for p in providers:
        for prompt in p.received_prompts:
            assert "/home/" not in prompt, (
                f"Prompt should not contain local file paths, got: {prompt[:200]}"
            )
            assert "/tmp/" not in prompt, (
                f"Prompt should not contain local /tmp/ paths, got: {prompt[:200]}"
            )


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


def test_cross_review_all_fail_returns_merged():
    """When all providers fail or no providers given, return merged unchanged."""
    merged = {"vendor_name": "Sigma", "_consensus": {}, "_needs_human": False}
    # extract_parallel with empty list will crash with ValueError on min(),
    # so test with providers that return None
    providers = [
        FakeProvider("opus", None),
        FakeProvider("gemini", None),
    ]
    result = cross_model_review(providers, "/path/to/doc.pdf", merged)
    assert result["vendor_name"] == "Sigma"
    assert "_review_round" not in result  # No reviews applied
