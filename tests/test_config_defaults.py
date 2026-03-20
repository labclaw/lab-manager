"""Test that config defaults are correct and up-to-date."""

from lab_manager.config import Settings


def test_rag_model_default_is_current():
    """RAG model default should be a current LiteLLM-routable model."""
    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.rag_model in ("gemini-2.5-flash", "gemini-2.5-pro")


def test_secure_cookies_default_true(monkeypatch):
    """secure_cookies defaults to True for production safety (set False via SECURE_COOKIES=false for local dev)."""
    monkeypatch.delenv("SECURE_COOKIES", raising=False)
    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.secure_cookies is True
