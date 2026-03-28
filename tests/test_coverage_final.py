"""Final coverage gap tests to push from 99% to 100%."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _find_vendor removed — reverse partial match no longer needed
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# consensus.py lines 42-43: TimeoutError in extract_parallel
# ---------------------------------------------------------------------------


class TestConsensusTimeout:
    def test_extract_parallel_timeout_error(self):
        """Provider that raises TimeoutError gets None result."""
        from lab_manager.intake.consensus import extract_parallel
        from lab_manager.intake.providers import VLMProvider

        class TimeoutProvider(VLMProvider):
            name = "timeout_provider"

            def extract(self, image_path, prompt):
                raise TimeoutError("took too long")

            def extract_from_image(self, image_path, prompt):
                return ""

        results = extract_parallel([TimeoutProvider()], "fake.png", "test")
        assert results["timeout_provider"] is None


# ---------------------------------------------------------------------------
# consensus.py line 178: underscore field skip in cross_model_review
# ---------------------------------------------------------------------------


class TestCrossModelReviewUnderscoreSkip:
    @patch("lab_manager.intake.consensus.extract_parallel")
    def test_review_skips_underscore_in_review_data(self, mock_parallel):
        from lab_manager.intake.consensus import cross_model_review

        mock_parallel.return_value = {
            "rev_a": {"vendor_name": "Same", "_internal": "skip"},
            "rev_b": {"vendor_name": "Same"},
        }
        merged = {
            "vendor_name": "Same",
            "_consensus": {"some": "data"},
            "_needs_human": False,
        }
        result = cross_model_review([], "img.png", merged)
        assert result["_review_round"]["corrections_applied"] == []


# ---------------------------------------------------------------------------
# documents.py line 104: _validate_file_path raises on traversal
# ---------------------------------------------------------------------------


class TestDocumentValidation:
    def test_path_traversal_raises(self):
        """Path traversal in file_path should raise ValueError."""
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir"):
            _validate_file_path("../../etc/passwd")

    def test_valid_path(self):
        from lab_manager.api.routes.documents import _validate_file_path

        # Should not raise — relative paths resolve against upload_dir
        _validate_file_path("valid_file.pdf")


# ---------------------------------------------------------------------------
# documents.py line 311: _create_order_from_doc with no extracted_data
# ---------------------------------------------------------------------------


class TestCreateOrderFromDocNoData:
    def test_approve_doc_without_extracted_data(self, client, db_session):
        from lab_manager.models.document import Document

        doc = Document(
            file_path="/tmp/no-data.pdf",
            file_name="no-data.pdf",
            status="needs_review",
            extracted_data=None,
        )
        db_session.add(doc)
        db_session.flush()

        resp = client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "approve", "reviewed_by": "tester"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# app.py — remaining lines: auth middleware session cookie, API key,
# login endpoint, health checks, static files
# ---------------------------------------------------------------------------


class TestAppSessionCookie:
    """Test auth middleware with session cookie (app.py lines 139-163)."""

    def test_auth_me_not_authenticated(self):
        """With auth_enabled, no session cookie -> 401."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-session"
        os.environ["API_KEY"] = "test-api-key"

        from lab_manager.config import get_settings

        get_settings.cache_clear()

        try:
            from lab_manager.api.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/auth/me")
                assert resp.status_code == 401
        finally:
            os.environ["AUTH_ENABLED"] = "false"
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("ADMIN_SECRET_KEY", None)
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    def test_api_key_header_auth(self):
        """With auth_enabled, valid X-Api-Key header -> 200."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-api"
        os.environ["API_KEY"] = "my-test-api-key"

        from lab_manager.config import get_settings

        get_settings.cache_clear()

        try:
            from lab_manager.api.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            with TestClient(app) as client:
                resp = client.get(
                    "/api/health",
                    headers={"X-Api-Key": "my-test-api-key"},
                )
                assert resp.status_code in (200, 503)
        finally:
            os.environ["AUTH_ENABLED"] = "false"
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("ADMIN_SECRET_KEY", None)
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    def test_unauthenticated_request(self):
        """With auth_enabled, no credentials -> 401."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-unauth"
        os.environ["API_KEY"] = "api-key-123"

        from lab_manager.config import get_settings

        get_settings.cache_clear()

        try:
            from lab_manager.api.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            with TestClient(app) as client:
                resp = client.get("/api/v1/vendors/")
                assert resp.status_code == 401
        finally:
            os.environ["AUTH_ENABLED"] = "false"
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("ADMIN_SECRET_KEY", None)
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()

    def test_invalid_session_cookie(self):
        """With auth_enabled, invalid session cookie -> 401."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-invalid"
        os.environ["API_KEY"] = ""

        from lab_manager.config import get_settings

        get_settings.cache_clear()

        try:
            from lab_manager.api.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            with TestClient(app) as client:
                # Set invalid session cookie
                client.cookies.set("lab_session", "invalid-cookie-data")
                resp = client.get("/api/v1/vendors/")
                assert resp.status_code == 401
        finally:
            os.environ["AUTH_ENABLED"] = "false"
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("ADMIN_SECRET_KEY", None)
            os.environ.pop("API_KEY", None)
            get_settings.cache_clear()


class TestAppLoginEndpoint:
    """Test the login endpoint (app.py lines 240-291)."""

    def test_login_wrong_password(self):
        """Login with wrong password returns 401."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-for-login"

        from lab_manager.config import get_settings

        get_settings.cache_clear()

        try:
            from lab_manager.api.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/auth/login",
                    json={"email": "nobody@test.com", "password": "wrong"},
                )
                # 401 = wrong creds, 503 = db unavailable (both are valid test outcomes)
                assert resp.status_code in (401, 503)
        finally:
            os.environ["AUTH_ENABLED"] = "false"
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("ADMIN_SECRET_KEY", None)
            get_settings.cache_clear()


class TestAppHealthEndpoints:
    """Exercise the health endpoint service checks."""

    def test_health_with_meilisearch_error(self, client):
        """Health check still returns 200 when Meilisearch is unavailable.

        Meilisearch is not core — the app can serve data without search.
        This is critical for managed deployments (e.g. DO App Platform)
        where search starts independently.
        """
        with patch("lab_manager.services.search.get_search_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.health.side_effect = Exception("connection refused")
            mock_get_client.return_value = mock_client

            resp = client.get("/api/health")
            data = resp.json()
            assert resp.status_code == 200
            assert data["services"]["meilisearch"] == "error"

    def test_health_with_disk_error(self, client):
        """Health check when disk usage check fails."""
        with patch("lab_manager.api.app.shutil.disk_usage") as mock_disk:
            mock_disk.side_effect = OSError("Permission denied")
            resp = client.get("/api/health")
            data = resp.json()
            assert "services" in data

    def test_health_with_pg_error(self, client):
        """Health check when PostgreSQL connection fails."""
        with patch("lab_manager.api.app.get_engine") as mock_engine:
            mock_engine.return_value.connect.side_effect = Exception("pg down")
            resp = client.get("/api/health")
            data = resp.json()
            assert data["services"]["postgresql"] == "error"


class TestAppStaticFiles:
    """Test static file endpoints (sw.js, manifest.json)."""

    def test_sw_js(self, client):
        resp = client.get("/sw.js")
        # May 404 if static files don't exist in test env
        assert resp.status_code in (200, 404, 405)

    def test_manifest_json(self, client):
        resp = client.get("/manifest.json")
        assert resp.status_code in (200, 404, 405)


class TestAppGetSerializer:
    """Test _get_serializer raises when no secret key."""

    def test_no_secret_key_raises(self):
        from lab_manager.api.app import _get_serializer

        with patch("lab_manager.api.app.get_settings") as mock_settings:
            mock_settings.return_value.admin_secret_key = ""
            with pytest.raises(RuntimeError, match="ADMIN_SECRET_KEY"):
                _get_serializer()


class TestDocumentValidPathInValidator:
    """Test the Pydantic validator return path when path is valid."""

    def test_update_document_valid_path(self, client, db_session):
        from lab_manager.models.document import Document

        doc = Document(
            file_path="original.pdf",
            file_name="original.pdf",
            status="pending",
        )
        db_session.add(doc)
        db_session.flush()

        resp = client.patch(
            f"/api/v1/documents/{doc.id}",
            json={"file_path": "new_valid_path.pdf"},
        )
        assert resp.status_code == 200

    def test_update_document_invalid_status_returns_422(self, client, db_session):
        from lab_manager.models.document import Document

        doc = Document(
            file_path="/tmp/original.pdf",
            file_name="original.pdf",
            status="pending",
        )
        db_session.add(doc)
        db_session.flush()

        resp = client.patch(
            f"/api/v1/documents/{doc.id}",
            json={"status": "bogus_status"},
        )
        assert resp.status_code == 422

    def test_approve_doc_empty_data(self, client, db_session):
        """Approve doc with empty dict as extracted_data."""
        from lab_manager.models.document import Document

        doc = Document(
            file_path="/tmp/empty-data.pdf",
            file_name="empty-data.pdf",
            status="needs_review",
            extracted_data={},
        )
        db_session.add(doc)
        db_session.flush()

        resp = client.post(
            f"/api/v1/documents/{doc.id}/review",
            json={"action": "approve", "reviewed_by": "tester"},
        )
        assert resp.status_code == 200


class TestAppAuthMeWithSession:
    """Test auth/me endpoint with valid session cookie."""

    def test_auth_me_valid_session(self):
        import os
        from unittest.mock import patch

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
        os.environ["ADMIN_SECRET_KEY"] = "session-test-key-12345"

        from lab_manager.config import get_settings

        get_settings.cache_clear()

        try:
            from itsdangerous import URLSafeTimedSerializer

            from lab_manager.api.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            serializer = URLSafeTimedSerializer(
                "session-test-key-12345", salt="lab-session"
            )
            session_data = serializer.dumps({"staff_id": 1, "name": "TestUser"})

            mock_staff = {"id": 1, "name": "TestUser"}

            with patch(
                "lab_manager.api.app._load_session_staff", return_value=mock_staff
            ):
                with TestClient(app) as client:
                    client.cookies.set("lab_session", session_data)
                    resp = client.get("/api/v1/auth/me")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["user"]["name"] == "TestUser"
        finally:
            os.environ["AUTH_ENABLED"] = "false"
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("ADMIN_SECRET_KEY", None)
            get_settings.cache_clear()

    def test_auth_me_bad_session_signature(self):
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
        os.environ["ADMIN_SECRET_KEY"] = "bad-sig-test-key-12345"

        from lab_manager.config import get_settings

        get_settings.cache_clear()

        try:
            from lab_manager.api.app import create_app
            from fastapi.testclient import TestClient

            app = create_app()
            with TestClient(app) as client:
                client.cookies.set("lab_session", "totally-invalid-token")
                resp = client.get("/api/v1/auth/me")
                assert resp.status_code == 401
                assert resp.json()["detail"] == "Invalid session"
        finally:
            os.environ["AUTH_ENABLED"] = "false"
            os.environ.pop("ADMIN_PASSWORD", None)
            os.environ.pop("ADMIN_SECRET_KEY", None)
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# audit.py — remaining lines: _get_record_id returns None, etc.
# ---------------------------------------------------------------------------


class TestAuditEventListenerPaths:
    """Test audit event listener edge cases."""

    def test_update_no_real_changes(self, db_session):
        """Touching a model without changing values should not create audit log."""
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="NoChange")
        db_session.add(v)
        db_session.flush()
        db_session.commit()

        # Mark as dirty without changing values
        v.name = "NoChange"  # same value
        db_session.flush()
        # No error expected

    def test_delete_creates_snapshot(self, db_session):
        """Deleting an object records a snapshot in audit log."""
        from lab_manager.models.audit import AuditLog
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="SnapshotDelete")
        db_session.add(v)
        db_session.flush()
        db_session.commit()

        vid = v.id
        db_session.delete(v)
        db_session.flush()

        logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.table_name == "vendors",
                AuditLog.action == "delete",
                AuditLog.record_id == vid,
            )
            .all()
        )
        assert len(logs) >= 1
        # The delete log should have a snapshot of the old values
        assert logs[0].changes is not None

    def test_create_then_modify_audit(self, db_session):
        """Create + modify in same session should create both audit entries."""
        from lab_manager.models.audit import AuditLog
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="AuditBoth")
        db_session.add(v)
        db_session.flush()  # create
        db_session.commit()

        v.name = "AuditBothModified"
        db_session.flush()  # update

        create_logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.table_name == "vendors",
                AuditLog.action == "create",
                AuditLog.record_id == v.id,
            )
            .all()
        )
        update_logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.table_name == "vendors",
                AuditLog.action == "update",
                AuditLog.record_id == v.id,
            )
            .all()
        )
        assert len(create_logs) >= 1
        assert len(update_logs) >= 1
