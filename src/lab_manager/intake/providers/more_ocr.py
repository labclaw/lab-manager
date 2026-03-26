"""Additional OCR providers for benchmarking.

Add new OCR models here. Each just needs to implement extract_text(image_path) -> str.
"""

from __future__ import annotations

import logging
import shlex
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


class GLM5NIMProvider(OCRProvider):
    """GLM-5 via NVIDIA NIM API (free tier).

    Uses NVIDIA NIM endpoint for GLM-5 text model. Since GLM-5 on NIM is text-only,
    this provider does a two-step OCR: first uses NVIDIA vision model to extract
    raw text, then uses GLM-5 to clean and structure the OCR output.
    For direct vision OCR, use GLMOCRProvider with a local vLLM server instead.
    """

    name = "glm5_nim"
    model_id = "z-ai/glm5"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def extract_text(self, image_path: str) -> str:
        import base64
        import os

        import httpx

        api_key = (
            self.api_key
            or os.environ.get("NVIDIA_BUILD_API_KEY", "")
            or os.environ.get("NVIDIA_API_KEY", "")
        )
        if not api_key:
            log.warning("No NVIDIA API key for GLM-5 NIM")
            return ""

        try:
            # Step 1: Vision OCR via NVIDIA Llama-3.2-90b-vision
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            suffix = Path(image_path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

            vision_resp = httpx.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "meta/llama-3.2-90b-vision-instruct",
                    "messages": [
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
                    "max_tokens": 4096,
                    "temperature": 0.1,
                },
                timeout=120,
            )
            vision_resp.raise_for_status()
            v_data = vision_resp.json()
            v_choices = v_data.get("choices") or []
            raw_ocr = (
                v_choices[0].get("message", {}).get("content", "") if v_choices else ""
            )

            if not raw_ocr.strip():
                return ""

            # Step 2: GLM-5 refines the OCR text
            refine_resp = httpx.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "z-ai/glm5",
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Clean up and organize this raw OCR text from a lab document. "
                                "Fix obvious OCR errors, preserve all numbers/codes exactly, "
                                "output clean plain text only:\n\n" + raw_ocr
                            ),
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.1,
                },
                timeout=60,
            )
            refine_resp.raise_for_status()
            r_data = refine_resp.json()
            r_choices = r_data.get("choices") or []
            return (
                r_choices[0].get("message", {}).get("content", "").strip()
                if r_choices
                else ""
            )
        except Exception as e:
            log.warning("GLM-5 NIM OCR error: %s", e)
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

        safe_path = shlex.quote(str(image_path))
        prompt = f"Read the image at {safe_path} and follow these instructions:\n\n{OCR_PROMPT}"
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
        safe_path = shlex.quote(str(image_path))
        prompt = f"Look at the image file {safe_path} and follow these instructions:\n\n{OCR_PROMPT}"
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


# ---------------------------------------------------------------------------
# Local OCR models (designed for initial detection / fast pre-screening)
# ---------------------------------------------------------------------------


class DotsMOCRProvider(OCRProvider):
    """dots.mocr 3B — open-source Elo #1 (1124.7) on OmniDocBench.

    From Rednote HiLab. MIT license. Native vLLM support.
    3B params, ~6GB VRAM, document-aware OCR with layout understanding.
    vLLM: vllm serve rednote-hilab/dots.mocr --tensor-parallel-size 1
    """

    name = "dots_mocr"
    model_id = "rednote-hilab/dots.mocr"

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "rednote-hilab/dots.mocr",
    ):
        self.base_url = base_url
        self.model = model

    def extract_text(self, image_path: str) -> str:
        import base64

        from openai import OpenAI

        try:
            client = OpenAI(base_url=self.base_url, api_key="dummy")
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            suffix = Path(image_path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

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
            return getattr(response.choices[0].message, "content", "") or ""
        except Exception as e:
            log.warning("dots.mocr error: %s", e)
            return ""


class GLMOCRDedicatedProvider(OCRProvider):
    """GLM-OCR 0.9B — fast lightweight OCR fallback.

    Ultra-lightweight dedicated OCR model from Z.ai. Supports:
    - Local mode: transformers AutoModelForCausalLM + AutoProcessor
    - API mode: Z.ai API (same endpoint as GLM-5) with model="glm-ocr"
    - vLLM mode: OpenAI-compatible endpoint

    0.9B params, ~2GB VRAM, sub-second per page.
    """

    name = "glm_ocr_09b"
    model_id = "zai-org/GLM-OCR"

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "zai-org/GLM-OCR",
        mode: str = "vllm",
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url
        self.model = model
        self.mode = mode
        self.api_key = api_key

    def extract_text(self, image_path: str) -> str:
        if self.mode == "api":
            return self._extract_api(image_path)
        return self._extract_vllm(image_path)

    def _extract_vllm(self, image_path: str) -> str:
        import base64

        from openai import OpenAI

        try:
            client = OpenAI(base_url=self.base_url, api_key="dummy")
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            suffix = Path(image_path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

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
            return getattr(response.choices[0].message, "content", "") or ""
        except Exception as e:
            log.warning("GLM-OCR 0.9B vLLM error: %s", e)
            return ""

    def _extract_api(self, image_path: str) -> str:
        import base64
        import os

        from openai import OpenAI

        api_key = (
            self.api_key
            or os.environ.get("ZAI_API_KEY", "")
            or os.environ.get("ZHIPU_API_KEY", "")
        )
        if not api_key:
            log.warning("No Z.ai API key for GLM-OCR")
            return ""

        try:
            client = OpenAI(
                base_url="https://open.bigmodel.cn/api/paas/v4",
                api_key=api_key,
            )
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            suffix = Path(image_path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

            response = client.chat.completions.create(
                model="glm-ocr",
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
            return getattr(response.choices[0].message, "content", "") or ""
        except Exception as e:
            log.warning("GLM-OCR API error: %s", e)
            return ""


class PaddleOCRVL15Provider(OCRProvider):
    """PaddleOCR-VL 1.5 via vLLM OpenAI-compatible endpoint.

    Upgraded from PaddleOCR-VL (0.9B). Better accuracy on complex layouts.
    109 languages, document-aware layout understanding.
    """

    name = "paddleocr_vl_15"
    model_id = "PaddlePaddle/PaddleOCR-VL-1.5"

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "PaddlePaddle/PaddleOCR-VL-1.5",
    ):
        self.base_url = base_url
        self.model = model

    def extract_text(self, image_path: str) -> str:
        import base64

        from openai import OpenAI

        try:
            client = OpenAI(base_url=self.base_url, api_key="dummy")
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            suffix = Path(image_path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

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
            return getattr(response.choices[0].message, "content", "") or ""
        except Exception as e:
            log.warning("PaddleOCR-VL 1.5 error: %s", e)
            return ""


class DeepSeekOCRProvider(OCRProvider):
    """DeepSeek-OCR 3B via vLLM OpenAI-compatible endpoint.

    Dedicated OCR model (different from DeepSeek-VL2 general VLM).
    ~16GB VRAM, 0.1-0.4 sec/page, supports context compression.
    """

    name = "deepseek_ocr"
    model_id = "deepseek-ai/DeepSeek-OCR"

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "deepseek-ai/DeepSeek-OCR",
    ):
        self.base_url = base_url
        self.model = model

    def extract_text(self, image_path: str) -> str:
        import base64

        from openai import OpenAI

        try:
            client = OpenAI(base_url=self.base_url, api_key="dummy")
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            suffix = Path(image_path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

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
            return getattr(response.choices[0].message, "content", "") or ""
        except Exception as e:
            log.warning("DeepSeek-OCR error: %s", e)
            return ""


class PaddleOCRVLProvider(OCRProvider):
    """PaddleOCR-VL 0.9B via vLLM OpenAI-compatible endpoint.

    Ultra-lightweight (0.9B params, ~2-3GB VRAM), fastest local OCR.
    109 languages, document-aware layout understanding.
    """

    name = "paddleocr_vl"
    model_id = "PaddlePaddle/PaddleOCR-VL"

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "PaddlePaddle/PaddleOCR-VL",
    ):
        self.base_url = base_url
        self.model = model

    def extract_text(self, image_path: str) -> str:
        import base64

        from openai import OpenAI

        try:
            client = OpenAI(base_url=self.base_url, api_key="dummy")
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            suffix = Path(image_path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

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
            return getattr(response.choices[0].message, "content", "") or ""
        except Exception as e:
            log.warning("PaddleOCR-VL error: %s", e)
            return ""


class MistralOCR3Provider(OCRProvider):
    """Mistral OCR 3 via dedicated /v1/ocr API endpoint.

    $2/1k pages, 96.6% table accuracy, 88.9% handwriting accuracy.
    Uses dedicated OCR endpoint (not chat completions like MistralOCRProvider).
    """

    name = "mistral_ocr3"
    model_id = "mistral-ocr-latest"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "mistral-ocr-latest",
    ):
        self.model = model
        self.api_key = api_key

    def extract_text(self, image_path: str) -> str:
        import base64
        import os

        import httpx

        api_key = self.api_key or os.environ.get("MISTRAL_API_KEY", "")
        if not api_key:
            log.warning("No MISTRAL_API_KEY configured for Mistral OCR 3")
            return ""

        try:
            b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            suffix = Path(image_path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

            resp = httpx.post(
                "https://api.mistral.ai/v1/ocr",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "document": {
                        "type": "image_url",
                        "image_url": f"data:{mime};base64,{b64}",
                    },
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("pages", [])
            return "\n\n".join(page.get("markdown", "") for page in pages).strip()
        except Exception as e:
            log.warning("Mistral OCR 3 error: %s", e)
            return ""


# Registry of all available OCR providers
OCR_PROVIDERS = {
    # Local models (fast initial detection, no API cost)
    # Default: dots.mocr 3B — open-source Elo #1 (1124.7)
    "dots_mocr": "lab_manager.intake.providers.more_ocr:DotsMOCRProvider",
    "glm_ocr_09b": "lab_manager.intake.providers.more_ocr:GLMOCRDedicatedProvider",
    "paddleocr_vl_15": "lab_manager.intake.providers.more_ocr:PaddleOCRVL15Provider",
    "deepseek_ocr": "lab_manager.intake.providers.more_ocr:DeepSeekOCRProvider",
    "paddleocr_vl": "lab_manager.intake.providers.more_ocr:PaddleOCRVLProvider",
    "qwen3_vl": "lab_manager.intake.providers.qwen_vllm:QwenVLLMProvider",
    "deepseek_vl": "lab_manager.intake.providers.more_ocr:DeepSeekVLProvider",
    "glm_4v": "lab_manager.intake.providers.more_ocr:GLMOCRProvider",
    "paddleocr": "lab_manager.intake.providers.more_ocr:PaddleOCRProvider",
    # API providers (free tier available)
    "glm5_nim": "lab_manager.intake.providers.more_ocr:GLM5NIMProvider",
    "mistral_ocr3": "lab_manager.intake.providers.more_ocr:MistralOCR3Provider",
    "mistral_pixtral": "lab_manager.intake.providers.more_ocr:MistralOCRProvider",
    "gemini_flash": "lab_manager.intake.providers.qwen_vllm:GeminiOCRProvider",
    "gemini_api": "lab_manager.intake.providers.qwen_vllm:GeminiAPIOCRProvider",
    # Premium (CLI-based, expensive)
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
