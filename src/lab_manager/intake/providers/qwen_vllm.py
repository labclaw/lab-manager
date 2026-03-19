"""Qwen3-VL OCR via local vLLM server."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from . import OCRProvider

log = logging.getLogger(__name__)

DEFAULT_VLLM_URL = "http://localhost:8000/v1"


class QwenVLLMProvider(OCRProvider):
    """Local Qwen3-VL via vLLM OpenAI-compatible endpoint."""

    name = "qwen3_vl"
    model_id = "Qwen/Qwen3-VL-4B-Instruct"

    def __init__(
        self,
        model: str = "Qwen/Qwen3-VL-4B-Instruct",
        base_url: str = DEFAULT_VLLM_URL,
    ):
        self.model = model
        self.base_url = base_url

    def extract_text(self, image_path: str) -> str:
        from openai import OpenAI

        client = OpenAI(base_url=self.base_url, api_key="dummy")

        image_bytes = Path(image_path).read_bytes()
        b64 = base64.b64encode(image_bytes).decode()
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
                },
            ],
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""


class GeminiOCRProvider(OCRProvider):
    """Gemini 3.1 Flash via CLI for fast OCR."""

    name = "gemini_3_1_flash"
    model_id = "gemini-3.1-flash-preview"

    def __init__(self, model: str = "gemini-3.1-flash-preview", timeout: int = 60):
        self.model = model
        self.timeout = timeout

    def extract_text(self, image_path: str) -> str:
        import subprocess

        prompt = f"Look at the image file {image_path} and follow these instructions:\n\n{OCR_PROMPT}"
        try:
            result = subprocess.run(
                ["gemini", "-p", prompt, "-m", self.model],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            log.warning("Gemini OCR failed: %s", result.stderr[:200])
            return ""
        except Exception as e:
            log.warning("Gemini OCR error: %s", e)
            return ""


class GeminiAPIOCRProvider(OCRProvider):
    """Gemini 3.1 Flash via Google GenAI API for OCR."""

    name = "gemini_api_flash"
    model_id = "gemini-3.1-flash-preview"

    def __init__(self, model: str = "gemini-3.1-flash-preview", api_key: str | None = None):
        self.model = model
        self.api_key = api_key

    def extract_text(self, image_path: str) -> str:
        import base64

        from google import genai

        api_key = self.api_key
        if not api_key:
            import os

            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("EXTRACTION_API_KEY", "")

        client = genai.Client(api_key=api_key)
        image_bytes = Path(image_path).read_bytes()
        b64 = base64.b64encode(image_bytes).decode()
        suffix = Path(image_path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"

        response = client.models.generate_content(
            model=self.model,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime, "data": b64}},
                        {"text": OCR_PROMPT},
                    ],
                },
            ],
        )
        return response.text


OCR_PROMPT = """You are performing OCR on a scanned lab supply document.
Transcribe ALL visible text faithfully, character by character.

Critical rules:
- Output plain text only. Preserve reading order top-to-bottom, left-to-right.
- Keep line breaks where they appear on the document.
- Pay extra attention to:
  * Catalog/part numbers (e.g., AB2251-1, MAB5406) — distinguish 1 vs I, 0 vs O
  * Batch/lot numbers — include ALL, even partially visible
  * Handwritten text and dates — transcribe exactly as written
  * PO numbers, delivery numbers, order numbers
- Include ALL text: fine print, footer, handwritten annotations.
- Do NOT summarize, explain, or skip any text region.
"""
