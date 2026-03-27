"""Ginkgo AI Model API routes — protein/DNA sequence analysis."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lab_manager.services import ginkgo_ai

router = APIRouter()


class AnalyzeRequest(BaseModel):
    sequence: str = Field(..., min_length=1, max_length=10000)
    model: str = "ginkgo-aa0-650M"
    analysis_type: str = "masked_inference"


class BatchAnalyzeRequest(BaseModel):
    sequences: list[str] = Field(..., min_length=1, max_length=100)
    model: str = "ginkgo-aa0-650M"
    analysis_type: str = "masked_inference"


@router.get("/models")
def list_models() -> list[dict[str, str]]:
    """List available Ginkgo AI models."""
    return ginkgo_ai.list_models()


@router.post("/analyze")
def analyze_sequence(body: AnalyzeRequest) -> dict[str, Any]:
    """Analyze a protein or DNA sequence using a Ginkgo AI model."""
    result = ginkgo_ai.analyze_sequence(body.sequence, body.model, body.analysis_type)
    if not result:
        return {"error": "Analysis failed — check API key and model availability"}
    return result


@router.post("/batch-analyze")
def batch_analyze(body: BatchAnalyzeRequest) -> list[dict[str, Any]]:
    """Analyze multiple sequences in a batch request."""
    return ginkgo_ai.batch_analyze(body.sequences, body.model, body.analysis_type)


@router.get("/health")
def health_check() -> dict[str, Any]:
    """Check Ginkgo AI API connectivity and configuration."""
    return ginkgo_ai.health_check()
