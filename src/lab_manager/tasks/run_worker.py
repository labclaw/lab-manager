"""Standalone worker process entry point.

Usage:
    python -m lab_manager.tasks.run_worker

Runs as a dedicated background task consumer, processing tasks from
the Redis queue. Multiple worker processes can run in parallel for
horizontal scaling.
"""

from __future__ import annotations

import logging
import signal
import time

from lab_manager.logging_config import configure_logging


def main():
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting background worker process")

    # Initialize task system
    from lab_manager.tasks.registry import register_builtin_tasks
    from lab_manager.tasks.worker import get_task_manager

    register_builtin_tasks()
    tm = get_task_manager()
    tm.start()

    # Enable event bus Redis broadcasting
    from lab_manager.events import get_event_bus

    bus = get_event_bus()
    bus.enable_redis_broadcast()

    logger.info("Worker ready — consuming tasks from Redis queue")

    # Graceful shutdown
    running = True

    def _shutdown(signum, frame):
        nonlocal running
        logger.info("Received signal %s, shutting down gracefully...", signum)
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Keep alive until signaled
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        tm.stop()
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
