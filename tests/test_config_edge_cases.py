"""Tests for config edge cases: validation, normalization, auth guards."""

import pytest

from lab_manager.config import Settings, get_settings


def _make_settings(**overrides):
    """Create a Settings instance with safe defaults for testing."""
    defaults = {
        "database_url": "sqlite://",
        "admin_secret_key": "test-key",
        "_env_file": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ---------------------------------------------------------------------------
# Database URL normalization
# ---------------------------------------------------------------------------


class TestDatabaseUrlNormalization:
    """Edge cases for postgresql:// -> postgresql+psycopg:// rewrite."""

    def test_readonly_url_also_normalized(self):
        """database_readonly_url gets the same prefix treatment."""
        s = _make_settings(
            database_readonly_url="postgresql://ro:pw@host/db",
        )
        assert s.database_readonly_url == "postgresql+psycopg://ro:pw@host/db"

    def test_readonly_url_empty_stays_empty(self):
        """Empty database_readonly_url is not touched."""
        s = _make_settings(database_readonly_url="")
        assert s.database_readonly_url == ""

    def test_readonly_url_already_normalized(self):
        """Already-prefixed readonly URL is not double-prefixed."""
        s = _make_settings(
            database_readonly_url="postgresql+psycopg://ro:pw@host/db",
        )
        assert s.database_readonly_url == "postgresql+psycopg://ro:pw@host/db"

    def test_sqlite_url_not_modified(self):
        """SQLite URLs should never be rewritten."""
        s = _make_settings(database_url="sqlite://")
        assert s.database_url == "sqlite://"

    def test_mysql_url_not_modified(self):
        """Non-postgresql URLs pass through unchanged."""
        s = _make_settings(database_url="mysql://u:p@host/db")
        assert s.database_url == "mysql://u:p@host/db"


# ---------------------------------------------------------------------------
# Auth validation
# ---------------------------------------------------------------------------


class TestAuthValidation:
    """Tests for auth_enabled / admin_secret_key guard."""

    def test_auth_enabled_without_secret_raises(self):
        """AUTH_ENABLED=true with no ADMIN_SECRET_KEY is a validation error."""
        with pytest.raises(ValueError, match="ADMIN_SECRET_KEY must be set"):
            _make_settings(auth_enabled=True, admin_secret_key="")

    def test_auth_disabled_no_secret_ok(self):
        """AUTH_ENABLED=false does not require ADMIN_SECRET_KEY."""
        s = _make_settings(auth_enabled=False, admin_secret_key="", domain="localhost")
        assert s.auth_enabled is False

    def test_auth_enabled_with_secret_ok(self):
        """AUTH_ENABLED=true + ADMIN_SECRET_KEY set is fine."""
        s = _make_settings(auth_enabled=True, admin_secret_key="a-real-secret")
        assert s.admin_secret_key == "a-real-secret"


# ---------------------------------------------------------------------------
# Public auth guard (domain-based)
# ---------------------------------------------------------------------------


class TestPublicAuthGuard:
    """AUTH_ENABLED=false is blocked on non-localhost domains."""

    def test_localhost_allowed_without_auth(self):
        s = _make_settings(auth_enabled=False, domain="localhost")
        assert s.auth_enabled is False

    def test_127_allowed_without_auth(self):
        s = _make_settings(auth_enabled=False, domain="127.0.0.1")
        assert s.auth_enabled is False

    def test_ipv6_loopback_allowed_without_auth(self):
        s = _make_settings(auth_enabled=False, domain="::1")
        assert s.auth_enabled is False

    def test_production_domain_requires_auth(self):
        with pytest.raises(ValueError, match="AUTH_ENABLED=false is only allowed"):
            _make_settings(auth_enabled=False, domain="labclaw.org")

    def test_custom_domain_requires_auth(self):
        with pytest.raises(ValueError, match="AUTH_ENABLED=false is only allowed"):
            _make_settings(auth_enabled=False, domain="my-lab.example.com")


# ---------------------------------------------------------------------------
# Settings from environment
# ---------------------------------------------------------------------------


class TestSettingsFromEnvironment:
    """Settings reads from environment variables."""

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("LAB_NAME", "Shen Lab")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "secret")
        s = Settings(_env_file=None)
        assert s.lab_name == "Shen Lab"

    def test_unknown_env_vars_ignored(self, monkeypatch):
        """Extra env vars are silently ignored (extra='ignore')."""
        monkeypatch.setenv("TOTALLY_FAKE_VAR", "nope")
        s = Settings(_env_file=None)
        assert not hasattr(s, "totally_fake_var")


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestDefaults:
    """Verify key defaults are safe for local development."""

    def test_auth_enabled_field_is_bool(self):
        """auth_enabled is a boolean field (True when explicitly set)."""
        s = _make_settings(auth_enabled=True)
        assert s.auth_enabled is True

    def test_secure_cookies_default_false(self):
        s = _make_settings()
        assert s.secure_cookies is False

    def test_log_format_default_console(self):
        s = _make_settings()
        assert s.log_format == "console"

    def test_ocr_tier_default_auto(self):
        s = _make_settings()
        assert s.ocr_tier == "auto"

    def test_domain_default_localhost(self):
        s = _make_settings()
        assert s.domain == "localhost"


# ---------------------------------------------------------------------------
# get_settings cache
# ---------------------------------------------------------------------------


class TestGetSettings:
    """Tests for the cached get_settings factory."""

    def test_returns_settings_instance(self):
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, Settings)

    def test_cache_returns_same_object(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_clear_then_new(self, monkeypatch):
        """After cache_clear, next call picks up new env vars."""
        get_settings.cache_clear()
        s1 = get_settings()

        monkeypatch.setenv("LAB_NAME", "New Lab Name")
        get_settings.cache_clear()
        s2 = get_settings()
        assert s2.lab_name == "New Lab Name"
        assert s1 is not s2
