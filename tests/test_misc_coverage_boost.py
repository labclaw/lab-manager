"""Targeted tests for remaining uncovered lines in equipment, inventory, search, admin."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# 1. equipment.py lines 63, 90: invalid status in Create / Update validators
# ---------------------------------------------------------------------------


class TestEquipmentStatusValidators:
    def test_create_invalid_status_raises(self):
        """EquipmentCreate rejects an unknown status (line 63)."""
        from lab_manager.api.routes.equipment import EquipmentCreate

        with pytest.raises(ValueError, match="status must be one of"):
            EquipmentCreate(name="Centrifuge", status="bogus")

    def test_update_invalid_status_raises(self):
        """EquipmentUpdate rejects an unknown non-None status (line 90)."""
        from lab_manager.api.routes.equipment import EquipmentUpdate

        with pytest.raises(ValueError, match="status must be one of"):
            EquipmentUpdate(status="bogus")


# ---------------------------------------------------------------------------
# 2. inventory.py lines 81, 102: status validators
#    inventory.py lines 160, 162: _format_quantity branches
# ---------------------------------------------------------------------------


class TestInventoryStatusValidators:
    def test_create_invalid_status_raises(self):
        """InventoryItemCreate rejects an unknown status (line 81)."""
        from lab_manager.api.routes.inventory import InventoryItemCreate

        with pytest.raises(ValueError, match="status must be one of"):
            InventoryItemCreate(product_id=1, status="bogus")

    def test_update_invalid_status_raises(self):
        """InventoryItemUpdate rejects an unknown non-None status (line 102)."""
        from lab_manager.api.routes.inventory import InventoryItemUpdate

        with pytest.raises(ValueError, match="status must be one of"):
            InventoryItemUpdate(status="bogus")


class TestFormatQuantityBranches:
    def test_none_returns_zero_string(self):
        """_format_quantity(None) returns '0' (line 160)."""
        from lab_manager.api.routes.inventory import _format_quantity

        assert _format_quantity(None) == "0"

    def test_non_decimal_uses_str(self):
        """_format_quantity on a plain int (no .normalize) returns str() (line 162)."""
        from lab_manager.api.routes.inventory import _format_quantity

        assert _format_quantity(7) == "7"

    def test_decimal_strips_trailing_zeros(self):
        """_format_quantity strips trailing zeros from Decimal."""
        from lab_manager.api.routes.inventory import _format_quantity

        assert _format_quantity(Decimal("3.1000")) == "3.1"
        assert _format_quantity(Decimal("5.0000")) == "5"


# ---------------------------------------------------------------------------
# 3. search.py line 27: HTTPException for invalid index name
# ---------------------------------------------------------------------------


class TestSearchInvalidIndex:
    def test_invalid_index_returns_400(self, client):
        """GET /api/v1/search/?q=x&index=fake returns 400 (line 27)."""
        resp = client.get("/api/v1/search/", params={"q": "test", "index": "fake"})
        assert resp.status_code == 400
        assert "Invalid index" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 4. admin.py line 138: RuntimeError when admin_secret_key is empty
# ---------------------------------------------------------------------------


class TestAdminAuthMissingSecretKey:
    def test_missing_secret_key_raises(self):
        """_make_auth_backend raises RuntimeError when ADMIN_SECRET_KEY is empty (line 138)."""
        from lab_manager.config import Settings

        # Build a valid Settings first, then blank out admin_secret_key
        # to bypass the Settings-level validator but trigger the admin.py check.
        settings = Settings(
            auth_enabled=True,
            admin_secret_key="a" * 64,
            admin_password="good-password",
            api_key="different-api-key",
            domain="localhost",
        )
        # Force admin_secret_key to empty after construction
        object.__setattr__(settings, "admin_secret_key", "")

        with patch("lab_manager.config.get_settings", return_value=settings):
            from lab_manager.api.admin import _make_auth_backend

            with pytest.raises(RuntimeError, match="ADMIN_SECRET_KEY must be set"):
                _make_auth_backend()
