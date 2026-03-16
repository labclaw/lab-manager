"""Tests for OCR module."""


def test_mime_type_mapping():
    """Verify correct MIME types for common image formats."""
    from lab_manager.intake.ocr import _get_mime_type

    assert _get_mime_type("doc.jpg") == "image/jpeg"
    assert _get_mime_type("doc.jpeg") == "image/jpeg"
    assert _get_mime_type("doc.png") == "image/png"
    assert _get_mime_type("doc.tif") == "image/tiff"
    assert _get_mime_type("doc.tiff") == "image/tiff"
    assert _get_mime_type("doc.pdf") == "application/pdf"
    assert _get_mime_type("doc.webp") == "image/webp"
    assert _get_mime_type("doc.bmp") == "image/bmp"
    assert _get_mime_type("doc.gif") == "image/gif"


def test_mime_type_case_insensitive():
    """Extension should be matched case-insensitively."""
    from lab_manager.intake.ocr import _get_mime_type

    assert _get_mime_type("DOC.JPG") == "image/jpeg"
    assert _get_mime_type("DOC.PDF") == "application/pdf"
    assert _get_mime_type("DOC.TIF") == "image/tiff"


def test_mime_type_unknown_extension():
    """Unknown extensions should fall back to image/{ext}."""
    from lab_manager.intake.ocr import _get_mime_type

    assert _get_mime_type("doc.svg") == "image/svg"
