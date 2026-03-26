"""Claude Code CLI provider (Opus 4.6)."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from typing import Optional

from . import VLMProvider

log = logging.getLogger(__name__)


class ClaudeProvider(VLMProvider):
    """Uses Claude Code CLI to run Opus 4.6 on images."""

    name = "opus_4_6"
    model_id = "claude-opus-4-6"

    def __init__(self, model: str = "claude-opus-4-6", timeout: int = 180):
        self.model = model
        self.timeout = timeout

    def extract_from_image(self, image_path: str, prompt: str) -> Optional[str]:
        safe_path = shlex.quote(str(image_path))
        full_prompt = (
            f"Read the image at {safe_path} and follow these instructions:\n\n{prompt}"
        )
        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, "CLAUDE_MODEL": self.model},
            )
            if result.returncode == 0:
                return result.stdout.strip()
            log.warning(
                "Claude failed (rc=%d): %s", result.returncode, result.stderr[:200]
            )
            return None
        except subprocess.TimeoutExpired:
            log.warning("Claude timed out (%ds) for %s", self.timeout, image_path)
            return None
        except Exception as e:
            log.warning("Claude error: %s", e)
            return None
