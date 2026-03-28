"""Additional tests for more_ocr.py to reach 95%+ coverage.

Covers error paths, edge cases, and provider classes not tested elsewhere.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# DeepSeekVLProvider (lines 31-66)
# ---------------------------------------------------------------------------


class TestDeepSeekVLProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import DeepSeekVLProvider

        p = DeepSeekVLProvider()
        assert p.name == "deepseek_vl"
        assert p.model_id == "deepseek-ai/DeepSeek-VL2"
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "deepseek-ai/DeepSeek-VL2"

    def test_custom_params(self):
        from lab_manager.intake.providers.more_ocr import DeepSeekVLProvider

        p = DeepSeekVLProvider(base_url="http://gpu:9999/v1", model="custom-model")
        assert p.base_url == "http://gpu:9999/v1"
        assert p.model == "custom-model"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import DeepSeekVLProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = "VL OCR result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = DeepSeekVLProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == "VL OCR result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_jpeg(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import DeepSeekVLProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = "JPEG result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = DeepSeekVLProvider()
            result = p.extract_text("/tmp/test.jpg")
            assert result == "JPEG result"
            # Verify jpeg mime type was used
            call_args = mock_client.chat.completions.create.call_args
            content = call_args[1]["messages"][0]["content"]
            image_part = content[0]
            assert "image/jpeg" in image_part["image_url"]["url"]

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_none_content_returns_empty(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import DeepSeekVLProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            p = DeepSeekVLProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    def test_extract_text_error_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import DeepSeekVLProvider

        p = DeepSeekVLProvider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# GLMOCRProvider (lines 78-113)
# ---------------------------------------------------------------------------


class TestGLMOCRProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRProvider

        p = GLMOCRProvider()
        assert p.name == "glm_4v"
        assert p.model_id == "glm-5"
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "THUDM/glm-4v-9b"

    def test_custom_params(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRProvider

        p = GLMOCRProvider(base_url="http://custom:8000/v1", model="custom-glm")
        assert p.base_url == "http://custom:8000/v1"
        assert p.model == "custom-glm"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = "GLM OCR text"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = GLMOCRProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == "GLM OCR text"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_jpeg_mime(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = "GLM JPEG"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = GLMOCRProvider()
            result = p.extract_text("/tmp/test.jpeg")
            assert result == "GLM JPEG"
            call_args = mock_client.chat.completions.create.call_args
            content = call_args[1]["messages"][0]["content"]
            assert "image/jpeg" in content[0]["image_url"]["url"]

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_none_content_returns_empty(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            p = GLMOCRProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    def test_extract_text_error_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRProvider

        p = GLMOCRProvider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# GLM5NIMProvider edge cases (lines 185, 219-221)
# ---------------------------------------------------------------------------


class TestGLM5NIMProviderEdgeCases:
    @patch("httpx.post")
    def test_vision_returns_empty_text(self, mock_post):
        """Line 185: raw_ocr is empty/whitespace after vision step."""
        from lab_manager.intake.providers.more_ocr import GLM5NIMProvider

        vision_resp = MagicMock()
        vision_resp.json.return_value = {"choices": [{"message": {"content": "   "}}]}
        vision_resp.raise_for_status = MagicMock()
        mock_post.return_value = vision_resp

        p = GLM5NIMProvider(api_key="test-key")
        with patch("lab_manager.intake.providers.more_ocr.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"img"
            mock_path.return_value.suffix = ".png"
            result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("httpx.post")
    def test_vision_returns_no_content_key(self, mock_post):
        """Line 185: vision choices have no content."""
        from lab_manager.intake.providers.more_ocr import GLM5NIMProvider

        vision_resp = MagicMock()
        vision_resp.json.return_value = {"choices": [{"message": {}}]}
        vision_resp.raise_for_status = MagicMock()
        mock_post.return_value = vision_resp

        p = GLM5NIMProvider(api_key="test-key")
        with patch("lab_manager.intake.providers.more_ocr.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"img"
            mock_path.return_value.suffix = ".png"
            result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("httpx.post")
    def test_vision_returns_empty_choices(self, mock_post):
        """Line 185: empty choices list."""
        from lab_manager.intake.providers.more_ocr import GLM5NIMProvider

        vision_resp = MagicMock()
        vision_resp.json.return_value = {"choices": []}
        vision_resp.raise_for_status = MagicMock()
        mock_post.return_value = vision_resp

        p = GLM5NIMProvider(api_key="test-key")
        with patch("lab_manager.intake.providers.more_ocr.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"img"
            mock_path.return_value.suffix = ".png"
            result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("httpx.post")
    def test_refine_exception_returns_empty(self, mock_post):
        """Lines 219-221: exception during refine step."""
        from lab_manager.intake.providers.more_ocr import GLM5NIMProvider

        vision_resp = MagicMock()
        vision_resp.json.return_value = {
            "choices": [{"message": {"content": "Some raw OCR text"}}]
        }
        vision_resp.raise_for_status = MagicMock()

        # Second call (refine) raises exception
        mock_post.side_effect = [vision_resp, Exception("Refine API error")]

        p = GLM5NIMProvider(api_key="test-key")
        with patch("lab_manager.intake.providers.more_ocr.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"img"
            mock_path.return_value.suffix = ".png"
            result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("httpx.post")
    def test_vision_exception_returns_empty(self, mock_post):
        """Lines 219-221: exception during vision step."""
        from lab_manager.intake.providers.more_ocr import GLM5NIMProvider

        mock_post.side_effect = Exception("Vision API down")

        p = GLM5NIMProvider(api_key="test-key")
        with patch("lab_manager.intake.providers.more_ocr.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"img"
            mock_path.return_value.suffix = ".png"
            result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("httpx.post")
    def test_refine_empty_choices(self, mock_post):
        """Refine step returns empty choices."""
        from lab_manager.intake.providers.more_ocr import GLM5NIMProvider

        vision_resp = MagicMock()
        vision_resp.json.return_value = {
            "choices": [{"message": {"content": "Raw text"}}]
        }
        vision_resp.raise_for_status = MagicMock()

        refine_resp = MagicMock()
        refine_resp.json.return_value = {"choices": []}
        refine_resp.raise_for_status = MagicMock()

        mock_post.side_effect = [vision_resp, refine_resp]

        p = GLM5NIMProvider(api_key="test-key")
        with patch("lab_manager.intake.providers.more_ocr.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"img"
            mock_path.return_value.suffix = ".png"
            result = p.extract_text("/tmp/test.png")
        assert result == ""


# ---------------------------------------------------------------------------
# PaddleOCRProvider (lines 231-250)
# ---------------------------------------------------------------------------


class TestPaddleOCRProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRProvider

        p = PaddleOCRProvider()
        assert p.name == "paddleocr"
        assert p.lang == "en"
        assert p._ocr is None

    def test_custom_lang(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRProvider

        p = PaddleOCRProvider(lang="zh")
        assert p.lang == "zh"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRProvider

        mock_paddle = MagicMock()
        mock_paddle.ocr.return_value = [
            [
                [["box"], ("Hello world", 0.99)],
                [["box"], ("Second line", 0.95)],
            ]
        ]

        p = PaddleOCRProvider()
        p._ocr = mock_paddle

        result = p.extract_text("/tmp/test.png")
        assert result == "Hello world\nSecond line"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_none_page(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRProvider

        mock_paddle = MagicMock()
        mock_paddle.ocr.return_value = [None]

        p = PaddleOCRProvider()
        p._ocr = mock_paddle

        result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_short_line(self, mock_path_cls):
        """Line with len <= 1 falls back to str(line)."""
        from lab_manager.intake.providers.more_ocr import PaddleOCRProvider

        mock_paddle = MagicMock()
        mock_paddle.ocr.return_value = [
            [
                ["single_item"],
            ]
        ]

        p = PaddleOCRProvider()
        p._ocr = mock_paddle

        result = p.extract_text("/tmp/test.png")
        assert "single_item" in result

    def test_lazy_init_creates_paddleocr(self):
        """_get_ocr lazily initializes PaddleOCR (lines 236-238)."""
        from lab_manager.intake.providers.more_ocr import PaddleOCRProvider

        mock_paddle_instance = MagicMock()
        mock_paddle_cls = MagicMock(return_value=mock_paddle_instance)
        mock_module = MagicMock()
        mock_module.PaddleOCR = mock_paddle_cls

        p = PaddleOCRProvider(lang="zh")
        with patch.dict("sys.modules", {"paddleocr": mock_module}):
            ocr = p._get_ocr()
            assert ocr is mock_paddle_instance
            mock_paddle_cls.assert_called_once_with(
                use_angle_cls=True, lang="zh", show_log=False
            )

            # Second call returns cached instance
            ocr2 = p._get_ocr()
            assert ocr2 is mock_paddle_instance
            assert mock_paddle_cls.call_count == 1  # Not called again

    def test_get_ocr_returns_cached_instance(self):
        """When _ocr is already set, returns it without importing."""
        from lab_manager.intake.providers.more_ocr import PaddleOCRProvider

        mock_ocr = MagicMock()
        p = PaddleOCRProvider()
        p._ocr = mock_ocr
        assert p._get_ocr() is mock_ocr


# ---------------------------------------------------------------------------
# MistralOCRProvider (lines 262-296)
# ---------------------------------------------------------------------------


class TestMistralOCRProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import MistralOCRProvider

        p = MistralOCRProvider()
        assert p.name == "mistral_pixtral"
        assert p.model_id == "pixtral-large-latest"
        assert p.model == "pixtral-large-latest"
        assert p.api_key is None

    def test_custom_params(self):
        from lab_manager.intake.providers.more_ocr import MistralOCRProvider

        p = MistralOCRProvider(api_key="test-key", model="custom-model")
        assert p.api_key == "test-key"
        assert p.model == "custom-model"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import MistralOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = "Mistral Pixtral OCR text"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = MistralOCRProvider(api_key="test-key")
            result = p.extract_text("/tmp/test.png")
            assert result == "Mistral Pixtral OCR text"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_jpeg(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import MistralOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = "JPEG result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = MistralOCRProvider(api_key="test-key")
            result = p.extract_text("/tmp/test.jpg")
            assert result == "JPEG result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_none_content_returns_empty(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import MistralOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            p = MistralOCRProvider(api_key="test-key")
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_env_key(self, mock_path_cls):
        """Uses MISTRAL_API_KEY from env when no explicit key."""
        from lab_manager.intake.providers.more_ocr import MistralOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_msg = MagicMock()
        mock_msg.content = "Env key result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with (
            patch("openai.OpenAI") as mock_openai,
            patch.dict("os.environ", {"MISTRAL_API_KEY": "env-key"}),
        ):
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = MistralOCRProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == "Env key result"


# ---------------------------------------------------------------------------
# ClaudeOCRProvider (lines 306-326)
# ---------------------------------------------------------------------------


class TestClaudeOCRProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import ClaudeOCRProvider

        p = ClaudeOCRProvider()
        assert p.name == "claude_sonnet"
        assert p.model_id == "claude-sonnet-4-6"
        assert p.timeout == 120

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_success(self, mock_run):
        from lab_manager.intake.providers.more_ocr import ClaudeOCRProvider

        mock_run.return_value = MagicMock(returncode=0, stdout="  Claude OCR result  ")

        p = ClaudeOCRProvider()
        result = p.extract_text("/tmp/test.png")
        assert result == "Claude OCR result"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "claude"
        assert "--output-format" in cmd

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_nonzero_return(self, mock_run):
        from lab_manager.intake.providers.more_ocr import ClaudeOCRProvider

        mock_run.return_value = MagicMock(returncode=1, stdout="error")

        p = ClaudeOCRProvider()
        result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_timeout_returns_empty(self, mock_run):
        from lab_manager.intake.providers.more_ocr import ClaudeOCRProvider

        mock_run.side_effect = subprocess.TimeoutExpired("claude", 120)

        p = ClaudeOCRProvider()
        result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_exception_returns_empty(self, mock_run):
        from lab_manager.intake.providers.more_ocr import ClaudeOCRProvider

        mock_run.side_effect = OSError("command not found")

        p = ClaudeOCRProvider()
        result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_env_model_override(self, mock_run):
        from lab_manager.intake.providers.more_ocr import ClaudeOCRProvider

        mock_run.return_value = MagicMock(returncode=0, stdout="result")

        p = ClaudeOCRProvider()
        p.extract_text("/tmp/test.png")

        env_arg = mock_run.call_args[1]["env"]
        assert env_arg["CLAUDE_MODEL"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# CodexOCRProvider (lines 336-353)
# ---------------------------------------------------------------------------


class TestCodexOCRProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import CodexOCRProvider

        p = CodexOCRProvider()
        assert p.name == "codex_gpt"
        assert p.model_id == "gpt-5.4"
        assert p.timeout == 120

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_success(self, mock_run):
        from lab_manager.intake.providers.more_ocr import CodexOCRProvider

        mock_run.return_value = MagicMock(returncode=0, stdout="  Codex OCR result  ")

        p = CodexOCRProvider()
        result = p.extract_text("/tmp/test.png")
        assert result == "Codex OCR result"
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "codex"
        assert "-m" in cmd
        assert "gpt-5.4" in cmd

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_nonzero_return(self, mock_run):
        from lab_manager.intake.providers.more_ocr import CodexOCRProvider

        mock_run.return_value = MagicMock(returncode=1, stdout="")

        p = CodexOCRProvider()
        result = p.extract_text("/tmp/test.png")
        assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.subprocess.run")
    def test_extract_text_exception_returns_empty(self, mock_run):
        from lab_manager.intake.providers.more_ocr import CodexOCRProvider

        mock_run.side_effect = Exception("timeout")

        p = CodexOCRProvider()
        result = p.extract_text("/tmp/test.png")
        assert result == ""


# ---------------------------------------------------------------------------
# DotsMOCRProvider (lines 387-407)
# ---------------------------------------------------------------------------


class TestDotsMOCRProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        p = DotsMOCRProvider()
        assert p.name == "dots_mocr"
        assert p.model_id == "rednote-hilab/dots.mocr"
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "rednote-hilab/dots.mocr"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock()
        mock_msg.content = "dots.mocr result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = DotsMOCRProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == "dots.mocr result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_jpeg(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".jpg"
        mock_msg = MagicMock()
        mock_msg.content = "JPEG result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = DotsMOCRProvider()
            result = p.extract_text("/tmp/test.jpg")
            assert result == "JPEG result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_no_content_attr(self, mock_path_cls):
        """getattr returns empty string when content is missing."""
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock(spec=[])
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            p = DotsMOCRProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    def test_extract_text_error_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        p = DotsMOCRProvider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# GLMOCRDedicatedProvider vLLM mode (lines 451-471)
# ---------------------------------------------------------------------------


class TestGLMOCRDedicatedProviderVLLM:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        p = GLMOCRDedicatedProvider()
        assert p.name == "glm_ocr_09b"
        assert p.mode == "vllm"
        assert p.base_url == "http://localhost:8000/v1"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_vllm_extract_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock()
        mock_msg.content = "GLM-OCR vLLM result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = GLMOCRDedicatedProvider(mode="vllm")
            result = p.extract_text("/tmp/test.png")
            assert result == "GLM-OCR vLLM result"

    def test_vllm_extract_error_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        p = GLMOCRDedicatedProvider(base_url="http://nonexistent:9999/v1", mode="vllm")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# GLMOCRDedicatedProvider API mode (lines 477-519)
# ---------------------------------------------------------------------------


class TestGLMOCRDedicatedProviderAPI:
    def test_no_api_key_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        with patch.dict(
            "os.environ", {"ZAI_API_KEY": "", "ZHIPU_API_KEY": ""}, clear=False
        ):
            p = GLMOCRDedicatedProvider(mode="api", api_key="")
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_api_extract_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock()
        mock_msg.content = "GLM-OCR API result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = GLMOCRDedicatedProvider(mode="api", api_key="test-key")
            result = p.extract_text("/tmp/test.png")
            assert result == "GLM-OCR API result"

            # Verify it uses the correct API base and model
            mock_openai.assert_called_once_with(
                base_url="https://open.bigmodel.cn/api/paas/v4",
                api_key="test-key",
            )
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "glm-ocr"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_api_uses_env_key(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock()
        mock_msg.content = "env key result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with (
            patch("openai.OpenAI") as mock_openai,
            patch.dict("os.environ", {"ZAI_API_KEY": "env-zai-key"}),
        ):
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = GLMOCRDedicatedProvider(mode="api")
            result = p.extract_text("/tmp/test.png")
            assert result == "env key result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_api_no_content_returns_empty(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock(spec=[])
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            p = GLMOCRDedicatedProvider(mode="api", api_key="test-key")
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_api_error_returns_empty(self, mock_path_cls):
        """Lines 517-519: API exception handler."""
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img"
        mock_path_cls.return_value.suffix = ".png"

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.side_effect = Exception("API connection failed")

            p = GLMOCRDedicatedProvider(mode="api", api_key="test-key")
            result = p.extract_text("/tmp/test.png")
            assert result == ""


# ---------------------------------------------------------------------------
# PaddleOCRVL15Provider (lines 537-570)
# ---------------------------------------------------------------------------


class TestPaddleOCRVL15Provider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVL15Provider

        p = PaddleOCRVL15Provider()
        assert p.name == "paddleocr_vl_15"
        assert p.model_id == "PaddlePaddle/PaddleOCR-VL-1.5"
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "PaddlePaddle/PaddleOCR-VL-1.5"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVL15Provider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock()
        mock_msg.content = "PaddleOCR-VL 1.5 result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = PaddleOCRVL15Provider()
            result = p.extract_text("/tmp/test.png")
            assert result == "PaddleOCR-VL 1.5 result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_jpeg(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVL15Provider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".jpg"
        mock_msg = MagicMock()
        mock_msg.content = "JPEG result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = PaddleOCRVL15Provider()
            result = p.extract_text("/tmp/test.jpg")
            assert result == "JPEG result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_no_content_returns_empty(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVL15Provider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock(spec=[])
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            p = PaddleOCRVL15Provider()
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    def test_extract_text_error_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVL15Provider

        p = PaddleOCRVL15Provider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# PaddleOCRVLProvider extract_text (lines 650-669)
# ---------------------------------------------------------------------------


class TestPaddleOCRVLProviderExtractText:
    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVLProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock()
        mock_msg.content = "PaddleOCR-VL result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = PaddleOCRVLProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == "PaddleOCR-VL result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_jpeg(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVLProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".jpg"
        mock_msg = MagicMock()
        mock_msg.content = "JPEG result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = PaddleOCRVLProvider()
            result = p.extract_text("/tmp/test.jpg")
            assert result == "JPEG result"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_no_content_returns_empty(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVLProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock(spec=[])
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            p = PaddleOCRVLProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_empty_content_returns_empty(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVLProvider

        mock_path_cls.return_value.read_bytes.return_value = b"img-data"
        mock_path_cls.return_value.suffix = ".png"
        mock_msg = MagicMock()
        mock_msg.content = ""
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            p = PaddleOCRVLProvider()
            result = p.extract_text("/tmp/test.png")
            # content="" is falsy, or "" returns ""
            assert result == ""

    def test_extract_text_error_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVLProvider

        p = PaddleOCRVLProvider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# get_provider with custom registry
# ---------------------------------------------------------------------------


class TestGetProviderCustomRegistry:
    def test_vlm_provider(self):
        """get_provider works with VLM_PROVIDERS."""
        from lab_manager.intake.providers.more_ocr import VLM_PROVIDERS

        # Can't actually instantiate (missing CLI tools), but verify it's in registry
        assert "opus_4_6" in VLM_PROVIDERS
        assert "gemini_3_1_pro" in VLM_PROVIDERS
        assert "gpt_5_4" in VLM_PROVIDERS

    def test_combined_registry_fallback(self):
        """When no registry passed, uses combined OCR + VLM registries."""
        from lab_manager.intake.providers.more_ocr import get_provider

        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent_vlm")


# ---------------------------------------------------------------------------
# Provider registration completeness
# ---------------------------------------------------------------------------


class TestProviderRegistration:
    def test_all_providers_in_registry(self):
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        expected = [
            "dots_mocr",
            "glm_ocr_09b",
            "paddleocr_vl_15",
            "deepseek_ocr",
            "paddleocr_vl",
            "deepseek_vl",
            "glm_4v",
            "paddleocr",
            "glm5_nim",
            "mistral_ocr3",
            "mistral_pixtral",
            "claude_sonnet",
            "codex_gpt",
        ]
        for name in expected:
            assert name in OCR_PROVIDERS, f"Missing: {name}"

    def test_all_local_providers_listed(self):
        """Verify local models are in the correct order in registry."""
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        local_keys = list(OCR_PROVIDERS.keys())[:6]  # first 6 are local
        assert "dots_mocr" in local_keys
        assert "glm_ocr_09b" in local_keys
        assert "paddleocr_vl_15" in local_keys
