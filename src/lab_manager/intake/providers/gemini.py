"""Gemini CLI provider (3.1 Pro)."""

from __future__ import annotations

import logging
import subprocess

from . import VLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(VLMProvider):
    """Uses Gemini CLI to run Gemini 3.1 Pro on images."""

    name = "gemini_3_1_pro"
    model_id = "gemini-3.1-pro-preview"

    def __init__(self, model: str = "gemini-3.1-pro-preview", timeout: int = 180):
        self.model = model
        self.timeout = timeout

    def extract_from_image(self, image_path: str, prompt: str) -> str | None:
        full_prompt = f"Look at the image file {image_path} and follow these instructions:\n\n{prompt}"
        try:
            result = subprocess.run(
                ["gemini", "-p", full_prompt, "-m", self.model],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            log.warning(
                "Gemini failed (rc=%d): %s", result.returncode, result.stderr[:200]
            )
            return None
        except subprocess.TimeoutExpired:
            log.warning("Gemini timed out (%ds) for %s", self.timeout, image_path)
            return None
        except Exception as e:
            log.warning("Gemini error: %s", e)
            return None
