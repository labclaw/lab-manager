"""VLM provider abstraction — swap models by changing provider class."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

log = logging.getLogger(__name__)


class VLMProvider(ABC):
    """Base class for all VLM providers.

    To add a new model, subclass and implement extract_from_image() and review().
    """

    name: str = "base"
    model_id: str = "unknown"

    @abstractmethod
    def extract_from_image(self, image_path: str, prompt: str) -> Optional[str]:
        """Send image + prompt to model, return raw text response."""
        ...

    def extract(self, image_path: str, prompt: str) -> Optional[dict]:
        """Extract structured JSON from image. Handles parsing."""
        raw = self.extract_from_image(image_path, prompt)
        return parse_json_response(raw) if raw else None

    def review(self, image_path: str, prompt: str) -> Optional[dict]:
        """Review an extraction. Same as extract by default."""
        return self.extract(image_path, prompt)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_id})"


class OCRProvider(ABC):
    """Base class for OCR providers."""

    name: str = "base_ocr"
    model_id: str = "unknown"

    @abstractmethod
    def extract_text(self, image_path: str) -> str:
        """Extract raw text from image."""
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_id})"


def parse_json_response(text: str) -> Optional[dict]:
    """Parse JSON from model response, handling markdown fences."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Strip only the opening (```json) and closing (```) fence lines
        if lines and lines[-1].strip() == "```":
            lines = lines[1:-1]
        elif lines:
            lines = lines[1:]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
    log.warning("Failed to parse JSON: %s...", text[:100])
    return None
