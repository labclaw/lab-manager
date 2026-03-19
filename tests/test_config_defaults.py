"""Test that config defaults are correct and up-to-date."""

from lab_manager.config import Settings


def test_rag_model_default_is_current():
    """RAG model default should be a current Gemini model via GenAI API."""
    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.rag_model in ("gemini-2.5-flash", "gemini-2.5-pro")


def test_secure_cookies_default_false(monkeypatch):
    """secure_cookies defaults to False for local dev (set True via SECURE_COOKIES=true in production)."""
    monkeypatch.delenv("SECURE_COOKIES", raising=False)
    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.secure_cookies is False
