"""Additional OCR providers for benchmarking.

Add new OCR models here. Each just needs to implement extract_text(image_path) -> str.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from . import OCRProvider
from lab_manager.intake.prompts import OCR_PROMPT

log = logging.getLogger(__name__)


class DeepSeekVLProvider(OCRProvider):
    """DeepSeek-VL via vLLM or API."""

    name = "deepseek_vl"
    model_id = "deepseek-ai/DeepSeek-VL2"

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "deepseek-ai/DeepSeek-VL2",
    ):
        self.base_url = base_url
        self.model = model

    def extract_text(self, image_path: str) -> str:
        import base64
        from openai import OpenAI

        try:
            client = OpenAI(base_url=self.base_url, api_key="dummy")
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            mime = (
                "image/jpeg"
                if image_path.lower().endswith((".jpg", ".jpeg"))
                else "image/png"
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                            {"type": "text", "text": OCR_PROMPT},
                        ],
                    }
                ],
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            log.warning("DeepSeek OCR error: %s", e)
            return ""


class GLMOCRProvider(OCRProvider):
    """GLM-4V / CogVLM via vLLM or Z.ai API."""

    name = "glm_4v"
    model_id = "glm-5"

    def __init__(
        self, base_url: str = "http://localhost:8000/v1", model: str = "THUDM/glm-4v-9b"
    ):
        self.base_url = base_url
        self.model = model

    def extract_text(self, image_path: str) -> str:
        import base64
        from openai import OpenAI

        try:
            client = OpenAI(base_url=self.base_url, api_key="dummy")
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            mime = (
                "image/jpeg"
                if image_path.lower().endswith((".jpg", ".jpeg"))
                else "image/png"
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                            {"type": "text", "text": OCR_PROMPT},
                        ],
                    }
                ],
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            log.warning("GLM OCR error: %s", e)
            return ""


class PaddleOCRProvider(OCRProvider):
    """PaddleOCR (local, no GPU required for inference)."""

    name = "paddleocr"
    model_id = "PaddlePaddle/PaddleOCR"

    def __init__(self, lang: str = "en"):
        self.lang = lang
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=True, lang=self.lang, show_log=False)
        return self._ocr

    def extract_text(self, image_path: str) -> str:
        ocr = self._get_ocr()
        result = ocr.ocr(image_path, cls=True)
        lines = []
        for page in result:
            if page:
                for line in page:
                    text = line[1][0] if len(line) > 1 else str(line)
                    lines.append(text)
        return "\n".join(lines)


class MistralOCRProvider(OCRProvider):
    """Mistral Pixtral via API."""

    name = "mistral_pixtral"
    model_id = "pixtral-large-latest"

    def __init__(
        self, api_key: Optional[str] = None, model: str = "pixtral-large-latest"
    ):
        self.model = model
        self.api_key = api_key

    def extract_text(self, image_path: str) -> str:
        import base64
        import os
        from openai import OpenAI

        api_key = self.api_key or os.environ.get("MISTRAL_API_KEY", "")
        client = OpenAI(base_url="https://api.mistral.ai/v1", api_key=api_key)

        b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        mime = (
            "image/jpeg"
            if image_path.lower().endswith((".jpg", ".jpeg"))
            else "image/png"
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                        {"type": "text", "text": OCR_PROMPT},
                    ],
                }
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""


class ClaudeOCRProvider(OCRProvider):
    """Claude Sonnet 4.6 via CLI for OCR."""

    name = "claude_sonnet"
    model_id = "claude-sonnet-4-6"

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def extract_text(self, image_path: str) -> str:
        import os

        prompt = f"Read the image at {image_path} and follow these instructions:\n\n{OCR_PROMPT}"
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, "CLAUDE_MODEL": "claude-sonnet-4-6"},
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return ""
        except Exception as e:
            log.warning("Claude OCR error: %s", e)
            return ""


class CodexOCRProvider(OCRProvider):
    """GPT-5.4 via Codex CLI for OCR."""

    name = "codex_gpt"
    model_id = "gpt-5.4"

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def extract_text(self, image_path: str) -> str:
        prompt = f"Look at the image file {image_path} and follow these instructions:\n\n{OCR_PROMPT}"
        try:
            result = subprocess.run(
                ["codex", "-p", prompt, "-m", "gpt-5.4", "--quiet"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return ""
        except Exception as e:
            log.warning("Codex OCR error: %s", e)
            return ""


# Registry of all available OCR providers
OCR_PROVIDERS = {
    "qwen3_vl": "lab_manager.intake.providers.qwen_vllm:QwenVLLMProvider",
    "gemini_flash": "lab_manager.intake.providers.qwen_vllm:GeminiOCRProvider",
    "gemini_api": "lab_manager.intake.providers.qwen_vllm:GeminiAPIOCRProvider",
    "deepseek_vl": "lab_manager.intake.providers.more_ocr:DeepSeekVLProvider",
    "glm_4v": "lab_manager.intake.providers.more_ocr:GLMOCRProvider",
    "paddleocr": "lab_manager.intake.providers.more_ocr:PaddleOCRProvider",
    "mistral_pixtral": "lab_manager.intake.providers.more_ocr:MistralOCRProvider",
    "claude_sonnet": "lab_manager.intake.providers.more_ocr:ClaudeOCRProvider",
    "codex_gpt": "lab_manager.intake.providers.more_ocr:CodexOCRProvider",
}

# Registry of all available VLM providers (for extraction/review)
VLM_PROVIDERS = {
    "opus_4_6": "lab_manager.intake.providers.claude:ClaudeProvider",
    "gemini_3_1_pro": "lab_manager.intake.providers.gemini:GeminiProvider",
    "gpt_5_4": "lab_manager.intake.providers.codex:CodexProvider",
}


def get_provider(name: str, registry: dict = None):
    """Instantiate a provider by name from registry."""
    reg = registry or {**OCR_PROVIDERS, **VLM_PROVIDERS}
    if name not in reg:
        raise ValueError(f"Unknown provider: {name}. Available: {list(reg.keys())}")
    module_path, class_name = reg[name].rsplit(":", 1)
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()
