"""Test that config defaults are correct and up-to-date."""

from lab_manager.config import Settings


def test_rag_model_default_is_current():
    """RAG model default should be a current LiteLLM-routable model."""
    import os

    os.environ.pop("RAG_MODEL", None)
    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.rag_model in ("gemini-2.5-flash", "gemini-2.5-pro", "nvidia_nim/z-ai/glm5")


def test_secure_cookies_default_true(monkeypatch):
    """secure_cookies defaults to True (secure by default)."""
    monkeypatch.delenv("SECURE_COOKIES", raising=False)
    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.secure_cookies is True


def test_insecure_cookies_warning_on_non_localhost(monkeypatch, caplog):
    """Warn when auth_enabled + non-localhost domain + secure_cookies=False."""
    import logging

    monkeypatch.delenv("SECURE_COOKIES", raising=False)
    with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
        Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            auth_enabled=True,
            domain="mylab.example.com",
            secure_cookies=False,
            _env_file=None,
        )
    assert "SECURE_COOKIES is False" in caplog.text


def test_no_insecure_cookies_warning_on_localhost(monkeypatch, caplog):
    """No warning on localhost even if secure_cookies=False."""
    import logging

    monkeypatch.delenv("SECURE_COOKIES", raising=False)
    with caplog.at_level(logging.WARNING, logger="lab_manager.config"):
        Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            auth_enabled=True,
            domain="localhost",
            secure_cookies=False,
            _env_file=None,
        )
    assert "SECURE_COOKIES is False" not in caplog.text


def test_api_key_role_default_admin():
    """api_key_role defaults to 'admin'."""
    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.api_key_role == "admin"


def test_api_key_role_accepts_valid_roles():
    """api_key_role accepts all known role names."""
    for role in (
        "pi",
        "admin",
        "postdoc",
        "grad_student",
        "tech",
        "undergrad",
        "visitor",
    ):
        s = Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            api_key_role=role,
            _env_file=None,
        )
        assert s.api_key_role == role


def test_api_key_role_rejects_invalid_role():
    """api_key_role rejects unknown role names."""
    import pytest

    with pytest.raises(ValueError, match="API_KEY_ROLE must be one of"):
        Settings(
            database_url="sqlite://",
            admin_secret_key="test",
            api_key_role="superadmin",
            _env_file=None,
        )
