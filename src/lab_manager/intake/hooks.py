"""Pipeline lifecycle hooks for the document intake pipeline.

Inspired by OpenClaw's plugin hooks system: register callbacks at each
pipeline stage for observability, metrics, custom validation, and integration
with external systems (logging, Slack, monitoring dashboards).

Usage::

    from lab_manager.intake.hooks import PipelineHooks, PipelineEvent

    hooks = PipelineHooks()

    @hooks.on(PipelineEvent.after_ocr)
    def log_ocr_result(ctx):
        print(f"OCR completed for {ctx['document_id']}: {len(ctx.get('ocr_text', ''))} chars")

    @hooks.on(PipelineEvent.after_consensus)
    def flag_low_agreement(ctx):
        if ctx.get("needs_human"):
            notify_reviewer(ctx["document_id"])
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from enum import Enum
from typing import Any, Callable

log = logging.getLogger(__name__)

HookCallback = Callable[[dict[str, Any]], None]


class PipelineEvent(str, Enum):
    """Events emitted during document intake pipeline stages."""

    # Stage 0: OCR
    before_ocr = "before_ocr"
    after_ocr = "after_ocr"
    ocr_failed = "ocr_failed"

    # Stage 1: Extraction (per-model and aggregate)
    before_extraction = "before_extraction"
    after_extraction = "after_extraction"
    model_extraction_complete = "model_extraction_complete"
    extraction_failed = "extraction_failed"

    # Stage 2: Consensus
    before_consensus = "before_consensus"
    after_consensus = "after_consensus"

    # Stage 3: Cross-model review
    before_review = "before_review"
    after_review = "after_review"
    review_skipped = "review_skipped"

    # Stage 4: Validation
    before_validation = "before_validation"
    after_validation = "after_validation"

    # Stage 5: Human review queue
    queued_for_review = "queued_for_review"
    auto_resolved = "auto_resolved"

    # Routing
    routing_decision = "routing_decision"

    # Pipeline lifecycle
    pipeline_start = "pipeline_start"
    pipeline_complete = "pipeline_complete"
    pipeline_error = "pipeline_error"


class PipelineHooks:
    """Registry for pipeline lifecycle hooks.

    Thread-safe for registration; callbacks are invoked synchronously
    in registration order.  Exceptions in callbacks are logged but do
    NOT halt the pipeline.
    """

    def __init__(self) -> None:
        self._hooks: dict[PipelineEvent, list[HookCallback]] = defaultdict(list)

    def register(self, event: PipelineEvent, callback: HookCallback) -> None:
        """Register a callback for a pipeline event."""
        self._hooks[event].append(callback)
        log.debug("Registered hook for %s: %s", event.value, callback.__name__)

    def on(self, event: PipelineEvent) -> Callable[[HookCallback], HookCallback]:
        """Decorator to register a hook callback.

        Example::

            @hooks.on(PipelineEvent.after_ocr)
            def my_hook(ctx):
                ...
        """

        def decorator(fn: HookCallback) -> HookCallback:
            self.register(event, fn)
            return fn

        return decorator

    def emit(self, event: PipelineEvent, context: dict[str, Any] | None = None) -> None:
        """Fire all registered callbacks for an event.

        Parameters
        ----------
        event : PipelineEvent
            The event to fire.
        context : dict, optional
            Arbitrary context dict passed to each callback.  A ``timestamp``
            key is added automatically if not present.
        """
        callbacks = self._hooks.get(event, [])
        if not callbacks:
            return

        ctx = dict(context) if context else {}
        ctx.setdefault("event", event.value)
        ctx.setdefault("timestamp", time.time())

        for cb in callbacks:
            try:
                cb(ctx)
            except Exception:
                log.exception(
                    "Hook %s raised an exception for event %s",
                    cb.__name__,
                    event.value,
                )

    def clear(self, event: PipelineEvent | None = None) -> None:
        """Remove hooks.  If event is None, remove all hooks."""
        if event is None:
            self._hooks.clear()
        else:
            self._hooks.pop(event, None)

    @property
    def registered_events(self) -> list[PipelineEvent]:
        """Return events that have at least one registered callback."""
        return [e for e, cbs in self._hooks.items() if cbs]


# ---------------------------------------------------------------------------
# Built-in hooks: structured logging
# ---------------------------------------------------------------------------


def structured_logging_hook(ctx: dict[str, Any]) -> None:
    """Default hook that logs pipeline events via structlog / stdlib."""
    event = ctx.get("event", "unknown")
    doc_id = ctx.get("document_id", "?")
    duration = ctx.get("duration_ms")

    extra = ""
    if duration is not None:
        extra = f" ({duration:.0f}ms)"
    if ctx.get("complexity"):
        extra += f" complexity={ctx['complexity']}"
    if ctx.get("num_models"):
        extra += f" models={ctx['num_models']}"
    if ctx.get("needs_human"):
        extra += " [NEEDS_HUMAN]"
    if ctx.get("error"):
        extra += f" error={ctx['error']}"

    log.info("[pipeline:%s] doc=%s%s", event, doc_id, extra)


def timing_hook(ctx: dict[str, Any]) -> None:
    """Hook that records stage timing metrics.

    Expects ``stage_start`` key (epoch float) in context; computes
    ``duration_ms`` and attaches it to the context dict for downstream hooks.
    """
    start = ctx.get("stage_start")
    if start is not None:
        ctx["duration_ms"] = (time.time() - start) * 1000


def create_default_hooks() -> PipelineHooks:
    """Create a PipelineHooks instance with standard logging and timing."""
    hooks = PipelineHooks()
    # Timing should fire before logging so duration_ms is available
    for event in PipelineEvent:
        hooks.register(event, timing_hook)
        hooks.register(event, structured_logging_hook)
    return hooks
