"""Tests for pipeline lifecycle hooks."""

import time


from lab_manager.intake.hooks import (
    PipelineEvent,
    PipelineHooks,
    create_default_hooks,
    structured_logging_hook,
    timing_hook,
)


class TestPipelineHooks:
    def test_register_and_emit(self):
        hooks = PipelineHooks()
        calls = []

        hooks.register(PipelineEvent.after_ocr, lambda ctx: calls.append(ctx))
        hooks.emit(PipelineEvent.after_ocr, {"document_id": 42})

        assert len(calls) == 1
        assert calls[0]["document_id"] == 42
        assert calls[0]["event"] == "after_ocr"
        assert "timestamp" in calls[0]

    def test_decorator_registration(self):
        hooks = PipelineHooks()
        calls = []

        @hooks.on(PipelineEvent.pipeline_start)
        def my_hook(ctx):
            calls.append("started")

        hooks.emit(PipelineEvent.pipeline_start)
        assert calls == ["started"]

    def test_multiple_hooks_same_event(self):
        hooks = PipelineHooks()
        order = []

        hooks.register(PipelineEvent.after_consensus, lambda ctx: order.append("first"))
        hooks.register(PipelineEvent.after_consensus, lambda ctx: order.append("second"))

        hooks.emit(PipelineEvent.after_consensus)
        assert order == ["first", "second"]

    def test_emit_unregistered_event_is_noop(self):
        hooks = PipelineHooks()
        # Should not raise
        hooks.emit(PipelineEvent.before_ocr, {"doc": 1})

    def test_exception_in_hook_does_not_halt_pipeline(self):
        hooks = PipelineHooks()
        calls = []

        hooks.register(PipelineEvent.after_ocr, lambda ctx: 1 / 0)  # raises
        hooks.register(PipelineEvent.after_ocr, lambda ctx: calls.append("ok"))

        hooks.emit(PipelineEvent.after_ocr)
        assert calls == ["ok"]  # second hook still ran

    def test_clear_specific_event(self):
        hooks = PipelineHooks()
        hooks.register(PipelineEvent.after_ocr, lambda ctx: None)
        hooks.register(PipelineEvent.after_consensus, lambda ctx: None)

        hooks.clear(PipelineEvent.after_ocr)
        assert PipelineEvent.after_ocr not in hooks.registered_events
        assert PipelineEvent.after_consensus in hooks.registered_events

    def test_clear_all(self):
        hooks = PipelineHooks()
        hooks.register(PipelineEvent.after_ocr, lambda ctx: None)
        hooks.register(PipelineEvent.after_consensus, lambda ctx: None)

        hooks.clear()
        assert hooks.registered_events == []

    def test_registered_events(self):
        hooks = PipelineHooks()
        hooks.register(PipelineEvent.pipeline_start, lambda ctx: None)
        hooks.register(PipelineEvent.pipeline_complete, lambda ctx: None)

        events = hooks.registered_events
        assert PipelineEvent.pipeline_start in events
        assert PipelineEvent.pipeline_complete in events

    def test_context_gets_default_timestamp(self):
        hooks = PipelineHooks()
        captured = []
        hooks.register(PipelineEvent.after_ocr, lambda ctx: captured.append(ctx))

        hooks.emit(PipelineEvent.after_ocr)
        assert abs(captured[0]["timestamp"] - time.time()) < 2

    def test_context_preserves_existing_timestamp(self):
        hooks = PipelineHooks()
        captured = []
        hooks.register(PipelineEvent.after_ocr, lambda ctx: captured.append(ctx))

        hooks.emit(PipelineEvent.after_ocr, {"timestamp": 12345.0})
        assert captured[0]["timestamp"] == 12345.0


class TestBuiltinHooks:
    def test_timing_hook_computes_duration(self):
        ctx = {"stage_start": time.time() - 0.1}
        timing_hook(ctx)
        assert "duration_ms" in ctx
        assert ctx["duration_ms"] >= 50  # at least 50ms

    def test_timing_hook_without_start_is_noop(self):
        ctx = {"document_id": 1}
        timing_hook(ctx)
        assert "duration_ms" not in ctx

    def test_structured_logging_hook_no_crash(self, caplog):
        """Logging hook should handle all possible context shapes."""
        import logging

        with caplog.at_level(logging.INFO):
            structured_logging_hook({"event": "after_ocr", "document_id": 42})
            structured_logging_hook({"event": "routing_decision", "complexity": "high", "num_models": 3})
            structured_logging_hook({"event": "pipeline_error", "error": "timeout"})
            structured_logging_hook({"event": "after_consensus", "needs_human": True, "duration_ms": 150})
            structured_logging_hook({})  # minimal context

    def test_create_default_hooks(self):
        hooks = create_default_hooks()
        # Every event should have timing + logging hooks
        for event in PipelineEvent:
            assert event in hooks.registered_events
