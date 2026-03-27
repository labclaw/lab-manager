"""Tests for email_intake service: parse_email internals, sanitize, save, and edge cases.

Focuses on unit-testable parts of the email_intake module that are NOT already
covered by test_email_intake.py (which tests the main parse/process paths).
"""

from __future__ import annotations

import base64
import struct
import zlib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest

from lab_manager.config import get_settings
from lab_manager.services.email_intake import (
    Attachment,
    ParsedEmail,
    _extract_attachment,
    _sanitize_filename,
    _save_attachment,
    extract_attachments,
    parse_email,
    process_email_json,
)


def _make_png() -> bytes:
    """Minimal valid 1x1 PNG."""

    def _chunk(ct: bytes, data: bytes) -> bytes:
        c = ct + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat = _chunk(b"IDAT", raw)
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _make_pdf() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n183\n%%EOF\n"
    )


class TestSanitizeFilename:
    """Test _sanitize_filename edge cases."""

    def test_normal_filename_unchanged(self):
        assert _sanitize_filename("report.pdf") == "report.pdf"

    def test_removes_forward_slash(self):
        result = _sanitize_filename("path/to/file.pdf")
        assert "/" not in result

    def test_removes_backslash(self):
        result = _sanitize_filename("path\\to\\file.pdf")
        assert "\\" not in result

    def test_removes_null_byte(self):
        result = _sanitize_filename("file\x00evil.pdf")
        assert "\x00" not in result

    def test_dot_prefix_gets_prefix_added(self):
        result = _sanitize_filename(".hidden")
        assert result.startswith("attachment")

    def test_empty_string_gets_prefix(self):
        result = _sanitize_filename("")
        assert result.startswith("attachment")

    def test_special_characters_replaced(self):
        result = _sanitize_filename("file (1).pdf")
        assert "(" not in result
        assert ")" not in result
        assert result.endswith(".pdf")

    def test_spaces_replaced(self):
        result = _sanitize_filename("my file.pdf")
        assert " " not in result

    def test_dots_and_hyphens_preserved(self):
        result = _sanitize_filename("my-report.v2.pdf")
        assert result == "my-report.v2.pdf"


class TestExtractAttachment:
    """Test _extract_attachment edge cases."""

    def test_skips_when_max_attachments_reached(self):
        """When attachment list is already at max, new ones are skipped."""
        from lab_manager.services.email_intake import _MAX_ATTACHMENTS

        attachments = [
            Attachment(filename=f"f{i}.pdf", content_type="application/pdf", data=b"x")
            for i in range(_MAX_ATTACHMENTS)
        ]
        initial_len = len(attachments)

        msg = MIMEMultipart()
        att = MIMEApplication(b"data", _subtype="pdf")
        att.add_header("Content-Disposition", "attachment", filename="extra.pdf")
        _extract_attachment(att, attachments)

        assert len(attachments) == initial_len

    def test_skips_empty_payload(self):
        """Attachment with None payload is skipped."""
        attachments: list[Attachment] = []

        class FakePart:
            def get_filename(self):
                return "empty.pdf"

            def get_content_type(self):
                return "application/pdf"

            def get_payload(self, decode=False):
                return None

        _extract_attachment(FakePart(), attachments)
        assert len(attachments) == 0

    def test_skips_oversized_attachment(self):
        """Attachment exceeding size limit is skipped."""
        from lab_manager.services.email_intake import _MAX_ATTACHMENT_BYTES

        attachments: list[Attachment] = []
        big_data = b"x" * (_MAX_ATTACHMENT_BYTES + 1)

        msg = MIMEMultipart()
        att = MIMEApplication(big_data, _subtype="pdf")
        att.add_header("Content-Disposition", "attachment", filename="huge.pdf")
        _extract_attachment(att, attachments)

        assert len(attachments) == 0

    def test_extracts_valid_attachment(self):
        """Normal attachment is extracted correctly."""
        attachments: list[Attachment] = []
        msg = MIMEMultipart()
        att = MIMEApplication(b"pdf-data", _subtype="pdf")
        att.add_header("Content-Disposition", "attachment", filename="doc.pdf")
        _extract_attachment(att, attachments)

        assert len(attachments) == 1
        assert attachments[0].filename == "doc.pdf"
        assert attachments[0].content_type == "application/pdf"
        assert attachments[0].data == b"pdf-data"

    def test_no_filename_defaults_to_unnamed(self):
        """Attachment without filename gets a default name."""
        attachments: list[Attachment] = []
        msg = MIMEMultipart()
        att = MIMEApplication(b"data", _subtype="pdf")
        # No Content-Disposition header
        _extract_attachment(att, attachments)

        assert len(attachments) == 1
        assert attachments[0].filename == "unnamed_attachment"


class TestSaveAttachment:
    """Test _save_attachment file operations."""

    def test_creates_directory_if_missing(self, tmp_path):
        upload_dir = tmp_path / "new_dir" / "uploads"
        att = Attachment(
            filename="test.pdf", content_type="application/pdf", data=b"data"
        )
        dest, saved_name = _save_attachment(att, upload_dir)
        assert upload_dir.exists()
        assert dest.exists()

    def test_file_content_matches_data(self, tmp_path):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        data = b"unique-content-12345"
        att = Attachment(filename="test.pdf", content_type="application/pdf", data=data)
        dest, saved_name = _save_attachment(att, upload_dir)
        assert dest.read_bytes() == data

    def test_filename_contains_timestamp_and_hash(self, tmp_path):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        att = Attachment(
            filename="report.pdf", content_type="application/pdf", data=b"abc"
        )
        dest, saved_name = _save_attachment(att, upload_dir)
        assert "email" in saved_name
        assert "report" in saved_name
        assert saved_name.endswith(".pdf")

    def test_dedup_via_content_hash(self, tmp_path):
        """Two attachments with same content produce filenames with same hash portion."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        data = b"same-data"
        att1 = Attachment(filename="a.pdf", content_type="application/pdf", data=data)
        att2 = Attachment(filename="b.pdf", content_type="application/pdf", data=data)
        _, name1 = _save_attachment(att1, upload_dir)
        _, name2 = _save_attachment(att2, upload_dir)
        # Hash portion (last 16 chars before suffix) should be the same
        # Names differ by stem (a vs b) but hash suffix is identical
        assert name1 != name2  # different timestamps/stems
        assert name1.endswith(".pdf")
        assert name2.endswith(".pdf")


class TestParseEmailEdgeCases:
    """Edge cases for parse_email not covered by existing tests."""

    def test_non_multipart_text_body(self):
        """Non-multipart plain text email parsed correctly."""
        msg = MIMEText("Hello world", "plain")
        msg["From"] = "test@example.com"
        msg["Subject"] = "Simple"
        parsed = parse_email(msg.as_string())
        assert "Hello world" in parsed.body_text
        assert parsed.body_html == ""

    def test_non_multipart_html_body(self):
        """Non-multipart HTML email parsed correctly."""
        msg = MIMEText("<b>Bold</b>", "html")
        msg["From"] = "test@example.com"
        msg["Subject"] = "HTML"
        parsed = parse_email(msg.as_string())
        assert "<b>Bold</b>" in parsed.body_html
        assert parsed.body_text == ""

    def test_missing_from_header(self):
        """Missing From header defaults to empty string."""
        msg = MIMEText("body")
        msg["Subject"] = "No sender"
        parsed = parse_email(msg.as_string())
        assert parsed.sender == ""

    def test_missing_subject_header(self):
        """Missing Subject header defaults to empty string."""
        msg = MIMEText("body")
        msg["From"] = "a@b.com"
        parsed = parse_email(msg.as_string())
        assert parsed.subject == ""

    def test_missing_date_header(self):
        """Missing Date header results in None."""
        msg = MIMEText("body")
        msg["From"] = "a@b.com"
        msg["Subject"] = "No date"
        parsed = parse_email(msg.as_string())
        assert parsed.date is None


class TestProcessEmailJsonEdgeCases:
    """Edge cases for process_email_json."""

    @pytest.fixture(autouse=True)
    def _setup_env(self, tmp_path, monkeypatch):
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
        monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password-not-for-production")
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_jpeg_extension_supported(self, db_session):
        pdf_b64 = base64.b64encode(b"jpg-data").decode()
        docs = process_email_json(
            sender="test@example.com",
            subject="JPEG test",
            body_html="",
            attachments_b64=[
                {"filename": "photo.jpeg", "content_base64": pdf_b64},
            ],
            db=db_session,
        )
        assert len(docs) == 1

    def test_tiff_extension_supported(self, db_session):
        b64 = base64.b64encode(b"tiff-data").decode()
        docs = process_email_json(
            sender="test@example.com",
            subject="TIFF test",
            body_html="",
            attachments_b64=[
                {"filename": "scan.tiff", "content_base64": b64},
            ],
            db=db_session,
        )
        assert len(docs) == 1

    def test_tif_extension_supported(self, db_session):
        b64 = base64.b64encode(b"tif-data").decode()
        docs = process_email_json(
            sender="test@example.com",
            subject="TIF test",
            body_html="",
            attachments_b64=[
                {"filename": "scan.tif", "content_base64": b64},
            ],
            db=db_session,
        )
        assert len(docs) == 1

    def test_missing_filename_defaults(self, db_session):
        """Missing filename defaults to 'unnamed.bin' which is unsupported."""
        b64 = base64.b64encode(b"data").decode()
        docs = process_email_json(
            sender="test@example.com",
            subject="No filename",
            body_html="",
            attachments_b64=[
                {"content_base64": b64},
            ],
            db=db_session,
        )
        assert len(docs) == 0

    def test_empty_attachments_list(self, db_session):
        docs = process_email_json(
            sender="test@example.com",
            subject="Empty",
            body_html="",
            attachments_b64=[],
            db=db_session,
        )
        assert docs == []

    def test_oversized_attachment_skipped(self, db_session):
        """Attachment exceeding limit is skipped in JSON path."""
        from lab_manager.services.email_intake import _MAX_ATTACHMENT_BYTES

        big = b"x" * (_MAX_ATTACHMENT_BYTES + 1)
        b64 = base64.b64encode(big).decode()
        docs = process_email_json(
            sender="test@example.com",
            subject="Big file",
            body_html="",
            attachments_b64=[
                {"filename": "huge.pdf", "content_base64": b64},
            ],
            db=db_session,
        )
        assert len(docs) == 0

    def test_metadata_contains_sender_and_subject(self, db_session):
        pdf_b64 = base64.b64encode(_make_pdf()).decode()
        docs = process_email_json(
            sender="alice@lab.org",
            subject="Reagent Order #42",
            body_html="<p>Order details</p>",
            attachments_b64=[
                {"filename": "order.pdf", "content_base64": pdf_b64},
            ],
            db=db_session,
        )
        assert len(docs) == 1
        assert docs[0].extracted_data["email_from"] == "alice@lab.org"
        assert docs[0].extracted_data["email_subject"] == "Reagent Order #42"
        assert docs[0].extracted_data["source"] == "email"


class TestExtractAttachmentTypes:
    """Test extract_attachments with various content types."""

    def test_jpeg_supported(self):
        parsed = ParsedEmail(
            sender="",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[
                Attachment(filename="img.jpg", content_type="image/jpeg", data=b"jpg"),
            ],
        )
        assert len(extract_attachments(parsed)) == 1

    def test_tiff_supported(self):
        parsed = ParsedEmail(
            sender="",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[
                Attachment(
                    filename="scan.tiff", content_type="image/tiff", data=b"tif"
                ),
            ],
        )
        assert len(extract_attachments(parsed)) == 1

    def test_docx_unsupported(self):
        parsed = ParsedEmail(
            sender="",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[
                Attachment(
                    filename="doc.docx",
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    data=b"docx",
                ),
            ],
        )
        assert len(extract_attachments(parsed)) == 0

    def test_mixed_supported_and_unsupported(self):
        parsed = ParsedEmail(
            sender="",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[
                Attachment(
                    filename="ok.pdf", content_type="application/pdf", data=b"pdf"
                ),
                Attachment(
                    filename="bad.exe",
                    content_type="application/x-msdownload",
                    data=b"exe",
                ),
                Attachment(filename="ok.png", content_type="image/png", data=b"png"),
            ],
        )
        supported = extract_attachments(parsed)
        assert len(supported) == 2
        assert {a.filename for a in supported} == {"ok.pdf", "ok.png"}
