"""Background task worker using thread pool with Redis queue.

Provides a scalable task execution system:
- In-process thread pool for light tasks
- Redis queue for distributed heavy tasks across workers
- Automatic retry with exponential backoff
- Dead letter queue for failed tasks
- Task status tracking

Usage:
    from lab_manager.tasks.worker import task_manager, submit_task

    # Submit a task
    task_id = submit_task("reindex_search", {"entity": "products"})

    # Check status
    status = task_manager.get_status(task_id)
"""

from __future__ import annotations

import json
import logging
import threading
import time
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: Any = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    retries: int = 0


@dataclass
class TaskDef:
    """Internal task definition."""

    task_id: str
    name: str
    kwargs: dict[str, Any]
    priority: int = 2
    max_retries: int = 3
    retry_delay: float = 2.0  # Base delay, exponential backoff applied
    timeout: float = 300.0  # 5 minutes default
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TaskManager:
    """Manages background task execution with thread pool and optional Redis queue."""

    def __init__(self, max_workers: int = 4, redis_queue: bool = True):
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None
        self._registry: dict[str, Callable] = {}
        self._futures: dict[str, Future] = {}
        self._results: dict[str, TaskResult] = {}
        self._lock = threading.RLock()
        self._redis_queue = redis_queue
        self._running = False
        self._queue_thread: threading.Thread | None = None

    def start(self):
        """Start the task manager."""
        if self._running:
            return
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers, thread_name_prefix="task-worker"
        )
        self._running = True

        # Start Redis queue consumer if available
        if self._redis_queue:
            self._start_queue_consumer()

        logger.info("Task manager started with %d workers", self._max_workers)

    def stop(self):
        """Gracefully stop the task manager."""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=False)
            self._executor = None
        logger.info("Task manager stopped")

    def register(self, name: str, func: Callable, **defaults):
        """Register a task function.

        Args:
            name: Unique task name (e.g., "reindex_search").
            func: Callable that accepts keyword arguments.
            **defaults: Default task options (max_retries, timeout, priority).
        """
        self._registry[name] = func
        if defaults:
            self._registry[f"_defaults_{name}"] = defaults
        logger.debug("Registered task: %s", name)

    def submit(
        self,
        name: str,
        kwargs: dict[str, Any] | None = None,
        priority: int = 2,
        max_retries: int = 3,
        timeout: float = 300.0,
        distributed: bool = False,
    ) -> str:
        """Submit a task for execution.

        Args:
            name: Registered task name.
            kwargs: Arguments to pass to the task function.
            priority: Task priority (0=critical, 3=low).
            max_retries: Number of retries on failure.
            timeout: Max execution time in seconds.
            distributed: If True, enqueue in Redis for any worker to pick up.

        Returns:
            Task ID string.
        """
        task_id = str(uuid.uuid4())[:12]
        task = TaskDef(
            task_id=task_id,
            name=name,
            kwargs=kwargs or {},
            priority=priority,
            max_retries=max_retries,
            timeout=timeout,
        )

        with self._lock:
            self._results[task_id] = TaskResult(
                task_id=task_id, status=TaskStatus.PENDING
            )

        if distributed and self._enqueue_redis(task):
            logger.info("Task %s enqueued to Redis: %s", task_id, name)
            return task_id

        # Execute locally
        self._execute_local(task)
        return task_id

    def get_status(self, task_id: str) -> TaskResult | None:
        """Get task status. Checks local cache then Redis."""
        with self._lock:
            result = self._results.get(task_id)
        if result:
            return result

        # Check Redis
        return self._get_redis_status(task_id)

    def _execute_local(self, task: TaskDef):
        """Execute task in local thread pool."""
        if not self._executor or not self._running:
            # Fallback: run synchronously
            self._run_task(task)
            return

        future = self._executor.submit(self._run_task, task)
        with self._lock:
            self._futures[task.task_id] = future

    def _run_task(self, task: TaskDef, retry: int = 0):
        """Execute a task with retry logic."""
        func = self._registry.get(task.name)
        if func is None:
            logger.error("Unknown task: %s", task.name)
            with self._lock:
                self._results[task.task_id] = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error=f"Unknown task: {task.name}",
                )
            return

        # Update status
        started = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._results[task.task_id] = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.RUNNING,
                started_at=started,
                retries=retry,
            )

        try:
            result = func(**task.kwargs)
            with self._lock:
                self._results[task.task_id] = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.COMPLETED,
                    result=result,
                    started_at=started,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    retries=retry,
                )
            self._store_redis_status(task.task_id, self._results[task.task_id])
            logger.info("Task %s completed: %s", task.task_id, task.name)
        except Exception as exc:
            if retry < task.max_retries:
                delay = task.retry_delay * (2**retry)
                logger.warning(
                    "Task %s failed (retry %d/%d in %.1fs): %s",
                    task.task_id,
                    retry + 1,
                    task.max_retries,
                    delay,
                    exc,
                )
                with self._lock:
                    self._results[task.task_id] = TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.RETRYING,
                        error=str(exc),
                        retries=retry + 1,
                    )
                time.sleep(delay)
                self._run_task(task, retry + 1)
            else:
                error_msg = f"{exc}\n{traceback.format_exc()}"
                with self._lock:
                    self._results[task.task_id] = TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.FAILED,
                        error=error_msg,
                        started_at=started,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        retries=retry,
                    )
                self._store_redis_status(task.task_id, self._results[task.task_id])
                self._dead_letter(task, error_msg)
                logger.error(
                    "Task %s permanently failed: %s - %s",
                    task.task_id,
                    task.name,
                    exc,
                )

    def _enqueue_redis(self, task: TaskDef) -> bool:
        """Enqueue task in Redis for distributed processing."""
        try:
            from lab_manager.cache import get_redis

            r = get_redis()
            if r is None:
                return False
            payload = json.dumps(
                {
                    "task_id": task.task_id,
                    "name": task.name,
                    "kwargs": task.kwargs,
                    "priority": task.priority,
                    "max_retries": task.max_retries,
                    "timeout": task.timeout,
                    "created_at": task.created_at,
                },
                default=str,
            )
            # Use sorted set for priority queue
            r.zadd("lm:task_queue", {payload: task.priority})
            return True
        except Exception:
            return False

    def _start_queue_consumer(self):
        """Start background thread to consume tasks from Redis queue."""

        def _consume():
            from lab_manager.cache import get_redis

            while self._running:
                try:
                    r = get_redis()
                    if r is None:
                        time.sleep(5)
                        continue

                    # Pop highest priority task (lowest score)
                    items = r.zpopmin("lm:task_queue", count=1)
                    if not items:
                        time.sleep(0.5)
                        continue

                    payload_str, _score = items[0]
                    payload = json.loads(payload_str)
                    task = TaskDef(
                        task_id=payload["task_id"],
                        name=payload["name"],
                        kwargs=payload.get("kwargs", {}),
                        priority=payload.get("priority", 2),
                        max_retries=payload.get("max_retries", 3),
                        timeout=payload.get("timeout", 300),
                        created_at=payload.get("created_at", ""),
                    )
                    self._execute_local(task)
                except Exception:
                    logger.debug("Queue consumer cycle error", exc_info=True)
                    time.sleep(1)

        self._queue_thread = threading.Thread(
            target=_consume, daemon=True, name="task-queue-consumer"
        )
        self._queue_thread.start()

    def _store_redis_status(self, task_id: str, result: TaskResult):
        """Store task status in Redis for cross-worker visibility."""
        try:
            from lab_manager.cache import get_redis

            r = get_redis()
            if r is None:
                return
            key = f"lm:task_status:{task_id}"
            r.setex(
                key,
                3600,  # Keep status for 1 hour
                json.dumps(
                    {
                        "task_id": result.task_id,
                        "status": result.status.value,
                        "result": str(result.result) if result.result else None,
                        "error": result.error,
                        "started_at": result.started_at,
                        "completed_at": result.completed_at,
                        "retries": result.retries,
                    },
                    default=str,
                ),
            )
        except Exception:
            pass

    def _get_redis_status(self, task_id: str) -> TaskResult | None:
        """Fetch task status from Redis."""
        try:
            from lab_manager.cache import get_redis

            r = get_redis()
            if r is None:
                return None
            raw = r.get(f"lm:task_status:{task_id}")
            if raw is None:
                return None
            data = json.loads(raw)
            return TaskResult(
                task_id=data["task_id"],
                status=TaskStatus(data["status"]),
                result=data.get("result"),
                error=data.get("error"),
                started_at=data.get("started_at"),
                completed_at=data.get("completed_at"),
                retries=data.get("retries", 0),
            )
        except Exception:
            return None

    def _dead_letter(self, task: TaskDef, error: str):
        """Move permanently failed task to dead letter queue."""
        try:
            from lab_manager.cache import get_redis

            r = get_redis()
            if r is None:
                return
            r.lpush(
                "lm:dead_letter",
                json.dumps(
                    {
                        "task_id": task.task_id,
                        "name": task.name,
                        "kwargs": task.kwargs,
                        "error": error,
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                    },
                    default=str,
                ),
            )
            # Keep only last 1000 dead letters
            r.ltrim("lm:dead_letter", 0, 999)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_task_manager: TaskManager | None = None
_tm_lock = threading.RLock()


def get_task_manager() -> TaskManager:
    """Return the global task manager (lazy init)."""
    global _task_manager
    if _task_manager is None:
        with _tm_lock:
            if _task_manager is None:
                from lab_manager.config import get_settings

                settings = get_settings()
                _task_manager = TaskManager(
                    max_workers=settings.task_workers,
                    redis_queue=True,
                )
    return _task_manager


def submit_task(name: str, kwargs: dict | None = None, **options) -> str:
    """Convenience: submit a task to the global manager."""
    tm = get_task_manager()
    if not tm._running:
        tm.start()
    return tm.submit(name, kwargs, **options)
