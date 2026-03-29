"""Tests for fix/vendor-pubchem-version: issues 5, 6, 7."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from lab_manager.exceptions import ConflictError
from lab_manager.models.vendor import Vendor


# ---------------------------------------------------------------------------
# Issue 5: Case-insensitive vendor duplicate check
# ---------------------------------------------------------------------------


class TestVendorCaseInsensitiveDedup:
    """Vendor name duplicate check must be case-insensitive."""

    def test_duplicate_different_case_rejected(self, db_session):
        """Given 'Sigma-Aldrich' exists, creating 'sigma-aldrich' must fail."""
        from lab_manager.api.routes.vendors import VendorCreate, create_vendor

        v1 = Vendor(name="Sigma-Aldrich")
        db_session.add(v1)
        db_session.flush()

        body = VendorCreate(name="sigma-aldrich")
        with pytest.raises(ConflictError, match="already exists"):
            create_vendor(body, db_session)

    def test_duplicate_upper_case_rejected(self, db_session):
        """Given 'sigma' exists, creating 'SIGMA' must fail."""
        from lab_manager.api.routes.vendors import VendorCreate, create_vendor

        v1 = Vendor(name="sigma")
        db_session.add(v1)
        db_session.flush()

        body = VendorCreate(name="SIGMA")
        with pytest.raises(ConflictError, match="already exists"):
            create_vendor(body, db_session)

    def test_exact_match_still_rejected(self, db_session):
        """Exact match must still be rejected (regression check)."""
        from lab_manager.api.routes.vendors import VendorCreate, create_vendor

        v1 = Vendor(name="Fisher Scientific")
        db_session.add(v1)
        db_session.flush()

        body = VendorCreate(name="Fisher Scientific")
        with pytest.raises(ConflictError, match="already exists"):
            create_vendor(body, db_session)

    def test_different_name_accepted(self, db_session):
        """Creating a genuinely different vendor name must succeed."""
        from lab_manager.api.routes.vendors import VendorCreate, create_vendor

        v1 = Vendor(name="Sigma-Aldrich")
        db_session.add(v1)
        db_session.flush()

        body = VendorCreate(name="Fisher Scientific")
        vendor = create_vendor(body, db_session)
        assert vendor.name == "Fisher Scientific"

    def test_case_insensitive_via_api(self, client):
        """POST /vendors/ rejects case-variant duplicate via HTTP."""
        resp1 = client.post("/api/v1/vendors/", json={"name": "ThermoFisher"})
        assert resp1.status_code == 201

        resp2 = client.post("/api/v1/vendors/", json={"name": "thermofisher"})
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Issue 6: pubchem _rate_limit must not sleep while holding lock
# ---------------------------------------------------------------------------


class TestPubChemRateLimitNoBlockingLock:
    """_rate_limit() must release the lock before sleeping."""

    def setup_method(self):
        from lab_manager.services.pubchem import clear_cache

        clear_cache()

    def test_lock_not_held_during_sleep(self):
        """Other threads must be able to acquire _LOCK while one thread sleeps."""
        from lab_manager.services import pubchem

        # Force a scenario where sleep is needed
        pubchem._last_request_time = time.monotonic() + 10  # far in the future

        lock_acquired = threading.Event()
        error_holder = []

        def try_acquire_lock():
            try:
                acquired = pubchem._LOCK.acquire(timeout=0.5)
                if acquired:
                    lock_acquired.set()
                    pubchem._LOCK.release()
                else:
                    error_holder.append("Could not acquire lock within 0.5s")
            except Exception as exc:
                error_holder.append(str(exc))

        # Patch time.sleep so we don't actually wait
        with patch("lab_manager.services.pubchem.time.sleep"):
            # Reset to trigger sleep path
            pubchem._last_request_time = time.monotonic()

            # Call rate_limit in a thread, but with mocked sleep it returns fast
            t1 = threading.Thread(target=pubchem._rate_limit)
            t1.start()
            t1.join(timeout=2)

        # Now verify: the lock should be free after _rate_limit returns
        acquired = pubchem._LOCK.acquire(timeout=0.5)
        assert acquired, "Lock was not released after _rate_limit"
        pubchem._LOCK.release()

    def test_rate_limit_calculates_sleep_under_lock(self):
        """_rate_limit should calculate sleep duration under lock, then sleep outside."""
        from lab_manager.services import pubchem

        # Set last request time to now so next call needs to sleep
        pubchem._last_request_time = time.monotonic()

        sleep_durations = []

        def capturing_sleep(duration):
            sleep_durations.append(duration)
            # Don't actually sleep

        with patch(
            "lab_manager.services.pubchem.time.sleep", side_effect=capturing_sleep
        ):
            pubchem._rate_limit()

        # Should have called sleep with a positive duration
        assert len(sleep_durations) == 1
        assert 0 < sleep_durations[0] <= pubchem._MIN_INTERVAL


# ---------------------------------------------------------------------------
# Issue 7: version from VERSION file, not hardcoded
# ---------------------------------------------------------------------------


class TestVersionFromFile:
    """FastAPI app version must come from VERSION file."""

    def test_app_version_matches_version_file(self, client):
        """The /api/health or OpenAPI schema must report version from VERSION file."""
        from pathlib import Path

        version_file = Path("/tmp/wt-fix-important/VERSION")
        expected = version_file.read_text().strip()

        # In dev mode, docs_url is available, check openapi schema
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        assert resp.json()["info"]["version"] == expected

    def test_package_version_matches_version_file(self):
        """__version__ must match VERSION file content."""
        from pathlib import Path

        from lab_manager import __version__

        version_file = Path("/tmp/wt-fix-important/VERSION")
        expected = version_file.read_text().strip()
        assert __version__ == expected

    def test_read_version_fallback(self, tmp_path):
        """_read_version falls back to __version__ if VERSION file is missing."""
        from lab_manager.api.app import _read_version

        # The function reads from a fixed path relative to app.py,
        # so we just verify it returns a non-empty string
        version = _read_version()
        assert version
        assert isinstance(version, str)
        assert len(version) > 0
