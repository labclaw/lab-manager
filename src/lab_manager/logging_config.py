"""Structured logging configuration with request_id correlation."""

from __future__ import annotations

import contextvars
import logging
import sys
import uuid

import structlog

# Context variable for per-request correlation ID.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def generate_request_id() -> str:
    """Generate and store a new request ID."""
    rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    return rid


def add_request_id(logger: str, method: str, event_dict: dict) -> dict:
    """Structlog processor that adds request_id to every log event."""
    rid = request_id_var.get()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging() -> None:
    """Configure structlog for JSON or console output with request_id."""
    from lab_manager.config import get_settings

    settings = get_settings()
    use_json = settings.log_format == "json"

    renderer: structlog.types.Processor
    if use_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            add_request_id,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            add_request_id,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    )

    # Rebind to the current stderr each time we configure logging.
    #
    # Test suites create and tear down multiple capture streams; keeping a
    # handler bound to an old closed stream causes noisy "I/O operation on
    # closed file" logging failures in later requests.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
