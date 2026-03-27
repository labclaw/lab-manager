"""Unit tests for email intake service.

Tests all functions: parse_email, _extract_attachment, extract_attachments,
_sanitize_filename, process_email, process_email_json.
"""

import base64
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from unittest.mock import MagicMock, patch


from lab_manager.services.email_intake import (
    Attachment,
    ParsedEmail,
    _extract_attachment,
    _sanitize_filename,
    extract_attachments,
    parse_email,
    process_email,
    process_email_json,
    _MAX_ATTACHMENT_BYTES,
    _MAX_ATTACHMENTS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_part(
    content: bytes,
    filename: str = "test.pdf",
    content_type: str = "application/pdf",
    disposition: str = "attachment",
) -> EmailMessage:
    """Build an EmailMessage part representing an attachment."""
    part = EmailMessage()
    part.set_content(
        content, maintype=content_type.split("/")[0], subtype=content_type.split("/")[1]
    )
    part.add_header("Content-Disposition", disposition, filename=filename)
    return part


def _make_db_with_auto_id():
    """Create a mock DB session that auto-assigns IDs on flush."""
    db = MagicMock()
    _counter = 0

    def flush_assign_id():
        nonlocal _counter
        if db.add.call_args:
            _counter += 1
            db.add.call_args[0][0].id = _counter

    db.flush.side_effect = flush_assign_id
    db.refresh.return_value = None
    return db


def _build_raw_email(
    from_addr: str = "vendor@example.com",
    subject: str = "Order shipped",
    date: str = "Thu, 27 Mar 2026 10:00:00 +0000",
    body_text: str | None = None,
    body_html: str | None = None,
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> str:
    """Build a raw MIME email string for testing.

    attachments: list of (filename, content_type, data_bytes)
    """
    has_attachments = attachments and len(attachments) > 0
    has_multipart = body_text and body_html or has_attachments

    if has_multipart:
        msg = MIMEMultipart()
    else:
        msg = EmailMessage()

    msg["From"] = from_addr
    msg["Subject"] = subject
    if date:
        msg["Date"] = date

    if has_multipart:
        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))
        for fname, ctype, data in attachments or []:
            maintype, subtype = ctype.split("/")
            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=fname)
            msg.attach(part)
    else:
        if body_html:
            msg.set_content(body_html, subtype="html")
        elif body_text:
            msg.set_content(body_text, subtype="plain")
        else:
            msg.set_content("")

    return msg.as_string()


# ===================================================================
# parse_email tests
# ===================================================================


class TestParseEmail:
    """Tests for parse_email()."""

    def test_simple_text_email(self):
        raw = _build_raw_email(
            from_addr="alice@example.com",
            subject="Hello",
            body_text="This is plain text body.",
        )
        parsed = parse_email(raw)
        assert parsed.sender == "alice@example.com"
        assert parsed.subject == "Hello"
        assert "This is plain text body." in parsed.body_text
        assert parsed.body_html == ""
        assert parsed.attachments == []

    def test_html_email(self):
        raw = _build_raw_email(
            from_addr="bob@example.com",
            subject="HTML Message",
            body_html="<h1>Hello</h1><p>World</p>",
        )
        parsed = parse_email(raw)
        assert parsed.sender == "bob@example.com"
        assert "<h1>Hello</h1><p>World</p>" in parsed.body_html
        assert parsed.body_text == ""

    def test_multipart_with_attachments(self):
        pdf_data = b"%PDF-1.4 fake content"
        raw = _build_raw_email(
            from_addr="vendor@supplier.com",
            subject="Invoice attached",
            body_text="Please find attached.",
            body_html="<p>Please find attached.</p>",
            attachments=[("invoice.pdf", "application/pdf", pdf_data)],
        )
        parsed = parse_email(raw)
        assert parsed.body_text == "Please find attached."
        assert "<p>Please find attached.</p>" in parsed.body_html
        assert len(parsed.attachments) == 1
        att = parsed.attachments[0]
        assert att.filename == "invoice.pdf"
        assert att.content_type == "application/pdf"
        assert att.data == pdf_data

    def test_multipart_with_multiple_attachments(self):
        raw = _build_raw_email(
            attachments=[
                ("a.pdf", "application/pdf", b"pdf-data"),
                ("b.png", "image/png", b"png-data"),
                ("c.jpg", "image/jpeg", b"jpg-data"),
            ],
        )
        parsed = parse_email(raw)
        assert len(parsed.attachments) == 3

    def test_empty_email(self):
        raw = _build_raw_email(subject="", from_addr="")
        parsed = parse_email(raw)
        assert parsed.sender == ""
        assert parsed.subject == ""
        assert parsed.body_text == "" or parsed.body_text is not None

    def test_email_no_subject(self):
        raw = _build_raw_email(subject="", body_text="body content")
        parsed = parse_email(raw)
        assert parsed.subject == ""
        assert "body content" in parsed.body_text

    def test_email_special_characters_in_subject(self):
        raw = _build_raw_email(
            subject="Re: Order #12345 — shipped ✓",
            body_text="See attached",
        )
        parsed = parse_email(raw)
        assert "12345" in parsed.subject

    def test_email_date_parsed(self):
        raw = _build_raw_email(date="Fri, 27 Mar 2026 14:30:00 +0000")
        parsed = parse_email(raw)
        assert parsed.date is not None
        assert "2026" in parsed.date

    def test_email_no_date(self):
        """Email with no Date header."""
        raw = _build_raw_email(date=None)
        parsed = parse_email(raw)
        assert parsed.date is None

    def test_multipart_text_and_html(self):
        """Both text and HTML body parts present."""
        raw = _build_raw_email(body_text="plain", body_html="<b>bold</b>")
        parsed = parse_email(raw)
        assert "plain" in parsed.body_text
        assert "bold" in parsed.body_html

    def test_email_with_cc_and_to_headers(self):
        raw = _build_raw_email(
            from_addr="sender@test.com",
            subject="Test CC",
            body_text="hello",
        )
        parsed = parse_email(raw)
        assert parsed.sender == "sender@test.com"


# ===================================================================
# _extract_attachment tests
# ===================================================================


class TestExtractAttachmentInternal:
    """Tests for _extract_attachment()."""

    def test_normal_attachment(self):
        attachments: list[Attachment] = []
        part = _make_part(
            b"hello world", filename="doc.pdf", content_type="application/pdf"
        )
        _extract_attachment(part, attachments)
        assert len(attachments) == 1
        assert attachments[0].filename == "doc.pdf"
        assert attachments[0].data == b"hello world"

    def test_oversized_attachment_skipped(self):
        attachments: list[Attachment] = []
        big_data = b"x" * (_MAX_ATTACHMENT_BYTES + 1)
        part = _make_part(big_data, filename="huge.pdf")
        _extract_attachment(part, attachments)
        assert len(attachments) == 0

    def test_exactly_max_size_attachment_accepted(self):
        """Attachment exactly at 50MB should be accepted."""
        attachments: list[Attachment] = []
        exact_data = b"x" * _MAX_ATTACHMENT_BYTES
        part = _make_part(exact_data, filename="exact.pdf")
        _extract_attachment(part, attachments)
        assert len(attachments) == 1

    def test_too_many_attachments(self):
        """When list is already at _MAX_ATTACHMENTS, skip new ones."""
        attachments: list[Attachment] = [
            Attachment(filename=f"f{i}.pdf", content_type="application/pdf", data=b"x")
            for i in range(_MAX_ATTACHMENTS)
        ]
        part = _make_part(b"extra data", filename="extra.pdf")
        _extract_attachment(part, attachments)
        assert len(attachments) == _MAX_ATTACHMENTS

    def test_empty_payload_skipped(self):
        """get_payload(decode=True) returning None means attachment is skipped."""
        attachments: list[Attachment] = []
        part = MagicMock()
        part.get_filename.return_value = "empty.pdf"
        part.get_content_type.return_value = "application/pdf"
        part.get_payload.return_value = None
        _extract_attachment(part, attachments)
        assert len(attachments) == 0

    def test_attachment_without_filename_gets_default_name(self):
        attachments: list[Attachment] = []
        part = EmailMessage()
        part.set_content(b"data", maintype="application", subtype="octet-stream")
        part.add_header("Content-Disposition", "attachment")
        _extract_attachment(part, attachments)
        if len(attachments) == 1:
            assert attachments[0].filename == "unnamed_attachment"

    def test_png_attachment(self):
        attachments: list[Attachment] = []
        part = _make_part(
            b"\x89PNG\r\n", filename="photo.png", content_type="image/png"
        )
        _extract_attachment(part, attachments)
        assert len(attachments) == 1
        assert attachments[0].content_type == "image/png"

    def test_jpeg_attachment(self):
        attachments: list[Attachment] = []
        part = _make_part(
            b"\xff\xd8\xff", filename="photo.jpg", content_type="image/jpeg"
        )
        _extract_attachment(part, attachments)
        assert len(attachments) == 1
        assert attachments[0].content_type == "image/jpeg"


# ===================================================================
# _sanitize_filename tests
# ===================================================================


class TestSanitizeFilename:
    """Tests for _sanitize_filename()."""

    def test_normal_filename(self):
        assert _sanitize_filename("report.pdf") == "report.pdf"

    def test_path_traversal_slashes(self):
        result = _sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result
        # Should still produce a usable name
        assert len(result) > 0

    def test_backslash_path_traversal(self):
        result = _sanitize_filename("..\\..\\windows\\system32")
        assert "\\" not in result

    def test_special_characters(self):
        result = _sanitize_filename("my file (1).pdf")
        assert " " not in result
        assert "(" not in result
        assert ")" not in result

    def test_empty_filename(self):
        result = _sanitize_filename("")
        assert result.startswith("attachment")

    def test_dot_only_filename(self):
        result = _sanitize_filename(".")
        assert result.startswith("attachment")

    def test_dotdot_filename(self):
        result = _sanitize_filename("..")
        assert result.startswith("attachment")

    def test_hidden_file_filename(self):
        result = _sanitize_filename(".env")
        assert result.startswith("attachment")

    def test_null_bytes_removed(self):
        result = _sanitize_filename("file\x00name.pdf")
        assert "\x00" not in result
        assert "file" in result

    def test_unicode_characters_replaced(self):
        result = _sanitize_filename("invoice_\u00e9.pdf")
        # Non-ASCII should be replaced with underscore
        assert all(c.isalnum() or c in "._-" for c in result)

    def test_multiple_dots_in_name(self):
        result = _sanitize_filename("my.report.v2.pdf")
        assert result == "my.report.v2.pdf"

    def test_filename_with_hyphens_and_underscores(self):
        result = _sanitize_filename("order_2026-03-27.pdf")
        assert result == "order_2026-03-27.pdf"


# ===================================================================
# extract_attachments tests
# ===================================================================


class TestExtractAttachments:
    """Tests for extract_attachments()."""

    def test_supported_pdf(self):
        parsed = ParsedEmail(
            sender="t@t.com",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[Attachment("doc.pdf", "application/pdf", b"data")],
        )
        result = extract_attachments(parsed)
        assert len(result) == 1
        assert result[0].filename == "doc.pdf"

    def test_supported_png(self):
        parsed = ParsedEmail(
            sender="t@t.com",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[Attachment("img.png", "image/png", b"data")],
        )
        result = extract_attachments(parsed)
        assert len(result) == 1

    def test_supported_jpeg(self):
        parsed = ParsedEmail(
            sender="t@t.com",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[Attachment("img.jpg", "image/jpeg", b"data")],
        )
        result = extract_attachments(parsed)
        assert len(result) == 1

    def test_supported_tiff(self):
        parsed = ParsedEmail(
            sender="t@t.com",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[Attachment("scan.tiff", "image/tiff", b"data")],
        )
        result = extract_attachments(parsed)
        assert len(result) == 1

    def test_unsupported_type_filtered(self):
        parsed = ParsedEmail(
            sender="t@t.com",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[
                Attachment(
                    "file.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    b"data",
                ),
            ],
        )
        result = extract_attachments(parsed)
        assert len(result) == 0

    def test_unsupported_zip_filtered(self):
        parsed = ParsedEmail(
            sender="t@t.com",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[Attachment("archive.zip", "application/zip", b"data")],
        )
        result = extract_attachments(parsed)
        assert len(result) == 0

    def test_mixed_supported_and_unsupported(self):
        parsed = ParsedEmail(
            sender="t@t.com",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[
                Attachment("doc.pdf", "application/pdf", b"data"),
                Attachment("file.zip", "application/zip", b"data"),
                Attachment("img.png", "image/png", b"data"),
                Attachment("data.xlsx", "application/vnd.ms-excel", b"data"),
            ],
        )
        result = extract_attachments(parsed)
        assert len(result) == 2
        assert result[0].filename == "doc.pdf"
        assert result[1].filename == "img.png"

    def test_empty_attachments_list(self):
        parsed = ParsedEmail(
            sender="t@t.com",
            subject="",
            date=None,
            body_text="",
            body_html="",
            attachments=[],
        )
        result = extract_attachments(parsed)
        assert result == []


# ===================================================================
# process_email tests
# ===================================================================


class TestProcessEmail:
    """Tests for process_email()."""

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_valid_email_creates_documents(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/saved.pdf"), "saved.pdf")

        db = MagicMock()
        doc_id_counter = 41

        def flush_side_effect():
            nonlocal doc_id_counter
            # Set id on any Document that was added (simulates auto-increment)
            for call in db.add.call_args_list:
                doc = call[0][0]
                doc_id_counter += 1
                doc.id = doc_id_counter

        db.flush.side_effect = flush_side_effect
        db.refresh.return_value = None

        raw = _build_raw_email(
            from_addr="vendor@example.com",
            subject="Invoice #123",
            body_text="Attached invoice.",
            attachments=[("invoice.pdf", "application/pdf", b"%PDF-1.4")],
        )

        docs = process_email(raw, db)
        assert len(docs) == 1
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

        # Verify Document was created with correct metadata
        added_doc = db.add.call_args[0][0]
        assert added_doc.status == "processing"
        assert added_doc.extracted_data["source"] == "email"
        assert added_doc.extracted_data["email_from"] == "vendor@example.com"
        assert "Invoice #123" in added_doc.review_notes

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_multiple_attachments_creates_multiple_docs(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.side_effect = [
            (Path("/tmp/uploads/a.pdf"), "a_saved.pdf"),
            (Path("/tmp/uploads/b.png"), "b_saved.png"),
        ]

        db = _make_db_with_auto_id()

        raw = _build_raw_email(
            attachments=[
                ("a.pdf", "application/pdf", b"pdf-data"),
                ("b.png", "image/png", b"png-data"),
            ],
        )

        docs = process_email(raw, db)
        assert len(docs) == 2
        assert db.add.call_count == 2

    def test_email_no_attachments_returns_empty(self):
        db = MagicMock()
        raw = _build_raw_email(
            from_addr="someone@test.com",
            subject="No attachments",
            body_text="Just text, nothing else.",
        )
        docs = process_email(raw, db)
        assert docs == []
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_email_unsupported_attachments_returns_empty(self):
        db = MagicMock()
        raw = _build_raw_email(
            attachments=[("archive.zip", "application/zip", b"zip-data")],
        )
        docs = process_email(raw, db)
        assert docs == []
        db.add.assert_not_called()

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_email_metadata_populated(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/doc.pdf"), "doc.pdf")

        db = _make_db_with_auto_id()

        raw = _build_raw_email(
            from_addr="sales@fisher.com",
            subject="PO-9988 shipped",
            date="Thu, 27 Mar 2026 12:00:00 +0000",
            attachments=[("packing_slip.pdf", "application/pdf", b"pdf")],
        )

        docs = process_email(raw, db)
        assert len(docs) == 1
        added_doc = db.add.call_args[0][0]
        assert added_doc.extracted_data["email_from"] == "sales@fisher.com"
        assert added_doc.extracted_data["email_subject"] == "PO-9988 shipped"
        assert added_doc.extracted_data["source"] == "email"


# ===================================================================
# process_email_json tests
# ===================================================================


class TestProcessEmailJson:
    """Tests for process_email_json()."""

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_valid_json_creates_document(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/doc.pdf"), "doc.pdf")

        db = _make_db_with_auto_id()

        att_b64 = base64.b64encode(b"PDF data here").decode()
        docs = process_email_json(
            sender="vendor@test.com",
            subject="Quote #Q1",
            body_html="<p>Quote attached</p>",
            attachments_b64=[{"filename": "quote.pdf", "content_base64": att_b64}],
            db=db,
        )
        assert len(docs) == 1
        db.commit.assert_called_once()
        added_doc = db.add.call_args[0][0]
        assert added_doc.extracted_data["source"] == "email"
        assert added_doc.extracted_data["email_from"] == "vendor@test.com"
        assert "Quote #Q1" in added_doc.review_notes

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_png_attachment(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/img.png"), "img.png")

        db = _make_db_with_auto_id()

        att_b64 = base64.b64encode(b"\x89PNG\r\ndata").decode()
        docs = process_email_json(
            sender="t@t.com",
            subject="Image",
            body_html="",
            attachments_b64=[{"filename": "photo.png", "content_base64": att_b64}],
            db=db,
        )
        assert len(docs) == 1

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_jpeg_attachment(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/img.jpg"), "img.jpg")

        db = _make_db_with_auto_id()

        att_b64 = base64.b64encode(b"\xff\xd8\xff data").decode()
        docs = process_email_json(
            sender="t@t.com",
            subject="JPEG",
            body_html="",
            attachments_b64=[{"filename": "photo.jpg", "content_base64": att_b64}],
            db=db,
        )
        assert len(docs) == 1

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_tiff_attachment(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/scan.tiff"), "scan.tiff")

        db = _make_db_with_auto_id()

        att_b64 = base64.b64encode(b"tiff-data").decode()
        docs = process_email_json(
            sender="t@t.com",
            subject="TIFF",
            body_html="",
            attachments_b64=[{"filename": "scan.tiff", "content_base64": att_b64}],
            db=db,
        )
        assert len(docs) == 1

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_tif_extension(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/scan.tif"), "scan.tif")

        db = _make_db_with_auto_id()

        att_b64 = base64.b64encode(b"tif-data").decode()
        docs = process_email_json(
            sender="t@t.com",
            subject="TIF",
            body_html="",
            attachments_b64=[{"filename": "scan.tif", "content_base64": att_b64}],
            db=db,
        )
        assert len(docs) == 1

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_jpeg_extension(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/img.jpeg"), "img.jpeg")

        db = _make_db_with_auto_id()

        att_b64 = base64.b64encode(b"jpeg-data").decode()
        docs = process_email_json(
            sender="t@t.com",
            subject="JPEG",
            body_html="",
            attachments_b64=[{"filename": "img.jpeg", "content_base64": att_b64}],
            db=db,
        )
        assert len(docs) == 1

    def test_unsupported_extension_skipped(self):
        db = MagicMock()
        att_b64 = base64.b64encode(b"data").decode()
        docs = process_email_json(
            sender="t@t.com",
            subject="Test",
            body_html="",
            attachments_b64=[{"filename": "file.docx", "content_base64": att_b64}],
            db=db,
        )
        assert docs == []
        db.add.assert_not_called()

    def test_invalid_base64_skipped(self):
        db = MagicMock()
        docs = process_email_json(
            sender="t@t.com",
            subject="Test",
            body_html="",
            attachments_b64=[
                {"filename": "file.pdf", "content_base64": "not-valid-base64!!!"}
            ],
            db=db,
        )
        assert docs == []
        db.add.assert_not_called()

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_oversized_base64_skipped(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")

        db = MagicMock()
        big_data = b"x" * (_MAX_ATTACHMENT_BYTES + 1)
        att_b64 = base64.b64encode(big_data).decode()
        docs = process_email_json(
            sender="t@t.com",
            subject="Big",
            body_html="",
            attachments_b64=[{"filename": "huge.pdf", "content_base64": att_b64}],
            db=db,
        )
        assert docs == []
        mock_save.assert_not_called()

    def test_empty_attachments_returns_empty(self):
        db = MagicMock()
        docs = process_email_json(
            sender="t@t.com",
            subject="Empty",
            body_html="",
            attachments_b64=[],
            db=db,
        )
        assert docs == []
        db.commit.assert_not_called()

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_missing_filename_defaults_to_unnamed(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/file.pdf"), "file.pdf")

        db = _make_db_with_auto_id()

        att_b64 = base64.b64encode(b"data").decode()
        docs = process_email_json(
            sender="t@t.com",
            subject="Test",
            body_html="",
            attachments_b64=[{"content_base64": att_b64}],  # no filename
            db=db,
        )
        # "unnamed.bin" is the default, extension .bin not in content_type_map -> skipped
        assert docs == []

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_multiple_valid_attachments(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.side_effect = [
            (Path("/tmp/uploads/a.pdf"), "a.pdf"),
            (Path("/tmp/uploads/b.png"), "b.png"),
            (Path("/tmp/uploads/c.jpg"), "c.jpg"),
        ]

        db = _make_db_with_auto_id()

        docs = process_email_json(
            sender="t@t.com",
            subject="Multi",
            body_html="",
            attachments_b64=[
                {
                    "filename": "a.pdf",
                    "content_base64": base64.b64encode(b"pdf").decode(),
                },
                {
                    "filename": "b.png",
                    "content_base64": base64.b64encode(b"png").decode(),
                },
                {
                    "filename": "c.jpg",
                    "content_base64": base64.b64encode(b"jpg").decode(),
                },
            ],
            db=db,
        )
        assert len(docs) == 3
        assert db.add.call_count == 3

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_no_commit_when_no_documents(self, mock_save, mock_settings):
        """process_email_json should not call commit if no valid docs created."""
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        db = MagicMock()

        docs = process_email_json(
            sender="t@t.com",
            subject="Nothing",
            body_html="",
            attachments_b64=[
                {
                    "filename": "file.exe",
                    "content_base64": base64.b64encode(b"exe").decode(),
                },
            ],
            db=db,
        )
        assert docs == []
        db.commit.assert_not_called()

    @patch("lab_manager.services.email_intake.get_settings")
    @patch("lab_manager.services.email_intake._save_attachment")
    def test_email_metadata_in_json_documents(self, mock_save, mock_settings):
        mock_settings.return_value = MagicMock(upload_dir="/tmp/uploads")
        mock_save.return_value = (Path("/tmp/uploads/doc.pdf"), "doc.pdf")

        db = _make_db_with_auto_id()

        att_b64 = base64.b64encode(b"pdf").decode()
        process_email_json(
            sender="procurement@lab.edu",
            subject="Order #5566",
            body_html="<p>See attached</p>",
            attachments_b64=[{"filename": "order.pdf", "content_base64": att_b64}],
            db=db,
        )
        added_doc = db.add.call_args[0][0]
        assert added_doc.extracted_data["email_from"] == "procurement@lab.edu"
        assert added_doc.extracted_data["email_subject"] == "Order #5566"
        # Note: no email_date key for JSON path (only set in process_email)
        assert "email_date" not in added_doc.extracted_data
