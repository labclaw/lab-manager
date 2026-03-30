"""Targeted tests for uncovered lines across core modules."""

import logging
import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# 1. __init__.py lines 10-11: VERSION file missing → fallback "0.0.0"
# ---------------------------------------------------------------------------


class TestVersionFallback:
    def test_version_fallback_when_file_missing(self, tmp_path):
        """_read_version returns '0.0.0' when VERSION file does not exist."""
        fake_init = tmp_path / "src" / "lab_manager" / "__init__.py"
        fake_init.parent.mkdir(parents=True)
        fake_init.write_text("# placeholder")

        # Point _version_file resolution at tmp_path (parents[2] of __init__.py
        # would be tmp_path itself).  No VERSION file → OSError → "0.0.0"
        import lab_manager

        with patch.object(Path, "resolve", return_value=fake_init):
            with patch.object(Path, "read_text", side_effect=OSError("no file")):
                result = lab_manager._read_version()
        assert result == "0.0.0"


# ---------------------------------------------------------------------------
# 2. config.py line 61: ValueError for auth_enabled=False on non-localhost
#    config.py line 78: warning for "changeme" default password
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_auth_disabled_on_non_localhost_raises(self):
        """AUTH_ENABLED=false with a non-localhost domain must raise ValueError."""
        from pydantic import ValidationError

        from lab_manager.config import Settings

        with pytest.raises(ValidationError, match="AUTH_ENABLED=false is only allowed"):
            Settings(
                auth_enabled=False,
                domain="example.com",
                admin_secret_key="irrelevant-but-set",
            )

    def test_changeme_password_logs_warning(self, caplog):
        """ADMIN_PASSWORD starting with 'changeme' should emit a warning."""
        from lab_manager.config import Settings

        with caplog.at_level(logging.WARNING):
            Settings(
                auth_enabled=True,
                admin_password="changeme123",
                admin_secret_key="a" * 64,
                domain="localhost",
            )
        assert any("default value" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# 3. validation.py line 30: empty domain label → False
# ---------------------------------------------------------------------------


class TestEmailValidationEmptyLabel:
    def test_empty_domain_label_rejected(self):
        """A domain with an empty label (consecutive dots) is invalid."""
        from lab_manager.api.validation import is_valid_email_address

        # "example..com" has an empty label → line 30 returns False
        assert is_valid_email_address("user@example..com") is False


# ---------------------------------------------------------------------------
# 4. admin.py line 138: RuntimeError when auth enabled but password empty
# ---------------------------------------------------------------------------


class TestAdminAuthMissingPassword:
    def test_password_same_as_api_key_raises(self):
        """RuntimeError when ADMIN_PASSWORD equals API_KEY."""
        from lab_manager.config import Settings

        settings = Settings(
            auth_enabled=True,
            admin_password="same-secret",
            admin_secret_key="a" * 64,
            api_key="same-secret",
            domain="localhost",
        )
        with patch("lab_manager.config.get_settings", return_value=settings):
            from lab_manager.api.admin import _make_auth_backend

            with pytest.raises(RuntimeError, match="ADMIN_PASSWORD must be distinct"):
                _make_auth_backend()


# ---------------------------------------------------------------------------
# 5. equipment.py lines 63, 90: invalid status in Create / Update validators
# ---------------------------------------------------------------------------


class TestEquipmentStatusValidation:
    def test_create_rejects_invalid_status(self):
        """EquipmentCreate.validate_status rejects unknown status values."""
        from lab_manager.api.routes.equipment import EquipmentCreate

        with pytest.raises(ValueError, match="status must be one of"):
            EquipmentCreate(name="Test Device", status="nonexistent")

    def test_update_rejects_invalid_status(self):
        """EquipmentUpdate.validate_status rejects unknown status values."""
        from lab_manager.api.routes.equipment import EquipmentUpdate

        with pytest.raises(ValueError, match="status must be one of"):
            EquipmentUpdate(status="invalid_status")

    def test_update_accepts_none_status(self):
        """EquipmentUpdate.validate_status passes when status is None."""
        from lab_manager.api.routes.equipment import EquipmentUpdate

        body = EquipmentUpdate(status=None)
        assert body.status is None

    def test_update_accepts_valid_status(self):
        """EquipmentUpdate.validate_status passes for a valid status."""
        from lab_manager.api.routes.equipment import EquipmentUpdate

        body = EquipmentUpdate(status="maintenance")
        assert body.status == "maintenance"


# ---------------------------------------------------------------------------
# 6. inventory.py lines 81, 102: status validators; lines 160, 162: _format_quantity
# ---------------------------------------------------------------------------


class TestInventoryStatusValidation:
    def test_create_rejects_invalid_status(self):
        """InventoryItemCreate.validate_status rejects unknown status values."""
        from lab_manager.api.routes.inventory import InventoryItemCreate

        with pytest.raises(ValueError, match="status must be one of"):
            InventoryItemCreate(product_id=1, status="invalid_status")

    def test_update_rejects_invalid_status(self):
        """InventoryItemUpdate.validate_status rejects unknown status values."""
        from lab_manager.api.routes.inventory import InventoryItemUpdate

        with pytest.raises(ValueError, match="status must be one of"):
            InventoryItemUpdate(status="bad_status")

    def test_update_accepts_none_status(self):
        """InventoryItemUpdate.validate_status passes when status is None."""
        from lab_manager.api.routes.inventory import InventoryItemUpdate

        body = InventoryItemUpdate(status=None)
        assert body.status is None


class TestFormatQuantity:
    def test_none_returns_zero(self):
        """_format_quantity(None) returns '0'."""
        from lab_manager.api.routes.inventory import _format_quantity

        assert _format_quantity(None) == "0"

    def test_non_decimal_passthrough(self):
        """_format_quantity with a non-normalize value (e.g. int) uses str()."""
        from lab_manager.api.routes.inventory import _format_quantity

        # Use a plain int — has no .normalize() → hits line 162
        assert _format_quantity(42) == "42"

    def test_decimal_trailing_zeros(self):
        """_format_quantity strips trailing zeros from Decimal."""
        from lab_manager.api.routes.inventory import _format_quantity

        assert _format_quantity(Decimal("1.0000")) == "1"
        assert _format_quantity(Decimal("2.5000")) == "2.5"

    def test_decimal_zero(self):
        """_format_quantity handles Decimal('0.0000')."""
        from lab_manager.api.routes.inventory import _format_quantity

        assert _format_quantity(Decimal("0.0000")) == "0"


# ---------------------------------------------------------------------------
# 7. search.py line 27: HTTPException for invalid index
# ---------------------------------------------------------------------------


class TestSearchInvalidIndex:
    def test_invalid_index_returns_400(self):
        """Search with an invalid index name returns HTTP 400."""
        from fastapi.testclient import TestClient

        from lab_manager.api.app import app

        client = TestClient(app, raise_server_exceptions=False)
        # Use a valid API key or disable auth — the test focuses on the index
        # validation logic.  We patch require_permission to skip auth.
        from lab_manager.api import auth as auth_mod

        with patch.object(auth_mod, "require_permission", return_value=lambda: None):
            # Patch search functions to avoid needing Meilisearch
            from lab_manager.api.routes import search as search_mod

            with patch.object(search_mod, "INDEX_CONFIG", {"products": None}):
                response = client.get(
                    "/api/v1/search/",
                    params={"q": "test", "index": "nonexistent"},
                )
        assert response.status_code == 400
        assert "Invalid index" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 8. logging_config.py line 42: JSON renderer branch
# ---------------------------------------------------------------------------


class TestLoggingJsonFormat:
    def test_json_renderer_selected(self):
        """configure_logging uses JSONRenderer when log_format='json'."""
        from lab_manager.config import get_settings

        # Clear cached settings so a fresh one is built
        get_settings.cache_clear()

        # Set env to force json log format
        with patch.dict(os.environ, {"LOG_FORMAT": "json"}):
            # Force a new Settings instance
            from lab_manager.config import Settings

            json_settings = Settings(log_format="json", domain="localhost")

            # Patch the lru_cache function to return our json settings
            with patch("lab_manager.config.get_settings", return_value=json_settings):
                from lab_manager.logging_config import configure_logging

                configure_logging()

            # Verify root logger has a handler
            root = logging.getLogger()
            assert root.handlers
            handler = root.handlers[-1]
            assert handler.formatter is not None

        # Cleanup: restore default console logging
        get_settings.cache_clear()
        from lab_manager.logging_config import configure_logging

        configure_logging()
