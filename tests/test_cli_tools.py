"""Tests for CLI tools in src/lab_manager/cli/.

Covers: set_staff_password, process_scans, index_meilisearch,
        pipeline_v2, populate_db, batch_ingest, extract_equipment.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# set_staff_password
# ---------------------------------------------------------------------------


class TestSetStaffPassword:
    """Tests for cli/set_staff_password.py."""

    def _import_main(self):
        from lab_manager.cli.set_staff_password import main

        return main

    def test_usage_no_args(self):
        main = self._import_main()
        with patch.object(sys, "argv", ["prog"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_usage_too_many_args(self):
        main = self._import_main()
        with patch.object(sys, "argv", ["prog", "a", "b", "c"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_short_password_rejected(self):
        main = self._import_main()
        with patch.object(sys, "argv", ["prog", "user@example.com", "short"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_staff_not_found(self):
        main = self._import_main()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        @contextmanager
        def fake_session():
            yield mock_db

        with patch.object(sys, "argv", ["prog", "missing@x.com", "longpassword"]):
            with patch("lab_manager.database.get_db_session", fake_session):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

    def test_password_set_success(self, capsys):
        main = self._import_main()
        staff = MagicMock()
        staff.name = "Alice"
        staff.email = "alice@lab.com"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff

        @contextmanager
        def fake_session():
            yield mock_db

        with patch.object(sys, "argv", ["prog", "alice@lab.com", "securepassword123"]):
            with patch("lab_manager.database.get_db_session", fake_session):
                main()

        mock_db.commit.assert_called_once()
        assert staff.password_hash is not None
        out = capsys.readouterr().out
        assert "Alice" in out

    def test_two_arg_mode_prompts_password(self):
        main = self._import_main()
        staff = MagicMock()
        staff.name = "Bob"
        staff.email = "bob@lab.com"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff

        @contextmanager
        def fake_session():
            yield mock_db

        with patch.object(sys, "argv", ["prog", "bob@lab.com"]):
            with patch("getpass.getpass", return_value="longpassword"):
                with patch("lab_manager.database.get_db_session", fake_session):
                    main()

        mock_db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# process_scans
# ---------------------------------------------------------------------------


class TestProcessScans:
    """Tests for cli/process_scans.py."""

    def _import_main(self):
        from lab_manager.cli.process_scans import main

        return main

    def test_directory_not_found(self, tmp_path):
        main = self._import_main()
        with patch.object(sys, "argv", ["prog", str(tmp_path / "nonexistent")]):
            with pytest.raises(SystemExit):
                main()

    def test_no_images(self, tmp_path, capsys):
        main = self._import_main()
        with patch.object(sys, "argv", ["prog", str(tmp_path)]):
            with patch("lab_manager.cli.process_scans.get_engine"):
                main()
        out = capsys.readouterr().out
        assert "Found 0 images" in out

    def test_processes_images(self, tmp_path, capsys):
        main = self._import_main()
        # Create fake image files
        (tmp_path / "scan1.jpg").touch()
        (tmp_path / "scan2.png").touch()
        (tmp_path / "readme.txt").touch()  # should be ignored

        mock_doc = MagicMock()
        mock_doc.status = "processed"

        mock_engine = MagicMock()

        with patch.object(sys, "argv", ["prog", str(tmp_path)]):
            with patch(
                "lab_manager.cli.process_scans.get_engine", return_value=mock_engine
            ):
                with patch(
                    "lab_manager.cli.process_scans.process_document",
                    return_value=mock_doc,
                ):
                    main()

        out = capsys.readouterr().out
        assert "Found 2 images" in out
        assert "processed" in out

    def test_handles_processing_error(self, tmp_path, capsys):
        main = self._import_main()
        (tmp_path / "bad.jpg").touch()

        mock_engine = MagicMock()

        with patch.object(sys, "argv", ["prog", str(tmp_path)]):
            with patch(
                "lab_manager.cli.process_scans.get_engine", return_value=mock_engine
            ):
                with patch(
                    "lab_manager.cli.process_scans.process_document",
                    side_effect=RuntimeError("VLM failed"),
                ):
                    main()

        out = capsys.readouterr().out
        assert "ERROR" in out

    def test_default_dir_from_env(self, tmp_path, capsys, monkeypatch):
        main = self._import_main()
        monkeypatch.setenv("LAB_DOCS_DIR", str(tmp_path))
        with patch.object(sys, "argv", ["prog"]):
            with patch("lab_manager.cli.process_scans.get_engine"):
                main()
        out = capsys.readouterr().out
        assert "Found 0 images" in out


# ---------------------------------------------------------------------------
# index_meilisearch
# ---------------------------------------------------------------------------


class TestIndexMeilisearch:
    """Tests for cli/index_meilisearch.py."""

    def _import_main(self):
        from lab_manager.cli.index_meilisearch import main

        return main

    def test_meilisearch_unreachable(self):
        main = self._import_main()
        mock_client = MagicMock()
        mock_client.get_version.side_effect = ConnectionError("unreachable")

        with patch(
            "lab_manager.services.search.get_search_client",
            return_value=mock_client,
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_successful_reindex(self):
        main = self._import_main()
        mock_client = MagicMock()
        mock_client.get_version.return_value = {"pkgVersion": "1.5.0"}

        mock_db = MagicMock()
        mock_factory = MagicMock(return_value=mock_db)

        mock_counts = {"products": 10, "documents": 20}

        with patch(
            "lab_manager.services.search.get_search_client",
            return_value=mock_client,
        ):
            with patch(
                "lab_manager.database.get_session_factory",
                return_value=mock_factory,
            ):
                with patch(
                    "lab_manager.services.search.sync_all",
                    return_value=mock_counts,
                ):
                    main()

        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# pipeline_v2
# ---------------------------------------------------------------------------


class TestPipelineV2:
    """Tests for cli/pipeline_v2.py."""

    def _import_module(self):
        from lab_manager.cli import pipeline_v2

        return pipeline_v2

    def test_process_one_image_not_found(self):
        mod = self._import_module()
        entry = {"file": "nonexistent.jpg", "fullText": "some text"}
        result = mod.process_one(entry, 1, 1, [])
        assert result["status"] == "image_not_found"

    def test_process_one_empty_ocr(self, tmp_path):
        mod = self._import_module()
        entry = {"file": "test.jpg", "fullText": "(No text detected)"}

        with patch.object(Path, "exists", return_value=True):
            result = mod.process_one(entry, 1, 1, [])
        assert result["status"] == "empty"

    def test_process_one_empty_text(self):
        mod = self._import_module()
        entry = {"file": "test.jpg", "fullText": ""}

        with patch.object(Path, "exists", return_value=True):
            result = mod.process_one(entry, 1, 1, [])
        assert result["status"] == "empty"

    def test_process_one_full_pipeline(self):
        mod = self._import_module()
        entry = {"file": "test.jpg", "fullText": "Sample OCR text", "model": "test"}

        mock_provider = MagicMock()
        mock_provider.name = "test_vlm"
        mock_provider.model_id = "test-1.0"

        mock_extractions = {"test_vlm": {"vendor_name": "Sigma"}}
        mock_merged = {
            "vendor_name": "Sigma",
            "_needs_human": False,
            "_model_count": 1,
            "_consensus": {},
        }
        mock_reviewed = dict(mock_merged)
        mock_reviewed["_review_round"] = {"corrections_applied": ["fix1"]}

        with patch.object(Path, "exists", return_value=True):
            with patch(
                "lab_manager.intake.consensus.extract_parallel",
                return_value=mock_extractions,
            ):
                with patch(
                    "lab_manager.intake.consensus.consensus_merge",
                    return_value=mock_merged,
                ):
                    with patch(
                        "lab_manager.intake.consensus.cross_model_review",
                        return_value=mock_reviewed,
                    ):
                        with patch(
                            "lab_manager.intake.validator.validate",
                            return_value=[],
                        ):
                            result = mod.process_one(
                                entry, 1, 1, [mock_provider], do_review=True
                            )

        assert result["status"] == "auto_resolved"
        assert result["document_status"] == "extracted"

    def test_process_one_needs_human(self):
        mod = self._import_module()
        entry = {"file": "test.jpg", "fullText": "Sample OCR text"}

        mock_provider = MagicMock()
        mock_provider.name = "test_vlm"
        mock_provider.model_id = "test-1.0"

        mock_merged = {
            "vendor_name": "Sigma",
            "_needs_human": True,
            "_model_count": 1,
            "_consensus": {},
        }

        with patch.object(Path, "exists", return_value=True):
            with patch(
                "lab_manager.intake.consensus.extract_parallel",
                return_value={"test_vlm": {"vendor_name": "Sigma"}},
            ):
                with patch(
                    "lab_manager.intake.consensus.consensus_merge",
                    return_value=mock_merged,
                ):
                    with patch(
                        "lab_manager.intake.validator.validate",
                        return_value=[],
                    ):
                        result = mod.process_one(
                            entry, 1, 1, [mock_provider], do_review=False
                        )

        assert result["status"] == "needs_human"
        assert result["needs_human"] is True
        assert result["document_status"] == "needs_review"

    def test_main_arg_parsing(self, tmp_path):
        mod = self._import_module()
        ocr_json = tmp_path / "ocr.json"
        ocr_json.write_text(json.dumps([{"file": "a.jpg", "fullText": "text"}]))

        mock_provider = MagicMock()
        mock_provider.name = "mock"
        mock_provider.model_id = "mock-1"

        out_dir = tmp_path / "pipeline_out"
        out_dir.mkdir()

        with patch.object(
            sys,
            "argv",
            ["prog", str(ocr_json), "--start", "0", "--end", "1", "--no-review"],
        ):
            with patch.object(mod, "OUTPUT_DIR", out_dir):
                with patch.object(
                    mod, "get_default_vlm_providers", return_value=[mock_provider]
                ):
                    with patch.object(
                        mod, "process_one", return_value={"status": "auto_resolved"}
                    ):
                        mod.main()

    def test_main_custom_vlms(self, tmp_path):
        mod = self._import_module()
        ocr_json = tmp_path / "ocr.json"
        ocr_json.write_text(json.dumps([]))

        mock_provider = MagicMock()
        mock_provider.name = "custom"
        mock_provider.model_id = "custom-1"

        out_dir = tmp_path / "pipeline_out"
        out_dir.mkdir()

        with patch.object(sys, "argv", ["prog", str(ocr_json), "--vlms", "custom_vlm"]):
            with patch.object(mod, "OUTPUT_DIR", out_dir):
                with patch.object(
                    mod, "get_vlm_providers", return_value=[mock_provider]
                ) as mock_get:
                    mod.main()
            mock_get.assert_called_once_with(["custom_vlm"])


# ---------------------------------------------------------------------------
# populate_db
# ---------------------------------------------------------------------------


class TestPopulateDb:
    """Tests for cli/populate_db.py."""

    def _import_module(self):
        from lab_manager.cli import populate_db

        return populate_db

    def test_populate_products_creates_new(self):
        mod = self._import_module()
        mock_db = MagicMock()
        # No existing products
        mock_db.query.return_value.all.return_value = []
        # One order_item row
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.all.return_value = [
            ("CAT001", "Widget A", "ea", 1),
        ]

        product_mock = MagicMock()
        product_mock.id = 42

        with patch("lab_manager.cli.populate_db.Product") as MockProduct:
            MockProduct.return_value = product_mock
            result = mod.populate_products(mock_db)

        assert "CAT001" in result
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_populate_products_skips_existing(self):
        mod = self._import_module()
        mock_db = MagicMock()
        existing_product = MagicMock()
        existing_product.catalog_number = "CAT001"
        existing_product.id = 10
        mock_db.query.return_value.all.return_value = [existing_product]
        mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.all.return_value = [
            ("CAT001", "Widget A", "ea", 1),
        ]

        result = mod.populate_products(mock_db)
        assert result["CAT001"] == 10
        mock_db.add.assert_not_called()

    def test_populate_staff_creates_from_orders(self):
        mod = self._import_module()
        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []  # no existing staff
        mock_db.query.return_value.filter.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("Alice",),
            ("bob",),
        ]
        mock_db.execute.return_value.all.return_value = []

        created = mod.populate_staff(mock_db)
        assert created == 2
        mock_db.commit.assert_called_once()

    def test_populate_staff_skips_existing(self):
        mod = self._import_module()
        mock_db = MagicMock()
        existing = MagicMock()
        existing.name = "Alice"
        mock_db.query.return_value.all.return_value = [existing]
        mock_db.query.return_value.filter.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("alice",),
        ]
        mock_db.execute.return_value.all.return_value = []

        created = mod.populate_staff(mock_db)
        assert created == 0

    def test_populate_locations_creates(self):
        mod = self._import_module()
        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []

        loc_id_counter = [0]

        def make_loc(**kwargs):
            loc_id_counter[0] += 1
            m = MagicMock()
            m.name = kwargs.get("name", "unknown")
            m.id = loc_id_counter[0]
            return m

        with patch("lab_manager.cli.populate_db.StorageLocation", side_effect=make_loc):
            result = mod.populate_locations(mock_db)

        assert len(result) == len(mod.LOCATIONS)
        mock_db.commit.assert_called_once()

    def test_populate_locations_skips_existing(self):
        mod = self._import_module()
        mock_db = MagicMock()
        existing = MagicMock()
        existing.name = "-80\u00b0C Freezer"
        existing.id = 99
        mock_db.query.return_value.all.return_value = [existing]

        with patch("lab_manager.cli.populate_db.StorageLocation") as MockLoc:
            MockLoc.return_value = MagicMock(id=1)
            result = mod.populate_locations(mock_db)

        assert result["-80\u00b0C Freezer"] == 99

    def test_populate_inventory(self):
        mod = self._import_module()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []  # no existing

        order_item = MagicMock()
        order_item.id = 1
        order_item.catalog_number = "CAT001"
        order_item.lot_number = "LOT1"
        order_item.quantity = 5
        order_item.unit = "ea"

        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            (order_item, "Alice"),
        ]

        catalog_map = {"CAT001": 42}
        loc_map = {"Room Temperature Shelf": 1}

        created = mod.populate_inventory(mock_db, catalog_map, loc_map)
        assert created == 1
        mock_db.add.assert_called_once()

    def test_update_order_items_product_id(self):
        mod = self._import_module()
        mock_db = MagicMock()

        item = MagicMock()
        item.catalog_number = "CAT001"
        item.product_id = None

        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [
            item,
        ]

        catalog_map = {"CAT001": 42}
        updated = mod.update_order_items_product_id(mock_db, catalog_map)
        assert updated == 1
        assert item.product_id == 42

    def test_main_runs_all_steps(self):
        mod = self._import_module()
        mock_engine = MagicMock()
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.execute.return_value.scalar.return_value = 0

        with patch("lab_manager.cli.populate_db.get_engine", return_value=mock_engine):
            with patch(
                "lab_manager.cli.populate_db.Session", return_value=mock_session
            ):
                with patch.object(mod, "populate_products", return_value={"CAT": 1}):
                    with patch.object(mod, "populate_staff", return_value=1):
                        with patch.object(
                            mod, "populate_locations", return_value={"Shelf": 1}
                        ):
                            with patch.object(
                                mod, "populate_inventory", return_value=1
                            ):
                                with patch.object(
                                    mod, "update_order_items_product_id", return_value=1
                                ):
                                    mod.main()


# ---------------------------------------------------------------------------
# batch_ingest
# ---------------------------------------------------------------------------


class TestBatchIngest:
    """Tests for cli/batch_ingest.py."""

    def _import_module(self):
        from lab_manager.cli import batch_ingest

        return batch_ingest

    def test_nvidia_call_success(self):
        mod = self._import_module()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "result text"}}]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("lab_manager.cli.batch_ingest.httpx.post", return_value=mock_resp):
            result = mod._nvidia_call({"model": "test"})
        assert result == "result text"

    def test_nvidia_call_rate_limit_retry(self):
        mod = self._import_module()
        error_resp = MagicMock()
        error_resp.status_code = 429
        error_resp.headers = {}

        ok_resp = MagicMock()
        ok_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        ok_resp.raise_for_status = MagicMock()

        import httpx

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "rate limited",
                    request=MagicMock(),
                    response=error_resp,
                )
            return ok_resp

        with patch("lab_manager.cli.batch_ingest.httpx.post", side_effect=mock_post):
            with patch("lab_manager.cli.batch_ingest.time.sleep"):
                result = mod._nvidia_call({"model": "test"})
        assert result == "ok"

    def test_nvidia_call_max_retries_exceeded(self):
        mod = self._import_module()
        import httpx

        error_resp = MagicMock()
        error_resp.status_code = 429
        error_resp.headers = {}

        def mock_post(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "rate limited", request=MagicMock(), response=error_resp
            )

        with patch("lab_manager.cli.batch_ingest.httpx.post", side_effect=mock_post):
            with patch("lab_manager.cli.batch_ingest.time.sleep"):
                with pytest.raises(RuntimeError, match="failed after"):
                    mod._nvidia_call({"model": "test"})

    def test_ocr_image_too_large(self, tmp_path):
        mod = self._import_module()
        big_file = tmp_path / "big.jpg"
        big_file.write_bytes(b"\x00" * (51 * 1024 * 1024))  # 51MB

        with pytest.raises(RuntimeError, match="Image too large"):
            mod.ocr_image(big_file)

    def test_ocr_image_success(self, tmp_path):
        mod = self._import_module()
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with patch.object(mod, "_nvidia_call", return_value="OCR text here"):
            result = mod.ocr_image(img)
        assert result == "OCR text here"

    def test_extract_text_success(self):
        mod = self._import_module()
        raw_json = json.dumps({"vendor_name": "Sigma", "document_type": "invoice"})

        with patch.object(mod, "_nvidia_call", return_value=raw_json):
            result = mod.extract_text("test-model", "some ocr text")
        assert result["vendor_name"] == "Sigma"

    def test_extract_text_markdown_wrapped(self):
        mod = self._import_module()
        raw = '```json\n{"vendor_name": "Bio-Rad"}\n```'

        with patch.object(mod, "_nvidia_call", return_value=raw):
            result = mod.extract_text("test-model", "text")
        assert result["vendor_name"] == "Bio-Rad"

    def test_extract_text_invalid_json(self):
        mod = self._import_module()
        with patch.object(mod, "_nvidia_call", return_value="not json at all"):
            result = mod.extract_text("test-model", "text")
        assert result is None

    def test_extract_text_exception(self):
        mod = self._import_module()
        with patch.object(mod, "_nvidia_call", side_effect=RuntimeError("fail")):
            result = mod.extract_text("test-model", "text")
        assert result is None

    def test_consensus_merge_all_none(self):
        mod = self._import_module()
        result = mod.consensus_merge({"a": None, "b": None})
        assert result["_needs_human"] is True
        assert result["_error"] == "all_models_failed"

    def test_consensus_merge_single_model(self):
        mod = self._import_module()
        result = mod.consensus_merge({"a": {"vendor": "X"}, "b": None})
        assert result["_consensus"] == "single_model"
        assert result["_needs_human"] is True

    def test_consensus_merge_unanimous(self):
        mod = self._import_module()
        result = mod.consensus_merge(
            {
                "glm5": {"vendor_name": "Sigma"},
                "qwen3.5": {"vendor_name": "Sigma"},
                "llama3.3": {"vendor_name": "Sigma"},
            }
        )
        assert result["vendor_name"] == "Sigma"
        assert result["_agreements"]["vendor_name"] == "unanimous"
        assert result["_needs_human"] is False

    def test_consensus_merge_majority(self):
        mod = self._import_module()
        result = mod.consensus_merge(
            {
                "glm5": {"vendor_name": "Sigma"},
                "qwen3.5": {"vendor_name": "Sigma"},
                "llama3.3": {"vendor_name": "Bio-Rad"},
            }
        )
        assert result["vendor_name"] == "Sigma"
        assert "majority" in result["_agreements"]["vendor_name"]

    def test_consensus_merge_no_consensus(self):
        mod = self._import_module()
        result = mod.consensus_merge(
            {
                "glm5": {"vendor_name": "A"},
                "qwen3.5": {"vendor_name": "B"},
                "llama3.3": {"vendor_name": "C"},
            }
        )
        assert result["_needs_human"] is True
        assert result["_agreements"]["vendor_name"] == "no_consensus"

    def test_validate_clean(self):
        mod = self._import_module()
        issues = mod.validate(
            {"vendor_name": "Sigma", "document_type": "invoice", "items": []}
        )
        assert issues == []

    def test_validate_vendor_too_long(self):
        mod = self._import_module()
        issues = mod.validate({"vendor_name": "X" * 101})
        assert any("too long" in i for i in issues)

    def test_validate_vendor_looks_like_address(self):
        mod = self._import_module()
        issues = mod.validate({"vendor_name": "123 Main Street"})
        assert any("address" in i for i in issues)

    def test_validate_invalid_doc_type(self):
        mod = self._import_module()
        issues = mod.validate({"document_type": "unknown_type"})
        assert any("invalid document_type" in i for i in issues)

    def test_validate_negative_quantity(self):
        mod = self._import_module()
        issues = mod.validate({"items": [{"quantity": -1}]})
        assert any("negative" in i for i in issues)

    def test_validate_vcat_lot(self):
        mod = self._import_module()
        issues = mod.validate({"items": [{"lot_number": "VCAT12345"}]})
        assert any("VCAT" in i for i in issues)

    def test_insert_document_success(self, tmp_path):
        mod = self._import_module()
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.id = 99
        mock_factory = MagicMock(return_value=mock_db)

        mock_status = MagicMock()
        mock_status.needs_review = "needs_review"
        mock_status.processed = "processed"

        with patch(
            "lab_manager.database.get_session_factory",
            return_value=mock_factory,
        ):
            with patch("lab_manager.models.document.Document") as MockDoc:
                MockDoc.return_value = mock_doc
                with patch("lab_manager.models.document.DocumentStatus", mock_status):
                    result = mod.insert_document(
                        tmp_path / "test.jpg",
                        "ocr text",
                        {
                            "vendor_name": "Sigma",
                            "_needs_human": False,
                            "_models": ["a"],
                        },
                        [],
                    )
        assert result == 99

    def test_insert_document_failure(self, tmp_path):
        mod = self._import_module()
        mock_db = MagicMock()
        mock_db.add.side_effect = RuntimeError("DB write failed")
        mock_factory = MagicMock(return_value=mock_db)

        mock_status = MagicMock()
        mock_status.needs_review = "needs_review"
        mock_status.processed = "processed"

        with patch(
            "lab_manager.database.get_session_factory",
            return_value=mock_factory,
        ):
            with patch("lab_manager.models.document.DocumentStatus", mock_status):
                result = mod.insert_document(
                    tmp_path / "test.jpg",
                    "text",
                    {"_models": [], "_needs_human": False},
                    [],
                )
        assert result is None
        mock_db.close.assert_called_once()

    def test_process_one_ocr_failure(self, tmp_path):
        mod = self._import_module()
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\x00" * 10)

        with patch.object(mod, "ocr_image", side_effect=RuntimeError("OCR failed")):
            result = mod.process_one(img)
        assert result["status"] == "ocr_failed"

    def test_process_one_ocr_empty(self, tmp_path):
        mod = self._import_module()
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\x00" * 10)

        with patch.object(mod, "ocr_image", return_value="short"):
            result = mod.process_one(img)
        assert result["status"] == "ocr_empty"

    def test_process_one_full_success(self, tmp_path):
        mod = self._import_module()
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\x00" * 10)

        merged = {
            "vendor_name": "Sigma",
            "_needs_human": False,
            "_models": ["a"],
            "_model_count": 1,
        }

        with patch.object(
            mod, "ocr_image", return_value="A long enough OCR text for testing"
        ):
            with patch.object(
                mod, "extract_text", return_value={"vendor_name": "Sigma"}
            ):
                with patch.object(mod, "consensus_merge", return_value=merged):
                    with patch.object(mod, "validate", return_value=[]):
                        with patch.object(mod, "insert_document", return_value=42):
                            with patch("lab_manager.cli.batch_ingest.time.sleep"):
                                result = mod.process_one(img)
        assert result["status"] == "ok"
        assert result["db_id"] == 42

    def test_main_no_api_key(self, monkeypatch):
        mod = self._import_module()
        monkeypatch.setattr(mod, "NVIDIA_KEY", "")
        with pytest.raises(SystemExit):
            mod.main()

    def test_main_no_images(self, tmp_path, monkeypatch):
        mod = self._import_module()
        monkeypatch.setattr(mod, "NVIDIA_KEY", "test-key")
        monkeypatch.setattr(mod, "DOCS_DIR", tmp_path)
        with pytest.raises(SystemExit):
            mod.main()


# ---------------------------------------------------------------------------
# extract_equipment
# ---------------------------------------------------------------------------


class TestExtractEquipment:
    """Tests for cli/extract_equipment.py."""

    def _import_module(self):
        from lab_manager.cli import extract_equipment

        return extract_equipment

    def test_extract_from_photo_success(self, tmp_path):
        mod = self._import_module()
        photo = tmp_path / "device.jpg"
        photo.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {"name": "Centrifuge", "manufacturer": "Eppendorf"}
        )
        mock_model.generate_content.return_value = mock_response

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        with patch.dict("sys.modules", {"google.generativeai": mock_genai}):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
                result = mod.extract_from_photo(photo)

        assert result["name"] == "Centrifuge"

    def test_extract_from_photo_no_api_key(self, tmp_path):
        mod = self._import_module()
        photo = tmp_path / "device.jpg"
        photo.write_bytes(b"\x00" * 10)

        mock_genai = MagicMock()

        with patch.dict("sys.modules", {"google.generativeai": mock_genai}):
            with patch.dict("os.environ", {}, clear=False):
                # Remove API keys if present
                import os

                env = os.environ.copy()
                env.pop("GEMINI_API_KEY", None)
                env.pop("GOOGLE_API_KEY", None)
                with patch.dict("os.environ", env, clear=True):
                    result = mod.extract_from_photo(photo)
        assert result is None

    def test_extract_from_photo_list_response(self, tmp_path):
        mod = self._import_module()
        photo = tmp_path / "device.jpg"
        photo.write_bytes(b"\x00" * 10)

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps([{"name": "Device A"}, {"name": "Device B"}])
        mock_model.generate_content.return_value = mock_response

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        with patch.dict("sys.modules", {"google.generativeai": mock_genai}):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
                result = mod.extract_from_photo(photo)
        assert result["name"] == "Device A"

    def test_extract_from_photo_invalid_json(self, tmp_path):
        mod = self._import_module()
        photo = tmp_path / "device.jpg"
        photo.write_bytes(b"\x00" * 10)

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "not json"
        mock_model.generate_content.return_value = mock_response

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        with patch.dict("sys.modules", {"google.generativeai": mock_genai}):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
                result = mod.extract_from_photo(photo)
        assert result is None

    def test_group_photos_by_device_single(self):
        mod = self._import_module()
        extractions = [
            {
                "photo": Path("a.jpg"),
                "data": {"name": "Centrifuge", "manufacturer": "Eppendorf"},
            },
        ]
        devices = mod.group_photos_by_device(extractions)
        assert len(devices) == 1
        assert len(devices[0]["photos"]) == 1

    def test_group_photos_by_device_merge(self):
        mod = self._import_module()
        extractions = [
            {
                "photo": Path("a.jpg"),
                "data": {
                    "name": "Centrifuge",
                    "manufacturer": "Eppendorf",
                    "confidence": 0.8,
                },
            },
            {
                "photo": Path("b.jpg"),
                "data": {
                    "name": "Centrifuge",
                    "manufacturer": "Eppendorf",
                    "serial_number": "SN123",
                    "confidence": 0.9,
                },
            },
        ]
        devices = mod.group_photos_by_device(extractions)
        assert len(devices) == 1
        assert len(devices[0]["photos"]) == 2
        # Higher confidence should contribute serial_number
        assert devices[0]["data"]["serial_number"] == "SN123"

    def test_group_photos_by_device_different(self):
        mod = self._import_module()
        extractions = [
            {
                "photo": Path("a.jpg"),
                "data": {"name": "Centrifuge", "manufacturer": "Eppendorf"},
            },
            {
                "photo": Path("b.jpg"),
                "data": {"name": "Microscope", "manufacturer": "Zeiss"},
            },
        ]
        devices = mod.group_photos_by_device(extractions)
        assert len(devices) == 2

    def test_group_photos_skips_none_data(self):
        mod = self._import_module()
        extractions = [
            {"photo": Path("a.jpg"), "data": None},
            {"photo": Path("b.jpg"), "data": {"name": "X", "manufacturer": "Y"}},
        ]
        devices = mod.group_photos_by_device(extractions)
        assert len(devices) == 1

    def test_insert_equipment_dry_run(self):
        mod = self._import_module()
        devices = [
            {
                "photos": [Path("a.jpg")],
                "data": {
                    "name": "Centrifuge",
                    "manufacturer": "Eppendorf",
                    "category": "centrifuge",
                },
            }
        ]
        # dry_run should not raise or touch DB
        mod.insert_equipment(devices, dry_run=True)

    def test_main_no_dir(self, tmp_path):
        mod = self._import_module()
        with patch.object(sys, "argv", ["prog", "--photo-dir", str(tmp_path / "nope")]):
            with pytest.raises(SystemExit):
                mod.main()

    def test_main_no_photos(self, tmp_path):
        mod = self._import_module()
        with patch.object(sys, "argv", ["prog", "--photo-dir", str(tmp_path)]):
            with pytest.raises(SystemExit):
                mod.main()

    def test_main_dry_run(self, tmp_path):
        mod = self._import_module()
        (tmp_path / "device1.jpg").touch()

        mock_data = {
            "name": "Test",
            "manufacturer": "ACME",
            "confidence": 0.9,
            "category": "other",
        }

        with patch.object(
            sys, "argv", ["prog", "--photo-dir", str(tmp_path), "--dry-run"]
        ):
            with patch.object(mod, "extract_from_photo", return_value=mock_data):
                with patch.object(mod, "insert_equipment") as mock_insert:
                    mod.main()
        mock_insert.assert_called_once()
        # Verify dry_run was passed
        assert mock_insert.call_args[1]["dry_run"] is True

    def test_main_with_output(self, tmp_path):
        mod = self._import_module()
        (tmp_path / "device1.jpg").touch()
        output_file = tmp_path / "out.json"

        mock_data = {
            "name": "Test",
            "manufacturer": "ACME",
            "confidence": 0.9,
            "category": "other",
        }

        with patch.object(
            sys,
            "argv",
            [
                "prog",
                "--photo-dir",
                str(tmp_path),
                "--dry-run",
                "--output",
                str(output_file),
            ],
        ):
            with patch.object(mod, "extract_from_photo", return_value=mock_data):
                with patch.object(mod, "insert_equipment"):
                    mod.main()

        saved = json.loads(output_file.read_text())
        assert len(saved) == 1
        assert saved[0]["data"]["name"] == "Test"

    def test_main_extraction_failure(self, tmp_path):
        mod = self._import_module()
        (tmp_path / "device1.jpg").touch()

        with patch.object(
            sys, "argv", ["prog", "--photo-dir", str(tmp_path), "--dry-run"]
        ):
            with patch.object(mod, "extract_from_photo", return_value=None):
                with patch.object(mod, "insert_equipment") as mock_insert:
                    mod.main()
        # insert_equipment still called, but with 0 devices (none extracted)
        mock_insert.assert_called_once()
        devices_arg = mock_insert.call_args[0][0]
        assert len(devices_arg) == 0
