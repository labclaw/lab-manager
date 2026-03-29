"""Test LiteLLM response_text guard against empty choices."""

from __future__ import annotations

from unittest.mock import MagicMock

from lab_manager.services.litellm_client import response_text


def test_empty_choices_returns_empty_string():
    """response_text must return '' when response.choices is empty."""
    resp = MagicMock()
    resp.choices = []
    assert response_text(resp) == ""


def test_none_choices_returns_empty_string():
    """response_text must return '' when response.choices is None."""
    resp = MagicMock()
    resp.choices = None
    assert response_text(resp) == ""


def test_normal_response_extracts_text():
    """response_text works normally with valid choices."""
    msg = MagicMock()
    msg.content = "Hello world"
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    assert response_text(resp) == "Hello world"
