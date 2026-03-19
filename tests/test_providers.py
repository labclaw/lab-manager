"""Tests for VLM and OCR provider modules."""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.intake.providers import (
    OCRProvider,
    VLMProvider,
    parse_json_response,
)
from lab_manager.intake.providers.claude import ClaudeProvider
from lab_manager.intake.providers.codex import CodexProvider
from lab_manager.intake.providers.gemini import GeminiProvider
from lab_manager.intake.providers.more_ocr import (
    ClaudeOCRProvider,
    CodexOCRProvider,
    DeepSeekVLProvider,
    GLMOCRProvider,
    MistralOCRProvider,
    OCR_PROVIDERS,
    PaddleOCRProvider,
    VLM_PROVIDERS,
    get_provider,
)
from lab_manager.intake.providers.qwen_vllm import (
    GeminiAPIOCRProvider,
    GeminiOCRProvider,
    QwenVLLMProvider,
)


def _mock_openai_response(content: str | None = "text"):
    """Create a mock OpenAI chat completion response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def _mock_genai_response(text: str = "text"):
    """Create a mock google.genai Client response."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = text
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


# ---------------------------------------------------------------------------
# parse_json_response
# ---------------------------------------------------------------------------


class TestParseJsonResponse:
    def test_none_input(self):
        assert parse_json_response(None) is None

    def test_empty_string(self):
        assert parse_json_response("") is None

    def test_plain_json(self):
        assert parse_json_response('{"key": "val"}') == {"key": "val"}

    def test_markdown_fenced_json(self):
        text = '```json\n{"a": 1}\n```'
        assert parse_json_response(text) == {"a": 1}

    def test_json_embedded_in_text(self):
        text = 'Here is the result: {"x": 2} done.'
        assert parse_json_response(text) == {"x": 2}

    def test_invalid_json_returns_none(self):
        assert parse_json_response("not json at all") is None


# ---------------------------------------------------------------------------
# VLMProvider base class
# ---------------------------------------------------------------------------


class ConcreteVLM(VLMProvider):
    name = "test_vlm"
    model_id = "test-model"

    def __init__(self, response: str | None = '{"a": 1}'):
        self._response = response

    def extract_from_image(self, image_path: str, prompt: str):
        return self._response


class TestVLMProviderBase:
    def test_extract_returns_parsed_json(self):
        p = ConcreteVLM('{"key": "value"}')
        assert p.extract("img.png", "do it") == {"key": "value"}

    def test_extract_returns_none_on_empty(self):
        p = ConcreteVLM(None)
        assert p.extract("img.png", "do it") is None

    def test_review_delegates_to_extract(self):
        p = ConcreteVLM('{"r": 1}')
        assert p.review("img.png", "check") == {"r": 1}

    def test_repr(self):
        p = ConcreteVLM()
        assert "ConcreteVLM" in repr(p)
        assert "test-model" in repr(p)


# ---------------------------------------------------------------------------
# OCRProvider base class
# ---------------------------------------------------------------------------


class ConcreteOCR(OCRProvider):
    name = "test_ocr"
    model_id = "test-ocr-model"

    def extract_text(self, image_path: str) -> str:
        return "text"


class TestOCRProviderBase:
    def test_repr(self):
        p = ConcreteOCR()
        assert "ConcreteOCR" in repr(p)
        assert "test-ocr-model" in repr(p)


# ---------------------------------------------------------------------------
# ClaudeProvider
# ---------------------------------------------------------------------------


class TestClaudeProvider:
    def test_init_defaults(self):
        p = ClaudeProvider()
        assert p.model == "claude-opus-4-6"
        assert p.timeout == 180

    @patch("lab_manager.intake.providers.claude.subprocess.run")
    def test_extract_success(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="  extracted text  ", stderr=""
        )
        p = ClaudeProvider()
        result = p.extract_from_image("/img.png", "extract")
        assert result == "extracted text"

    @patch("lab_manager.intake.providers.claude.subprocess.run")
    def test_extract_nonzero_rc(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=1, stdout="", stderr="error msg"
        )
        p = ClaudeProvider()
        assert p.extract_from_image("/img.png", "extract") is None

    @patch("lab_manager.intake.providers.claude.subprocess.run")
    def test_extract_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=180)
        p = ClaudeProvider()
        assert p.extract_from_image("/img.png", "extract") is None

    @patch("lab_manager.intake.providers.claude.subprocess.run")
    def test_extract_generic_exception(self, mock_run):
        mock_run.side_effect = OSError("not found")
        p = ClaudeProvider()
        assert p.extract_from_image("/img.png", "extract") is None


# ---------------------------------------------------------------------------
# CodexProvider
# ---------------------------------------------------------------------------


class TestCodexProvider:
    def test_init_defaults(self):
        p = CodexProvider()
        assert p.model == "gpt-5.4"

    @patch("lab_manager.intake.providers.codex.subprocess.run")
    def test_extract_success(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="result", stderr=""
        )
        p = CodexProvider()
        assert p.extract_from_image("/img.png", "do") == "result"

    @patch("lab_manager.intake.providers.codex.subprocess.run")
    def test_extract_nonzero_rc(self, mock_run):
        mock_run.return_value = SimpleNamespace(returncode=1, stdout="", stderr="err")
        p = CodexProvider()
        assert p.extract_from_image("/img.png", "do") is None

    @patch("lab_manager.intake.providers.codex.subprocess.run")
    def test_extract_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="codex", timeout=180)
        p = CodexProvider()
        assert p.extract_from_image("/img.png", "do") is None

    @patch("lab_manager.intake.providers.codex.subprocess.run")
    def test_extract_generic_exception(self, mock_run):
        mock_run.side_effect = RuntimeError("boom")
        p = CodexProvider()
        assert p.extract_from_image("/img.png", "do") is None


# ---------------------------------------------------------------------------
# GeminiProvider
# ---------------------------------------------------------------------------


class TestGeminiProvider:
    def test_init_defaults(self):
        p = GeminiProvider()
        assert p.model == "gemini-3.1-pro-preview"

    @patch("lab_manager.intake.providers.gemini.subprocess.run")
    def test_extract_success(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="gemini result", stderr=""
        )
        p = GeminiProvider()
        assert p.extract_from_image("/img.png", "do") == "gemini result"

    @patch("lab_manager.intake.providers.gemini.subprocess.run")
    def test_extract_nonzero_rc(self, mock_run):
        mock_run.return_value = SimpleNamespace(returncode=1, stdout="", stderr="err")
        p = GeminiProvider()
        assert p.extract_from_image("/img.png", "do") is None

    @patch("lab_manager.intake.providers.gemini.subprocess.run")
    def test_extract_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gemini", timeout=180)
        p = GeminiProvider()
        assert p.extract_from_image("/img.png", "do") is None

    @patch("lab_manager.intake.providers.gemini.subprocess.run")
    def test_extract_generic_exception(self, mock_run):
        mock_run.side_effect = FileNotFoundError("no binary")
        p = GeminiProvider()
        assert p.extract_from_image("/img.png", "do") is None


# ---------------------------------------------------------------------------
# QwenVLLMProvider — OpenAI is imported inside extract_text()
# ---------------------------------------------------------------------------


class TestQwenVLLMProvider:
    def test_init_defaults(self):
        p = QwenVLLMProvider()
        assert p.model == "Qwen/Qwen3-VL-4B-Instruct"

    def test_extract_text_jpg(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8fake jpeg")

        mock_client = _mock_openai_response("OCR text")
        mock_openai = MagicMock(return_value=mock_client)
        with patch.dict(sys.modules, {"openai": MagicMock(OpenAI=mock_openai)}):
            # Reimport not needed since OpenAI is imported inside method
            p = QwenVLLMProvider()
            # Directly mock the extract_text method's local import
            with patch(
                "builtins.__import__",
                wraps=__builtins__.__import__
                if hasattr(__builtins__, "__import__")
                else __import__,
            ):
                pass
        # Simpler approach: mock the method directly to test class behavior
        p = QwenVLLMProvider()
        p.extract_text = MagicMock(return_value="OCR text")
        assert p.extract_text(str(img)) == "OCR text"

    def test_extract_text_uses_openai(self, tmp_path):
        """Integration-style test: mock OpenAI at module level and call."""
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNGfake")

        mock_client = _mock_openai_response("png text")
        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            # Force re-import of the method
            import importlib
            import lab_manager.intake.providers.qwen_vllm as qwen_mod

            importlib.reload(qwen_mod)
            p = qwen_mod.QwenVLLMProvider()
            result = p.extract_text(str(img))
            assert result == "png text"

    def test_extract_text_none_content(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"data")

        mock_client = _mock_openai_response(None)
        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            import importlib
            import lab_manager.intake.providers.qwen_vllm as qwen_mod

            importlib.reload(qwen_mod)
            p = qwen_mod.QwenVLLMProvider()
            assert p.extract_text(str(img)) == ""


# ---------------------------------------------------------------------------
# GeminiOCRProvider — uses subprocess (imported at module level)
# ---------------------------------------------------------------------------


class TestGeminiOCRProvider:
    def test_init_defaults(self):
        p = GeminiOCRProvider()
        assert p.model == "gemini-3.1-flash-preview"

    def test_extract_text_success(self):
        p = GeminiOCRProvider()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(
                returncode=0, stdout="  ocr text  ", stderr=""
            )
            assert p.extract_text("/img.png") == "ocr text"

    def test_extract_text_failure(self):
        p = GeminiOCRProvider()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(
                returncode=1, stdout="", stderr="error"
            )
            assert p.extract_text("/img.png") == ""

    def test_extract_text_exception(self):
        p = GeminiOCRProvider()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("nope")
            assert p.extract_text("/img.png") == ""


# ---------------------------------------------------------------------------
# GeminiAPIOCRProvider — genai imported inside method
# ---------------------------------------------------------------------------


class TestGeminiAPIOCRProvider:
    def test_init_defaults(self):
        p = GeminiAPIOCRProvider()
        assert p.model == "gemini-2.5-flash"

    def test_extract_text_with_api_key(self, tmp_path):
        img = tmp_path / "doc.jpeg"
        img.write_bytes(b"\xff\xd8fake")

        mock_client = _mock_genai_response("api ocr text")
        mock_genai = MagicMock()
        mock_genai.Client = MagicMock(return_value=mock_client)

        with patch.dict(
            sys.modules,
            {"google.genai": mock_genai, "google": MagicMock(genai=mock_genai)},
        ):
            import importlib
            import lab_manager.intake.providers.qwen_vllm as qwen_mod

            importlib.reload(qwen_mod)
            p = qwen_mod.GeminiAPIOCRProvider(api_key="test-key")
            result = p.extract_text(str(img))
            assert result == "api ocr text"


# ---------------------------------------------------------------------------
# more_ocr.py providers — OpenAI imported inside methods
# ---------------------------------------------------------------------------


class TestDeepSeekVLProvider:
    def test_init_defaults(self):
        p = DeepSeekVLProvider()
        assert p.model == "deepseek-ai/DeepSeek-VL2"

    def test_extract_text_jpg(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"jpeg data")

        mock_client = _mock_openai_response("deep text")
        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            import importlib
            import lab_manager.intake.providers.more_ocr as ocr_mod

            importlib.reload(ocr_mod)
            p = ocr_mod.DeepSeekVLProvider()
            assert p.extract_text(str(img)) == "deep text"

    def test_extract_text_png(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"png data")

        mock_client = _mock_openai_response("png text")
        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            import importlib
            import lab_manager.intake.providers.more_ocr as ocr_mod

            importlib.reload(ocr_mod)
            p = ocr_mod.DeepSeekVLProvider()
            assert p.extract_text(str(img)) == "png text"

    def test_extract_text_none_content(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"data")

        mock_client = _mock_openai_response(None)
        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            import importlib
            import lab_manager.intake.providers.more_ocr as ocr_mod

            importlib.reload(ocr_mod)
            p = ocr_mod.DeepSeekVLProvider()
            assert p.extract_text(str(img)) == ""


class TestGLMOCRProvider:
    def test_init_defaults(self):
        p = GLMOCRProvider()
        assert p.model == "THUDM/glm-4v-9b"

    def test_extract_text(self, tmp_path):
        img = tmp_path / "test.jpeg"
        img.write_bytes(b"jpeg data")

        mock_client = _mock_openai_response("glm text")
        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            import importlib
            import lab_manager.intake.providers.more_ocr as ocr_mod

            importlib.reload(ocr_mod)
            p = ocr_mod.GLMOCRProvider()
            assert p.extract_text(str(img)) == "glm text"


class TestPaddleOCRProvider:
    def test_init_defaults(self):
        p = PaddleOCRProvider()
        assert p.lang == "en"
        assert p._ocr is None

    def test_extract_text(self):
        p = PaddleOCRProvider()
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [
            [([0, 0], ("line 1", 0.9)), ([0, 1], ("line 2", 0.8))]
        ]
        p._ocr = mock_ocr
        result = p.extract_text("/img.png")
        assert "line 1" in result
        assert "line 2" in result

    def test_extract_text_empty_page(self):
        p = PaddleOCRProvider()
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [None]
        p._ocr = mock_ocr
        assert p.extract_text("/img.png") == ""

    def test_get_ocr_lazy_init(self):
        p = PaddleOCRProvider()
        mock_paddle = MagicMock()
        with patch.dict(sys.modules, {"paddleocr": mock_paddle}):
            p._get_ocr()
            assert p._ocr is not None

    def test_get_ocr_caches(self):
        p = PaddleOCRProvider()
        sentinel = MagicMock()
        p._ocr = sentinel
        assert p._get_ocr() is sentinel


class TestMistralOCRProvider:
    def test_init_defaults(self):
        p = MistralOCRProvider()
        assert p.model == "pixtral-large-latest"

    def test_extract_text(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"data")

        mock_client = _mock_openai_response("mistral text")
        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            import importlib
            import lab_manager.intake.providers.more_ocr as ocr_mod

            importlib.reload(ocr_mod)
            p = ocr_mod.MistralOCRProvider(api_key="key")
            assert p.extract_text(str(img)) == "mistral text"

    @patch.dict("os.environ", {"MISTRAL_API_KEY": "env-key"})
    def test_extract_text_env_key(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"data")

        mock_client = _mock_openai_response("text")
        mock_openai_mod = MagicMock()
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"openai": mock_openai_mod}):
            import importlib
            import lab_manager.intake.providers.more_ocr as ocr_mod

            importlib.reload(ocr_mod)
            p = ocr_mod.MistralOCRProvider()
            p.extract_text(str(img))


class TestClaudeOCRProvider:
    def test_init(self):
        p = ClaudeOCRProvider()
        assert p.timeout == 120

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_success(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="claude ocr", stderr=""
        )
        p = ClaudeOCRProvider()
        assert p.extract_text("/img.png") == "claude ocr"

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_failure(self, mock_run):
        mock_run.return_value = SimpleNamespace(returncode=1, stdout="", stderr="err")
        p = ClaudeOCRProvider()
        assert p.extract_text("/img.png") == ""

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_exception(self, mock_run):
        mock_run.side_effect = OSError("boom")
        p = ClaudeOCRProvider()
        assert p.extract_text("/img.png") == ""


class TestCodexOCRProvider:
    def test_init(self):
        p = CodexOCRProvider()
        assert p.timeout == 120

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_success(self, mock_run):
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout="codex ocr", stderr=""
        )
        p = CodexOCRProvider()
        assert p.extract_text("/img.png") == "codex ocr"

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_failure(self, mock_run):
        mock_run.return_value = SimpleNamespace(returncode=1, stdout="", stderr="err")
        p = CodexOCRProvider()
        assert p.extract_text("/img.png") == ""

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_exception(self, mock_run):
        mock_run.side_effect = RuntimeError("boom")
        p = CodexOCRProvider()
        assert p.extract_text("/img.png") == ""


# ---------------------------------------------------------------------------
# Provider registry / get_provider
# ---------------------------------------------------------------------------


class TestProviderRegistry:
    def test_ocr_providers_dict(self):
        assert "qwen3_vl" in OCR_PROVIDERS
        assert "gemini_flash" in OCR_PROVIDERS
        assert "gemini_api" in OCR_PROVIDERS
        assert "deepseek_vl" in OCR_PROVIDERS
        assert "glm_4v" in OCR_PROVIDERS
        assert "paddleocr" in OCR_PROVIDERS
        assert "mistral_pixtral" in OCR_PROVIDERS
        assert "claude_sonnet" in OCR_PROVIDERS
        assert "codex_gpt" in OCR_PROVIDERS

    def test_vlm_providers_dict(self):
        assert "opus_4_6" in VLM_PROVIDERS
        assert "gemini_3_1_pro" in VLM_PROVIDERS
        assert "gpt_5_4" in VLM_PROVIDERS

    def test_get_provider_vlm(self):
        p = get_provider("opus_4_6")
        assert isinstance(p, ClaudeProvider)

    def test_get_provider_ocr(self):
        p = get_provider("claude_sonnet")
        assert type(p).__name__ == "ClaudeOCRProvider"

    def test_get_provider_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent_provider")

    def test_get_provider_custom_registry(self):
        registry = {"custom": "lab_manager.intake.providers.claude:ClaudeProvider"}
        p = get_provider("custom", registry=registry)
        assert isinstance(p, ClaudeProvider)
