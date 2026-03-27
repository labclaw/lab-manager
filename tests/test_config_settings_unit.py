"""Comprehensive unit tests for config.Settings.

Covers: defaults, env overrides, validators, DATABASE_URL normalization,
auth guards, edge cases, and get_settings caching.
"""

from __future__ import annotations

import logging

import pytest

from lab_manager.config import Settings, get_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make(**overrides):
    """Create a Settings instance with safe defaults suitable for testing."""
    defaults = {
        "database_url": "sqlite://",
        "admin_secret_key": "test-secret-key",
        "_env_file": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)


# ===================================================================
# 1. Default values for all settings fields
# ===================================================================


class TestDefaults:
    """Verify every field's default when no env overrides are present."""

    def test_database_url_default(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        s = _make(database_url=Settings.model_fields["database_url"].default)
        assert s.database_url == (
            "postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager"
        )

    def test_meilisearch_url_default(self):
        s = _make()
        assert s.meilisearch_url == "http://localhost:7700"

    def test_meilisearch_api_key_default(self):
        s = _make()
        assert s.meilisearch_api_key == ""

    def test_database_readonly_url_default(self):
        s = _make()
        assert s.database_readonly_url == ""

    def test_lab_name_default(self):
        s = _make()
        assert s.lab_name == "My Lab"

    def test_lab_subtitle_default(self):
        s = _make()
        assert s.lab_subtitle == ""

    def test_api_key_default(self):
        s = _make()
        assert s.api_key == ""

    def test_admin_secret_key_default_via_env(self, monkeypatch):
        monkeypatch.delenv("ADMIN_SECRET_KEY", raising=False)
        s = Settings(
            database_url="sqlite://",
            auth_enabled=False,
            _env_file=None,
        )
        assert s.admin_secret_key == ""

    def test_admin_password_default(self, monkeypatch):
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        s = _make(admin_password=Settings.model_fields["admin_password"].default)
        assert s.admin_password == ""

    def test_auth_enabled_default(self, monkeypatch):
        monkeypatch.delenv("AUTH_ENABLED", raising=False)
        monkeypatch.delenv("ADMIN_SECRET_KEY", raising=False)
        s = Settings(
            database_url="sqlite://",
            auth_enabled=Settings.model_fields["auth_enabled"].default,
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.auth_enabled is True

    def test_secure_cookies_default(self):
        s = _make()
        assert s.secure_cookies is False

    def test_domain_default(self):
        s = _make()
        assert s.domain == "localhost"

    def test_ocr_tier_default(self):
        s = _make()
        assert s.ocr_tier == "auto"

    def test_ocr_model_default(self):
        s = _make()
        assert s.ocr_model == "nvidia_nim/meta/llama-3.2-90b-vision-instruct"

    def test_ocr_local_model_default(self):
        s = _make()
        assert s.ocr_local_model == "dots_mocr"

    def test_ocr_local_url_default(self):
        s = _make()
        assert s.ocr_local_url == "http://localhost:8000/v1"

    def test_extraction_model_default(self):
        s = _make()
        assert s.extraction_model == "nvidia_nim/z-ai/glm5"

    def test_extraction_api_key_default(self):
        s = _make()
        assert s.extraction_api_key == ""

    def test_mistral_api_key_default(self):
        s = _make()
        assert s.mistral_api_key == ""

    def test_openai_api_key_default(self):
        s = _make()
        assert s.openai_api_key == ""

    def test_gemini_api_key_default(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        s = _make(gemini_api_key=Settings.model_fields["gemini_api_key"].default)
        assert s.gemini_api_key == ""

    def test_google_api_key_default(self):
        s = _make()
        assert s.google_api_key == ""

    def test_rag_model_default(self):
        s = _make()
        assert s.rag_model == "nvidia_nim/z-ai/glm5"

    def test_rag_api_key_default(self):
        s = _make()
        assert s.rag_api_key == ""

    def test_rag_base_url_default(self):
        s = _make()
        assert s.rag_base_url == ""

    def test_nvidia_build_api_key_default(self):
        s = _make()
        assert s.nvidia_build_api_key == ""

    def test_litellm_config_path_default(self):
        s = _make()
        assert s.litellm_config_path == ""

    def test_routing_strategy_default(self):
        s = _make()
        assert s.routing_strategy == "auto"

    def test_slack_webhook_url_default(self):
        s = _make()
        assert s.slack_webhook_url == ""

    def test_notification_webhook_url_default(self):
        s = _make()
        assert s.notification_webhook_url == ""

    def test_notification_severities_default(self):
        s = _make()
        assert s.notification_severities == "critical,warning"

    def test_log_format_default(self):
        s = _make()
        assert s.log_format == "console"

    def test_upload_dir_default(self, monkeypatch):
        monkeypatch.delenv("UPLOAD_DIR", raising=False)
        s = _make(upload_dir=Settings.model_fields["upload_dir"].default)
        assert s.upload_dir == "uploads"

    def test_scans_dir_default(self):
        s = _make()
        assert s.scans_dir == ""

    def test_devices_dir_default(self):
        s = _make()
        assert s.devices_dir == ""


# ===================================================================
# 2. Environment variable overrides
# ===================================================================


class TestEnvOverrides:
    """Verify that every field reads from the expected env var."""

    def test_database_url_from_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example.com/prod")
        s = Settings(
            admin_secret_key="test",
            _env_file=None,
        )
        assert "db.example.com" in s.database_url

    def test_meilisearch_url_from_env(self, monkeypatch):
        monkeypatch.setenv("MEILISEARCH_URL", "http://search:7700")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.meilisearch_url == "http://search:7700"

    def test_meilisearch_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("MEILISEARCH_API_KEY", "secret-key-123")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.meilisearch_api_key == "secret-key-123"

    def test_lab_name_from_env(self, monkeypatch):
        monkeypatch.setenv("LAB_NAME", "Shen Lab")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.lab_name == "Shen Lab"

    def test_lab_subtitle_from_env(self, monkeypatch):
        monkeypatch.setenv("LAB_SUBTITLE", "MGH/Harvard")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.lab_subtitle == "MGH/Harvard"

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "my-api-key")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.api_key == "my-api-key"

    def test_admin_secret_key_from_env(self, monkeypatch):
        monkeypatch.setenv("ADMIN_SECRET_KEY", "admin-secret")
        s = Settings(
            database_url="sqlite://",
            _env_file=None,
        )
        assert s.admin_secret_key == "admin-secret"

    def test_admin_password_from_env(self, monkeypatch):
        monkeypatch.setenv("ADMIN_PASSWORD", "s3cure!")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.admin_password == "s3cure!"

    def test_auth_enabled_from_env_true(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "true")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.auth_enabled is True

    def test_auth_enabled_from_env_false(self, monkeypatch):
        monkeypatch.setenv("AUTH_ENABLED", "false")
        monkeypatch.delenv("ADMIN_SECRET_KEY", raising=False)
        s = Settings(
            database_url="sqlite://",
            _env_file=None,
        )
        assert s.auth_enabled is False

    def test_secure_cookies_from_env(self, monkeypatch):
        monkeypatch.setenv("SECURE_COOKIES", "true")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.secure_cookies is True

    def test_domain_from_env(self, monkeypatch):
        monkeypatch.setenv("DOMAIN", "lab.example.com")
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test")
        s = Settings(_env_file=None)
        assert s.domain == "lab.example.com"

    def test_ocr_tier_from_env(self, monkeypatch):
        monkeypatch.setenv("OCR_TIER", "api")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.ocr_tier == "api"

    def test_ocr_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OCR_MODEL", "custom-model")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.ocr_model == "custom-model"

    def test_ocr_local_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OCR_LOCAL_MODEL", "qwen3vl")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.ocr_local_model == "qwen3vl"

    def test_ocr_local_url_from_env(self, monkeypatch):
        monkeypatch.setenv("OCR_LOCAL_URL", "http://gpu:8080/v1")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.ocr_local_url == "http://gpu:8080/v1"

    def test_extraction_model_from_env(self, monkeypatch):
        monkeypatch.setenv("EXTRACTION_MODEL", "gpt-5.4")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.extraction_model == "gpt-5.4"

    def test_rag_model_from_env(self, monkeypatch):
        monkeypatch.setenv("RAG_MODEL", "gemini-2.5-flash")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.rag_model == "gemini-2.5-flash"

    def test_rag_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("RAG_API_KEY", "rag-key")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.rag_api_key == "rag-key"

    def test_rag_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("RAG_BASE_URL", "http://llm:4000")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.rag_base_url == "http://llm:4000"

    def test_nvidia_build_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_BUILD_API_KEY", "nv-key")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.nvidia_build_api_key == "nv-key"

    def test_litellm_config_path_from_env(self, monkeypatch):
        monkeypatch.setenv("LITELLM_CONFIG_PATH", "/etc/litellm.yaml")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.litellm_config_path == "/etc/litellm.yaml"

    def test_routing_strategy_from_env(self, monkeypatch):
        monkeypatch.setenv("ROUTING_STRATEGY", "high")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.routing_strategy == "high"

    def test_slack_webhook_url_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/xxx")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.slack_webhook_url == "https://hooks.slack.com/xxx"

    def test_notification_webhook_url_from_env(self, monkeypatch):
        monkeypatch.setenv("NOTIFICATION_WEBHOOK_URL", "https://notify.example.com")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.notification_webhook_url == "https://notify.example.com"

    def test_notification_severities_from_env(self, monkeypatch):
        monkeypatch.setenv("NOTIFICATION_SEVERITIES", "critical,warning,info")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.notification_severities == "critical,warning,info"

    def test_log_format_from_env(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "json")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.log_format == "json"

    def test_upload_dir_from_env(self, monkeypatch):
        monkeypatch.setenv("UPLOAD_DIR", "/data/uploads")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.upload_dir == "/data/uploads"

    def test_scans_dir_from_env(self, monkeypatch):
        monkeypatch.setenv("SCANS_DIR", "/data/scans")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.scans_dir == "/data/scans"

    def test_devices_dir_from_env(self, monkeypatch):
        monkeypatch.setenv("DEVICES_DIR", "/data/devices")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.devices_dir == "/data/devices"

    def test_database_readonly_url_from_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_READONLY_URL", "postgresql://ro:p@host/db")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert "ro:p@host" in s.database_readonly_url

    def test_extraneous_env_vars_ignored(self, monkeypatch):
        """Extra env vars should not cause errors (extra='ignore')."""
        monkeypatch.setenv("TOTALLY_UNKNOWN_VAR", "whatever")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.admin_secret_key == "test"

    def test_keyword_constructor_overrides_env(self, monkeypatch):
        """Constructor kwargs take precedence over env vars."""
        monkeypatch.setenv("LAB_NAME", "from-env")
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            lab_name="from-ctor",
            _env_file=None,
        )
        assert s.lab_name == "from-ctor"


# ===================================================================
# 3. Field validators
# ===================================================================


class TestDatabaseUrlNormalization:
    """Tests for _normalize_database_urls validator."""

    def test_postgresql_prefix_added(self):
        s = _make(database_url="postgresql://user:pass@host:5432/db")
        assert s.database_url == "postgresql+psycopg://user:pass@host:5432/db"

    def test_already_normalized_unchanged(self):
        s = _make(database_url="postgresql+psycopg://user:pass@host:5432/db")
        assert s.database_url == "postgresql+psycopg://user:pass@host:5432/db"

    def test_sqlite_url_unchanged(self):
        s = _make(database_url="sqlite://")
        assert s.database_url == "sqlite://"

    def test_sqlite_file_url_unchanged(self):
        s = _make(database_url="sqlite:///data/test.db")
        assert s.database_url == "sqlite:///data/test.db"

    def test_readonly_url_normalized(self):
        s = _make(database_readonly_url="postgresql://ro:pw@replica:5432/db")
        assert s.database_readonly_url == "postgresql+psycopg://ro:pw@replica:5432/db"

    def test_readonly_url_already_normalized(self):
        s = _make(database_readonly_url="postgresql+psycopg://ro:pw@replica:5432/db")
        assert s.database_readonly_url == "postgresql+psycopg://ro:pw@replica:5432/db"

    def test_empty_readonly_url_stays_empty(self):
        s = _make(database_readonly_url="")
        assert s.database_readonly_url == ""

    def test_both_urls_normalized(self):
        s = _make(
            database_url="postgresql://u1:p1@host1/db1",
            database_readonly_url="postgresql://u2:p2@host2/db2",
        )
        assert s.database_url == "postgresql+psycopg://u1:p1@host1/db1"
        assert s.database_readonly_url == "postgresql+psycopg://u2:p2@host2/db2"

    def test_double_prefix_not_applied(self):
        """Ensure normalization is not applied to an already-prefixed URL."""
        s = _make(database_url="postgresql+psycopg://u:p@h/d")
        assert "psycopg+psycopg" not in s.database_url


class TestAuthValidator:
    """Tests for _validate_auth_config validator."""

    def test_auth_enabled_with_secret_key_ok(self):
        s = _make(auth_enabled=True, admin_secret_key="good-key")
        assert s.auth_enabled is True

    def test_auth_enabled_without_secret_key_raises(self):
        with pytest.raises(ValueError, match="ADMIN_SECRET_KEY must be set"):
            _make(auth_enabled=True, admin_secret_key="")

    def test_auth_disabled_no_secret_key_ok(self):
        """When auth is disabled, empty secret key is fine."""
        s = _make(auth_enabled=False, admin_secret_key="")
        assert s.auth_enabled is False

    def test_auth_disabled_with_secret_key_ok(self):
        """Having a secret key when auth is disabled should not raise."""
        s = _make(auth_enabled=False, admin_secret_key="unused-key")
        assert s.auth_enabled is False


class TestPublicAuthGuard:
    """Tests for _validate_public_auth_guard validator."""

    def test_localhost_no_auth_ok(self):
        s = _make(auth_enabled=False, domain="localhost")
        assert s.domain == "localhost"

    def test_127_no_auth_ok(self):
        s = _make(auth_enabled=False, domain="127.0.0.1")
        assert s.domain == "127.0.0.1"

    def test_ipv6_loopback_no_auth_ok(self):
        s = _make(auth_enabled=False, domain="::1")
        assert s.domain == "::1"

    def test_public_domain_no_auth_raises(self):
        with pytest.raises(ValueError, match="AUTH_ENABLED=false is only allowed"):
            _make(auth_enabled=False, domain="lab.example.com")

    def test_public_domain_with_auth_ok(self):
        s = _make(auth_enabled=True, domain="lab.example.com", admin_secret_key="key")
        assert s.domain == "lab.example.com"

    def test_ip_address_public_no_auth_raises(self):
        with pytest.raises(ValueError, match="AUTH_ENABLED=false is only allowed"):
            _make(auth_enabled=False, domain="203.0.113.50")


class TestWarnDefaultDatabaseUrl:
    """Tests for _warn_default_database_url validator (warning logging)."""

    def test_warns_on_default_url(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
            Settings(
                database_url="postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager",
                admin_secret_key="test",
                _env_file=None,
            )
        assert any("default DATABASE_URL" in r.message for r in caplog.records)

    def test_no_warning_on_custom_url(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
            _make(database_url="postgresql+psycopg://custom:pw@host/db")
        assert not any("default DATABASE_URL" in r.message for r in caplog.records)


class TestWarnDefaultAdminPassword:
    """Tests for _warn_default_admin_password validator (warning logging)."""

    def test_warns_on_empty_password_with_auth(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
            _make(auth_enabled=True, admin_password="")
        assert any("ADMIN_PASSWORD is empty" in r.message for r in caplog.records)

    def test_warns_on_changeme_password(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
            _make(auth_enabled=True, admin_password="changeme123")
        assert any("default-style value" in r.message for r in caplog.records)

    def test_no_warning_on_strong_password(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
            _make(auth_enabled=True, admin_password="S3cur3P@ssw0rd!")
        pwd_warnings = [r for r in caplog.records if "ADMIN_PASSWORD" in r.message]
        assert len(pwd_warnings) == 0

    def test_no_warning_when_auth_disabled(self, caplog):
        """Empty password is fine when auth is disabled entirely."""
        with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
            _make(auth_enabled=False, admin_password="")
        pwd_warnings = [r for r in caplog.records if "ADMIN_PASSWORD" in r.message]
        assert len(pwd_warnings) == 0

    def test_warns_on_whitespace_only_password(self, caplog):
        with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
            _make(auth_enabled=True, admin_password="   ")
        assert any("ADMIN_PASSWORD is empty" in r.message for r in caplog.records)


# ===================================================================
# 4. Boolean parsing edge cases
# ===================================================================


class TestBooleanParsing:
    """Verify truthy/falsy env values for bool fields."""

    @pytest.mark.parametrize("truthy", ["true", "True", "TRUE", "1", "yes"])
    def test_truthy_values(self, monkeypatch, truthy):
        monkeypatch.setenv("SECURE_COOKIES", truthy)
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.secure_cookies is True

    @pytest.mark.parametrize("falsy", ["false", "False", "FALSE", "0", "no"])
    def test_falsy_values(self, monkeypatch, falsy):
        monkeypatch.setenv("SECURE_COOKIES", falsy)
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
        )
        assert s.secure_cookies is False


# ===================================================================
# 5. get_settings caching behavior
# ===================================================================


class TestGetSettings:
    """Tests for the get_settings singleton/lru_cache."""

    def test_returns_settings_instance(self):
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, Settings)

    def test_cached_return_same_instance(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_clear_returns_new_instance(self):
        get_settings.cache_clear()
        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()
        assert s1 is not s2


# ===================================================================
# 6. Model config
# ===================================================================


class TestModelConfig:
    """Tests for the Pydantic model configuration."""

    def test_extra_fields_ignored(self):
        """Settings with extra='ignore' should silently drop unknown fields."""
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            _env_file=None,
            unknown_field="should be ignored",
        )
        assert not hasattr(s, "unknown_field")

    def test_env_file_encoding_utf8(self):
        assert Settings.model_config["env_file_encoding"] == "utf-8"

    def test_env_file_is_dotenv(self):
        assert Settings.model_config["env_file"] == ".env"


# ===================================================================
# 7. Combined / integration-style edge cases
# ===================================================================


class TestEdgeCases:
    """Edge cases spanning multiple validators."""

    def test_minimal_prod_like_config(self, monkeypatch):
        """A realistic production-like configuration should load cleanly."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://app:pw@db.host/lab")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "a" * 64)
        monkeypatch.setenv("AUTH_ENABLED", "true")
        monkeypatch.setenv("ADMIN_PASSWORD", "prod-pw-12345")
        monkeypatch.setenv("DOMAIN", "lab.myorg.com")
        monkeypatch.setenv("MEILISEARCH_URL", "http://search:7700")
        monkeypatch.setenv("LAB_NAME", "Production Lab")
        monkeypatch.setenv("LOG_FORMAT", "json")
        s = Settings(_env_file=None)
        assert s.domain == "lab.myorg.com"
        assert s.auth_enabled is True
        assert "db.host" in s.database_url

    def test_local_dev_config(self):
        """Minimal local dev config with auth disabled."""
        s = _make(auth_enabled=False, admin_secret_key="", domain="localhost")
        assert s.auth_enabled is False
        assert s.domain == "localhost"

    def test_url_with_special_chars(self):
        """Database URL with URL-encoded special characters."""
        s = _make(database_url="postgresql://user:p%40ss@host/db")
        assert "+psycopg" in s.database_url
        assert "p%40ss" in s.database_url

    def test_long_api_key(self):
        """Very long API key should be stored without truncation."""
        long_key = "x" * 10000
        s = _make(extraction_api_key=long_key)
        assert s.extraction_api_key == long_key

    def test_unicode_lab_name(self):
        """Lab name with unicode characters."""
        s = _make(lab_name="Shen Lab \u6c88\u5b9e\u9a8c\u5ba4")
        assert "\u6c88" in s.lab_name
