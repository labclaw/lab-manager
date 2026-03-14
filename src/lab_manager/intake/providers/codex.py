"""Codex CLI provider (GPT-5.4)."""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

from . import VLMProvider

log = logging.getLogger(__name__)


class CodexProvider(VLMProvider):
    """Uses Codex CLI to run GPT-5.4 on images."""

    name = "gpt_5_4"
    model_id = "gpt-5.4"

    def __init__(self, model: str = "gpt-5.4", timeout: int = 180):
        self.model = model
        self.timeout = timeout

    def extract_from_image(self, image_path: str, prompt: str) -> Optional[str]:
        full_prompt = f"Look at the image file {image_path} and follow these instructions:\n\n{prompt}"
        try:
            result = subprocess.run(
                ["codex", "-p", full_prompt, "-m", self.model, "--quiet"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            log.warning(
                "Codex failed (rc=%d): %s", result.returncode, result.stderr[:200]
            )
            return None
        except subprocess.TimeoutExpired:
            log.warning("Codex timed out (%ds) for %s", self.timeout, image_path)
            return None
        except Exception as e:
            log.warning("Codex error: %s", e)
            return None
