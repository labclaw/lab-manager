"""AI cost tracker — records and aggregates LLM API usage.

Tracks per-call token usage and cost for BYOK users to see their
API spending. Adapted from dollar-lab's cost.py for the lab-manager
multi-model, multi-provider environment.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlmodel import Session

from lab_manager.models.api_usage import ApiUsageEvent

logger = logging.getLogger(__name__)

# ── Provider pricing (USD per 1M tokens) ────────────────────────
# Updated 2026-03. These are list prices; actual BYOK costs may differ.
PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "google": {
        "gemini-2.5-flash": (0.15, 0.60),
        "gemini-2.5-pro": (1.25, 10.00),
        "gemini-3.1-pro-preview": (1.25, 10.00),
        "gemini-3.1-flash-preview": (0.15, 0.60),
    },
    "openai": {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-5.4": (5.00, 15.00),
    },
    "anthropic": {
        "claude-opus-4-6": (15.00, 75.00),
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-haiku-3-5": (0.80, 4.00),
    },
    "nvidia": {
        "meta/llama-3.2-90b-vision-instruct": (0.90, 0.90),
    },
}

# Fallback: $5 / 1M tokens in, $15 / 1M tokens out (conservative estimate)
_DEFAULT_PRICE = (5.00, 15.00)


def _resolve_provider(model: str) -> str:
    """Infer provider from model name."""
    m = model.lower()
    if m.startswith("gemini") or m.startswith("google/"):
        return "google"
    if m.startswith("gpt") or m.startswith("openai/"):
        return "openai"
    if m.startswith("claude") or m.startswith("anthropic/"):
        return "anthropic"
    if m.startswith("nvidia") or m.startswith("meta/"):
        return "nvidia"
    return "unknown"


def _strip_prefix(model: str) -> str:
    """Remove provider prefix like 'gemini/', 'openai/' from model name."""
    if "/" in model:
        parts = model.split("/", 1)
        # Keep paths like meta/llama-... as-is
        if parts[0] in ("gemini", "openai", "anthropic", "nvidia_nim"):
            return parts[1]
    return model


def calculate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost in USD for a single API call.

    Args:
        provider: Provider name (google, openai, anthropic, nvidia).
        model: Model name (may include provider prefix).
        tokens_in: Number of input/prompt tokens.
        tokens_out: Number of output/completion tokens.

    Returns:
        Cost in USD, rounded to 6 decimal places.
    """
    clean_model = _strip_prefix(model)
    provider_prices = PRICING.get(provider.lower(), {})
    price_in, price_out = provider_prices.get(clean_model, _DEFAULT_PRICE)
    cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
    return round(cost, 6)


def track_usage(
    db: Session,
    *,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    endpoint: str = "unknown",
    request_id: Optional[str] = None,
) -> ApiUsageEvent:
    """Record a single API call with automatic cost calculation.

    This is the main entry point. Call after each LLM API response.
    """
    if not provider:
        provider = _resolve_provider(model)

    cost = calculate_cost(provider, model, tokens_in, tokens_out)

    event = ApiUsageEvent(
        provider=provider,
        model=_strip_prefix(model),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        endpoint=endpoint,
        request_id=request_id,
    )
    db.add(event)
    db.flush()

    logger.info(
        "AI cost: $%.6f (%s/%s, %d in + %d out tokens, endpoint=%s)",
        cost,
        provider,
        model,
        tokens_in,
        tokens_out,
        endpoint,
    )
    return event


# ── Aggregation queries ──────────────────────────────────────────


def get_daily_cost(db: Session, days: int = 30) -> list[dict]:
    """Aggregate cost by day for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    # func.date() works on both PostgreSQL and SQLite
    day_col = func.date(ApiUsageEvent.timestamp).label("day")
    rows = db.execute(
        select(
            day_col,
            func.sum(ApiUsageEvent.cost_usd).label("total_cost"),
            func.sum(ApiUsageEvent.tokens_in).label("total_tokens_in"),
            func.sum(ApiUsageEvent.tokens_out).label("total_tokens_out"),
            func.count(ApiUsageEvent.id).label("request_count"),
        )
        .where(ApiUsageEvent.timestamp >= cutoff)
        .group_by(day_col)
        .order_by(day_col)
    ).all()
    return [
        {
            "date": r.day.isoformat() if isinstance(r.day, date) else str(r.day),
            "total_cost": round(float(r.total_cost or 0), 4),
            "total_tokens_in": int(r.total_tokens_in or 0),
            "total_tokens_out": int(r.total_tokens_out or 0),
            "request_count": int(r.request_count or 0),
        }
        for r in rows
    ]


def get_model_breakdown(db: Session, days: int = 30) -> list[dict]:
    """Aggregate cost by model for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(
            ApiUsageEvent.provider,
            ApiUsageEvent.model,
            func.sum(ApiUsageEvent.cost_usd).label("total_cost"),
            func.sum(ApiUsageEvent.tokens_in).label("total_tokens_in"),
            func.sum(ApiUsageEvent.tokens_out).label("total_tokens_out"),
            func.count(ApiUsageEvent.id).label("request_count"),
        )
        .where(ApiUsageEvent.timestamp >= cutoff)
        .group_by(ApiUsageEvent.provider, ApiUsageEvent.model)
        .order_by(func.sum(ApiUsageEvent.cost_usd).desc())
    ).all()
    return [
        {
            "provider": r.provider,
            "model": r.model,
            "total_cost": round(float(r.total_cost or 0), 4),
            "total_tokens_in": int(r.total_tokens_in or 0),
            "total_tokens_out": int(r.total_tokens_out or 0),
            "request_count": int(r.request_count or 0),
        }
        for r in rows
    ]


def get_endpoint_breakdown(db: Session, days: int = 30) -> list[dict]:
    """Aggregate cost by endpoint (ocr, rag, consensus, etc.)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(
            ApiUsageEvent.endpoint,
            func.sum(ApiUsageEvent.cost_usd).label("total_cost"),
            func.count(ApiUsageEvent.id).label("request_count"),
        )
        .where(ApiUsageEvent.timestamp >= cutoff)
        .group_by(ApiUsageEvent.endpoint)
        .order_by(func.sum(ApiUsageEvent.cost_usd).desc())
    ).all()
    return [
        {
            "endpoint": r.endpoint,
            "total_cost": round(float(r.total_cost or 0), 4),
            "request_count": int(r.request_count or 0),
        }
        for r in rows
    ]


def get_total_cost(db: Session, days: int = 30) -> dict:
    """Get total cost summary for the period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    row = db.execute(
        select(
            func.coalesce(func.sum(ApiUsageEvent.cost_usd), 0).label("total_cost"),
            func.coalesce(func.sum(ApiUsageEvent.tokens_in), 0).label(
                "total_tokens_in"
            ),
            func.coalesce(func.sum(ApiUsageEvent.tokens_out), 0).label(
                "total_tokens_out"
            ),
            func.count(ApiUsageEvent.id).label("request_count"),
        ).where(ApiUsageEvent.timestamp >= cutoff)
    ).one()
    return {
        "period_days": days,
        "total_cost": round(float(row.total_cost), 4),
        "total_tokens_in": int(row.total_tokens_in),
        "total_tokens_out": int(row.total_tokens_out),
        "request_count": int(row.request_count),
    }
