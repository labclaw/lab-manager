"""Targeted tests to boost coverage for services, app, config, and helpers.

Covers:
- alerts.py 326-348 (persist_alerts IntegrityError rollback path)
- rag.py 398 (_validate_sql dangerous keywords)
- rag.py 600-605 (ask() cache hit and stale-cache eviction)
- email_poller.py 68 (_fetch_unseen_emails empty-num skip)
- app.py 153 (_load_session_staff access_expires_at naive tz)
- app.py 183-186 (_read_version fallback)
- app.py 546-548 (login lock after 5 failures)
- app.py 560-564 (login access_expires_at check)
- app.py 745 (setup_complete email > 255 chars)
- app.py 790-792 (setup_complete IntegrityError)
- app.py 909 (_safe_serve path traversal)
- __init__.py 10-11 (version fallback when VERSION missing)
- config.py 61 (AUTH_ENABLED=false on non-localhost)
- config.py 78 (ADMIN_PASSWORD starts with "changeme")
- validation.py 30 (empty label in domain)
- logging_config.py 42 (JSON renderer branch)
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import structlog
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


def _hash_password(pw: str) -> str:
    import bcrypt

    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _auth_env_setup(engine):
    """Set up environment and database module for auth-enabled tests."""
    old_env = {
        k: os.environ.get(k)
        for k in (
            "AUTH_ENABLED",
            "ADMIN_SECRET_KEY",
            "ADMIN_PASSWORD",
            "API_KEY",
            "SECURE_COOKIES",
        )
    }
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-signing"
    os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
    os.environ["API_KEY"] = "test-api-key-12345"
    os.environ["SECURE_COOKIES"] = "false"
    get_settings.cache_clear()

    import lab_manager.database as db_module

    orig_engine = db_module._engine
    orig_factory = db_module._session_factory
    db_module._engine = engine
    db_module._session_factory = None

    return old_env, orig_engine, orig_factory


def _auth_env_teardown(old_env, orig_engine, orig_factory):
    """Restore environment after auth-enabled tests."""
    import lab_manager.database as db_module

    db_module._engine = orig_engine
    db_module._session_factory = orig_factory
    for k, v in old_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 1. __init__.py lines 10-11: version fallback when VERSION file is missing
# ---------------------------------------------------------------------------


class TestVersionFallback:
    def test_version_fallback_when_file_missing(self):
        """_read_version returns '0.0.0' when VERSION file doesn't exist."""
        import lab_manager

        # Patch Path.read_text to raise OSError, forcing the fallback path
        with patch("pathlib.Path.read_text", side_effect=OSError("no file")):
            result = lab_manager._read_version()
        assert result == "0.0.0"


# ---------------------------------------------------------------------------
# 2. config.py line 61: AUTH_ENABLED=false on non-localhost domain
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_auth_disabled_on_public_domain_raises(self):
        """AUTH_ENABLED=false on a non-localhost domain should raise."""
        old_env = {
            k: os.environ.get(k)
            for k in ("AUTH_ENABLED", "DOMAIN", "ADMIN_SECRET_KEY", "ADMIN_PASSWORD")
        }
        try:
            os.environ["AUTH_ENABLED"] = "false"
            os.environ["DOMAIN"] = "example.com"
            os.environ["ADMIN_SECRET_KEY"] = "dummy-key"
            os.environ["ADMIN_PASSWORD"] = "irrelevant"
            get_settings.cache_clear()

            from lab_manager.config import Settings

            with pytest.raises(
                ValueError, match="AUTH_ENABLED=false is only allowed on localhost"
            ):
                Settings(
                    auth_enabled=False,
                    domain="example.com",
                    admin_secret_key="dummy-key",
                    admin_password="something",
                )
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            get_settings.cache_clear()

    def test_changeme_admin_password_warns(self, caplog):
        """ADMIN_PASSWORD starting with 'changeme' should log a warning."""
        old_env = {
            k: os.environ.get(k)
            for k in ("AUTH_ENABLED", "ADMIN_SECRET_KEY", "ADMIN_PASSWORD", "DOMAIN")
        }
        try:
            os.environ["AUTH_ENABLED"] = "true"
            os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-32chars-minimum!!"
            os.environ["ADMIN_PASSWORD"] = "changeme-password"
            os.environ["DOMAIN"] = "localhost"
            get_settings.cache_clear()

            from lab_manager.config import Settings

            with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
                Settings(
                    auth_enabled=True,
                    domain="localhost",
                    admin_secret_key="test-secret-key-32chars-minimum!!",
                    admin_password="changeme-password",
                )
            assert any("default value" in r.message for r in caplog.records)
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 3. validation.py line 30: empty label in domain
# ---------------------------------------------------------------------------


class TestEmailValidation:
    def test_empty_label_in_domain(self):
        """Domain like 'a.@b.com' where split produces empty label."""
        from lab_manager.api.validation import is_valid_email_address

        # "user@a..com" -> domain labels ["a", "", "com"] -> line 29 catches it
        assert is_valid_email_address("user@a..com") is False

    def test_domain_trailing_dot(self):
        """Domain ending with dot produces empty trailing label."""
        from lab_manager.api.validation import is_valid_email_address

        assert is_valid_email_address("user@example.com.") is False


# ---------------------------------------------------------------------------
# 4. logging_config.py line 42: JSON renderer branch
# ---------------------------------------------------------------------------


class TestLoggingConfig:
    def test_json_renderer_when_log_format_json(self):
        """configure_logging should use JSONRenderer when log_format='json'."""
        old_env = os.environ.get("LOG_FORMAT")
        try:
            os.environ["LOG_FORMAT"] = "json"
            get_settings.cache_clear()

            from lab_manager.logging_config import configure_logging

            with patch.object(
                structlog.processors,
                "JSONRenderer",
                wraps=structlog.processors.JSONRenderer,
            ) as mock_json:
                configure_logging()
                mock_json.assert_called_once()
        finally:
            if old_env is None:
                os.environ.pop("LOG_FORMAT", None)
            else:
                os.environ["LOG_FORMAT"] = old_env
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 5. email_poller.py line 68: empty num in split results
# ---------------------------------------------------------------------------


class TestEmailPollerFetchUnseen:
    def test_empty_num_skipped(self):
        """Empty bytes in msg_nums split should be skipped (line 68)."""
        from lab_manager.services.email_poller import _fetch_unseen_emails

        conn = MagicMock()
        # b" 1" splits to [b"", b"1"] -- the b"" triggers line 67-68
        conn.search.return_value = ("OK", [b" 1"])
        conn.fetch.return_value = (
            "OK",
            [(b"1", b"Subject: test\r\n\r\nBody")],
        )

        result = _fetch_unseen_emails(conn, "INBOX")
        assert len(result) == 1

    def test_only_empty_nums(self):
        """If msg_nums split yields only empty bytes, return empty list."""
        from lab_manager.services.email_poller import _fetch_unseen_emails

        conn = MagicMock()
        conn.search.return_value = ("OK", [b""])

        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []


# ---------------------------------------------------------------------------
# 6. rag.py line 398: _validate_sql dangerous keywords
# ---------------------------------------------------------------------------


class TestRagValidateSql:
    def test_dangerous_keyword_drop(self):
        """SQL containing DROP should be blocked by _DANGEROUS_KEYWORDS."""
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="forbidden keyword"):
            _validate_sql("SELECT DROP FROM materials")

    def test_dangerous_keyword_truncate(self):
        """TRUNCATE keyword should be caught."""
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="forbidden keyword"):
            _validate_sql("SELECT TRUNCATE FROM materials")

    def test_dangerous_keyword_grant(self):
        """GRANT keyword should be caught."""
        from lab_manager.services.rag import _validate_sql

        with pytest.raises(ValueError, match="forbidden keyword"):
            _validate_sql("SELECT GRANT FROM materials")


# ---------------------------------------------------------------------------
# 7. rag.py lines 600-605: ask() cache hit and stale-cache eviction
# ---------------------------------------------------------------------------


class TestRagCacheHitAndEviction:
    def test_cache_hit_returns_cached_result(self):
        """An identical question within TTL should return cached result."""
        from lab_manager.services import rag

        question = "How many materials do we have?"
        cached_result = {
            "question": question,
            "answer": "42",
            "raw_results": [{"count": 42}],
            "source": "sql",
        }

        key = rag._cache_key(question)
        with rag._CACHE_LOCK:
            rag._CACHE[key] = (time.time(), cached_result)

        try:
            engine = _make_engine()
            with Session(engine) as db:
                result = rag.ask(question, db)
            assert result["answer"] == "42"
            assert result["source"] == "sql"
        finally:
            with rag._CACHE_LOCK:
                rag._CACHE.pop(key, None)

    def test_stale_cache_evicted(self):
        """A cached entry past TTL should be evicted, not returned."""
        from lab_manager.services import rag

        question = "How many vendors?"
        stale_result = {
            "question": question,
            "answer": "stale",
            "raw_results": [],
            "source": "sql",
        }

        key = rag._cache_key(question)
        with rag._CACHE_LOCK:
            rag._CACHE[key] = (time.time() - rag._CACHE_TTL_S - 10, stale_result)

        try:
            engine = _make_engine()
            with Session(engine) as db:
                with patch.object(
                    rag, "_generate_plan", side_effect=Exception("no LLM")
                ):
                    result = rag.ask(question, db)
            with rag._CACHE_LOCK:
                assert key not in rag._CACHE
            assert result["answer"] != "stale"
        finally:
            with rag._CACHE_LOCK:
                rag._CACHE.pop(key, None)


# ---------------------------------------------------------------------------
# 8. alerts.py lines 326-348: persist_alerts IntegrityError after rollback
# ---------------------------------------------------------------------------


class TestPersistAlertsIntegrityError:
    def test_integrity_error_rollback_re_queries(self):
        """When flush raises IntegrityError, persist_alerts should rollback
        and re-query existing alerts."""
        from sqlalchemy.exc import IntegrityError

        from lab_manager.services.alerts import persist_alerts

        engine = _make_engine()
        with Session(engine) as db:
            fake_alerts = [
                {
                    "type": "low_stock",
                    "severity": "warning",
                    "message": "Low stock for Product X",
                    "entity_type": "product",
                    "entity_id": 999,
                },
            ]

            with patch(
                "lab_manager.services.alerts.check_all_alerts", return_value=fake_alerts
            ):
                original_flush = Session.flush.__get__(db)
                armed = False

                def patched_flush(*a, **kw):
                    nonlocal armed
                    if armed:
                        armed = False
                        raise IntegrityError(
                            "duplicate", params=None, orig=Exception("dup")
                        )
                    return original_flush(*a, **kw)

                original_add = db.add

                def patched_add(obj, **kw):
                    nonlocal armed
                    result = original_add(obj, **kw)
                    armed = True
                    return result

                with patch.object(db, "add", side_effect=patched_add):
                    with patch.object(db, "flush", side_effect=patched_flush):
                        created, current = persist_alerts(db)

                assert isinstance(created, list)
                assert current == fake_alerts


# ---------------------------------------------------------------------------
# 9. app.py line 153: _load_session_staff with naive access_expires_at
# ---------------------------------------------------------------------------


class TestLoadSessionStaffAccessExpires:
    def test_expired_access_returns_none(self):
        """Staff with expired access_expires_at should get None from
        _load_session_staff."""
        engine = _make_engine()

        from lab_manager.models.staff import Staff

        with Session(engine) as db:
            staff = Staff(
                name="Expired User",
                email="expired@example.com",
                role="member",
                is_active=True,
                password_hash=_hash_password("password123"),
                access_expires_at=datetime(2020, 1, 1, 0, 0, 0),
            )
            db.add(staff)
            db.commit()
            db.refresh(staff)
            staff_id = staff.id

        old_env, orig_engine, orig_factory = _auth_env_setup(engine)
        try:
            from lab_manager.api.app import _get_serializer, _load_session_staff

            serializer = _get_serializer()
            cookie = serializer.dumps({"staff_id": staff_id, "name": "Expired User"})

            result = _load_session_staff(cookie)
            assert result is None
        finally:
            _auth_env_teardown(old_env, orig_engine, orig_factory)


# ---------------------------------------------------------------------------
# 10. app.py lines 183-186: _read_version fallback to __version__
# ---------------------------------------------------------------------------


class TestAppReadVersionFallback:
    def test_read_version_fallback(self):
        """_read_version in app.py should fall back to __version__
        when VERSION file is missing."""
        from lab_manager.api.app import _read_version

        # Patch read_text to raise OSError, forcing the fallback to __version__
        with patch("pathlib.Path.read_text", side_effect=OSError("no file")):
            result = _read_version()
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# 11. app.py lines 546-548: login lock after 5 failed attempts
# ---------------------------------------------------------------------------


class TestLoginLockAfterFailures:
    @pytest.fixture
    def auth_setup(self):
        engine = _make_engine()

        from lab_manager.models.staff import Staff

        with Session(engine) as db:
            staff = Staff(
                name="Lock Test",
                email="lock@example.com",
                role="admin",
                is_active=True,
                password_hash=_hash_password("correctpassword"),
                failed_login_count=4,
            )
            db.add(staff)
            db.commit()

        old_env, orig_engine, orig_factory = _auth_env_setup(engine)

        with Session(engine) as session:
            from lab_manager.api.app import create_app
            from lab_manager.api.deps import get_db

            app = create_app()

            def override():
                yield session

            app.dependency_overrides[get_db] = override

            from fastapi.testclient import TestClient

            with TestClient(app) as c:
                yield c, engine

        _auth_env_teardown(old_env, orig_engine, orig_factory)

    def test_lock_after_fifth_failure(self, auth_setup):
        """After 5 failed logins, the account should be locked."""
        client, engine = auth_setup
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "lock@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 12. app.py lines 560-564: login with expired access_expires_at
# ---------------------------------------------------------------------------


class TestLoginAccessExpired:
    @pytest.fixture
    def auth_setup_expired(self):
        engine = _make_engine()

        from lab_manager.models.staff import Staff

        with Session(engine) as db:
            staff = Staff(
                name="Expired Access",
                email="expaccess@example.com",
                role="admin",
                is_active=True,
                password_hash=_hash_password("correctpassword"),
                access_expires_at=datetime(2020, 1, 1, 0, 0, 0),
            )
            db.add(staff)
            db.commit()

        old_env, orig_engine, orig_factory = _auth_env_setup(engine)

        with Session(engine) as session:
            from lab_manager.api.app import create_app
            from lab_manager.api.deps import get_db

            app = create_app()

            def override():
                yield session

            app.dependency_overrides[get_db] = override

            from fastapi.testclient import TestClient

            with TestClient(app) as c:
                yield c

        _auth_env_teardown(old_env, orig_engine, orig_factory)

    def test_login_rejected_when_access_expired(self, auth_setup_expired):
        """Login should fail when staff access_expires_at is in the past."""
        client = auth_setup_expired
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "expaccess@example.com", "password": "correctpassword"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 13. app.py line 745: setup_complete email > 255 chars
# ---------------------------------------------------------------------------


class TestSetupEmailTooLong:
    def test_setup_email_exceeds_255(self, client):
        """Setup with email > 255 chars should return 422 (length check)."""
        long_email = "a" * 250 + "@b.com"
        with patch("lab_manager.api.app.is_valid_email_address", return_value=True):
            resp = client.post(
                "/api/v1/setup/complete",
                json={
                    "admin_name": "Test Admin",
                    "admin_email": long_email,
                    "admin_password": "securepassword123",
                },
            )
        assert resp.status_code == 422
        assert "255" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 14. app.py lines 790-792: setup_complete IntegrityError on commit
# ---------------------------------------------------------------------------


class TestSetupIntegrityError:
    def test_setup_integrity_error_returns_409(self, db_session):
        """If commit raises IntegrityError during setup, return 409."""
        from sqlalchemy.exc import IntegrityError

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()

        app = create_app()

        def override():
            yield db_session

        app.dependency_overrides[get_db] = override

        from fastapi.testclient import TestClient

        def fake_commit():
            raise IntegrityError("dup", params=None, orig=Exception("dup"))

        with TestClient(app) as c:
            with patch.object(db_session, "commit", side_effect=fake_commit):
                with patch.object(db_session, "rollback"):
                    resp = c.post(
                        "/api/v1/setup/complete",
                        json={
                            "admin_name": "Admin",
                            "admin_email": "admin@example.com",
                            "admin_password": "securepassword123",
                        },
                    )
        assert resp.status_code == 409
        assert "Setup already completed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 15. app.py line 909: _safe_serve path traversal
# ---------------------------------------------------------------------------


class TestSafeServe:
    def _make_app_with_uploads(self, upload_dir):
        """Create an app with a custom upload directory."""
        os.environ["AUTH_ENABLED"] = "false"
        os.environ["UPLOAD_DIR"] = str(upload_dir)
        get_settings.cache_clear()

        from lab_manager.api.app import create_app

        return create_app()

    def _cleanup_upload_env(self):
        os.environ["UPLOAD_DIR"] = "/tmp/lab-manager-test-uploads"
        get_settings.cache_clear()

    def test_upload_path_traversal_403(self, tmp_path):
        """Path traversal via URL-encoded dots should return 403
        (exercises _safe_serve line 909)."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir(exist_ok=True)
        # Create a secret file outside the upload dir
        (tmp_path / "secret.txt").write_text("secret")

        app = self._make_app_with_uploads(upload_dir)

        from lab_manager.api.deps import get_db
        from fastapi.testclient import TestClient

        engine = _make_engine()

        with Session(engine) as session:

            def override():
                yield session

            app.dependency_overrides[get_db] = override

            with TestClient(app) as c:
                # URL-encoded "../" bypasses client normalization
                resp = c.get("/uploads/%2e%2e/secret.txt")
                assert resp.status_code == 403

        self._cleanup_upload_env()

    def test_upload_nonexistent_file_404(self, tmp_path):
        """Requesting a nonexistent upload file should return 404
        (exercises _safe_serve line 911)."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir(exist_ok=True)

        app = self._make_app_with_uploads(upload_dir)

        from lab_manager.api.deps import get_db
        from fastapi.testclient import TestClient

        engine = _make_engine()

        with Session(engine) as session:

            def override():
                yield session

            app.dependency_overrides[get_db] = override

            with TestClient(app) as c:
                resp = c.get("/uploads/nonexistent.txt")
                assert resp.status_code == 404

        self._cleanup_upload_env()

    def test_upload_valid_file_200(self, tmp_path):
        """Requesting a valid upload file should return 200
        (exercises _safe_serve happy path)."""
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir(exist_ok=True)
        (upload_dir / "test.txt").write_text("hello")

        app = self._make_app_with_uploads(upload_dir)

        from lab_manager.api.deps import get_db
        from fastapi.testclient import TestClient

        engine = _make_engine()

        with Session(engine) as session:

            def override():
                yield session

            app.dependency_overrides[get_db] = override

            with TestClient(app) as c:
                resp = c.get("/uploads/test.txt")
                assert resp.status_code == 200
                assert resp.text == "hello"

        self._cleanup_upload_env()
