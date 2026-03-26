"""Tests for AI cost tracker: pricing, recording, aggregation, and API endpoint."""

from datetime import datetime, timedelta, timezone

import pytest


# ── 1. Cost calculation tests ────────────────────────────────────


class TestCalculateCost:
    def test_known_gemini_flash(self):
        from lab_manager.services.cost_tracker import calculate_cost

        # gemini-2.5-flash: $0.15/M in, $0.60/M out
        cost = calculate_cost("google", "gemini-2.5-flash", 1000, 500)
        expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
        assert cost == pytest.approx(expected, abs=1e-7)

    def test_known_gpt5(self):
        from lab_manager.services.cost_tracker import calculate_cost

        # gpt-5.4: $5.00/M in, $15.00/M out
        cost = calculate_cost("openai", "gpt-5.4", 2000, 1000)
        expected = (2000 * 5.0 + 1000 * 15.0) / 1_000_000
        assert cost == pytest.approx(expected, abs=1e-7)

    def test_unknown_model_uses_default(self):
        from lab_manager.services.cost_tracker import calculate_cost

        # Unknown model gets default pricing ($5/M in, $15/M out)
        cost = calculate_cost("unknown", "some-random-model", 1000, 1000)
        expected = (1000 * 5.0 + 1000 * 15.0) / 1_000_000
        assert cost == pytest.approx(expected, abs=1e-7)

    def test_zero_tokens(self):
        from lab_manager.services.cost_tracker import calculate_cost

        cost = calculate_cost("google", "gemini-2.5-flash", 0, 0)
        assert cost == 0.0

    def test_strips_provider_prefix(self):
        from lab_manager.services.cost_tracker import calculate_cost

        # "gemini/gemini-2.5-flash" should strip to "gemini-2.5-flash"
        cost = calculate_cost("google", "gemini/gemini-2.5-flash", 1000, 500)
        expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
        assert cost == pytest.approx(expected, abs=1e-7)


# ── 2. Provider resolution tests ────────────────────────────────


class TestResolveProvider:
    def test_gemini(self):
        from lab_manager.services.cost_tracker import _resolve_provider

        assert _resolve_provider("gemini-2.5-flash") == "google"

    def test_gpt(self):
        from lab_manager.services.cost_tracker import _resolve_provider

        assert _resolve_provider("gpt-5.4") == "openai"

    def test_claude(self):
        from lab_manager.services.cost_tracker import _resolve_provider

        assert _resolve_provider("claude-opus-4-6") == "anthropic"

    def test_nvidia(self):
        from lab_manager.services.cost_tracker import _resolve_provider

        assert _resolve_provider("nvidia_nim/model") == "nvidia"

    def test_unknown(self):
        from lab_manager.services.cost_tracker import _resolve_provider

        assert _resolve_provider("custom-model") == "unknown"


# ── 3. Track usage + aggregation (DB integration) ───────────────


class TestTrackUsage:
    def test_track_usage_creates_event(self, db_session):
        from lab_manager.services.cost_tracker import track_usage

        event = track_usage(
            db_session,
            provider="google",
            model="gemini-2.5-flash",
            tokens_in=1000,
            tokens_out=500,
            endpoint="rag",
        )
        assert event.id is not None
        assert event.provider == "google"
        assert event.model == "gemini-2.5-flash"
        assert event.tokens_in == 1000
        assert event.tokens_out == 500
        assert event.cost_usd > 0
        assert event.endpoint == "rag"

    def test_track_usage_auto_resolves_provider(self, db_session):
        from lab_manager.services.cost_tracker import track_usage

        event = track_usage(
            db_session,
            provider="",  # empty provider should auto-resolve
            model="gpt-5.4",
            tokens_in=100,
            tokens_out=50,
            endpoint="test",
        )
        assert event.provider == "openai"


class TestAggregation:
    def _seed_events(self, db):
        from lab_manager.models.api_usage import ApiUsageEvent

        now = datetime.now(timezone.utc)
        events = [
            ApiUsageEvent(
                provider="google",
                model="gemini-2.5-flash",
                tokens_in=1000,
                tokens_out=500,
                cost_usd=0.000450,
                endpoint="rag",
                timestamp=now - timedelta(hours=2),
            ),
            ApiUsageEvent(
                provider="google",
                model="gemini-2.5-flash",
                tokens_in=2000,
                tokens_out=800,
                cost_usd=0.000780,
                endpoint="rag",
                timestamp=now - timedelta(hours=1),
            ),
            ApiUsageEvent(
                provider="openai",
                model="gpt-5.4",
                tokens_in=500,
                tokens_out=200,
                cost_usd=0.005500,
                endpoint="ocr",
                timestamp=now,
            ),
        ]
        for e in events:
            db.add(e)
        db.flush()

    def test_get_daily_cost(self, db_session):
        from lab_manager.services.cost_tracker import get_daily_cost

        self._seed_events(db_session)
        daily = get_daily_cost(db_session, days=7)
        assert len(daily) >= 1
        total = sum(d["total_cost"] for d in daily)
        assert total > 0

    def test_get_model_breakdown(self, db_session):
        from lab_manager.services.cost_tracker import get_model_breakdown

        self._seed_events(db_session)
        models = get_model_breakdown(db_session, days=7)
        assert len(models) == 2
        model_names = {m["model"] for m in models}
        assert "gemini-2.5-flash" in model_names
        assert "gpt-5.4" in model_names

    def test_get_endpoint_breakdown(self, db_session):
        from lab_manager.services.cost_tracker import get_endpoint_breakdown

        self._seed_events(db_session)
        endpoints = get_endpoint_breakdown(db_session, days=7)
        endpoint_names = {e["endpoint"] for e in endpoints}
        assert "rag" in endpoint_names
        assert "ocr" in endpoint_names

    def test_get_total_cost(self, db_session):
        from lab_manager.services.cost_tracker import get_total_cost

        self._seed_events(db_session)
        total = get_total_cost(db_session, days=7)
        assert total["request_count"] == 3
        assert total["total_cost"] > 0
        assert total["total_tokens_in"] == 3500
        assert total["total_tokens_out"] == 1500

    def test_empty_db_returns_zeros(self, db_session):
        from lab_manager.services.cost_tracker import get_total_cost

        total = get_total_cost(db_session, days=7)
        assert total["request_count"] == 0
        assert total["total_cost"] == 0.0


# ── 4. API endpoint test ────────────────────────────────────────


class TestAiCostEndpoint:
    def _seed(self, db):
        from lab_manager.models.api_usage import ApiUsageEvent

        db.add(
            ApiUsageEvent(
                provider="google",
                model="gemini-2.5-flash",
                tokens_in=1000,
                tokens_out=500,
                cost_usd=0.000450,
                endpoint="rag",
            )
        )
        db.commit()

    def test_ai_cost_endpoint_returns_structure(self, client, db_session):
        self._seed(db_session)
        resp = client.get("/api/v1/analytics/ai-cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "daily" in data
        assert "by_model" in data
        assert "by_endpoint" in data
        assert data["summary"]["request_count"] >= 1

    def test_ai_cost_endpoint_with_days_param(self, client, db_session):
        self._seed(db_session)
        resp = client.get("/api/v1/analytics/ai-cost?days=7")
        assert resp.status_code == 200

    def test_ai_cost_endpoint_empty(self, client):
        resp = client.get("/api/v1/analytics/ai-cost")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["request_count"] == 0
        assert data["summary"]["total_cost"] == 0.0
