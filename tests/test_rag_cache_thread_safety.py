"""Test RAG cache thread safety — concurrent reads/writes must not corrupt state."""

import threading
import time

from lab_manager.services import rag


def test_evict_cache_thread_safe():
    """Concurrent _evict_cache calls must not raise or corrupt the dict."""
    for i in range(100):
        rag._CACHE[f"key-{i}"] = (time.time(), {"answer": f"val-{i}"})

    errors: list[Exception] = []

    def evict():
        try:
            rag._evict_cache()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=evict) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent _evict_cache raised: {errors}"
    rag._CACHE.clear()


def test_cache_write_thread_safe():
    """Concurrent cache writes must not corrupt the dict."""
    rag._CACHE.clear()
    errors: list[Exception] = []

    def write(i: int):
        try:
            key = f"thread-key-{i}"
            with rag._CACHE_LOCK:
                rag._CACHE[key] = (time.time(), {"answer": f"val-{i}"})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent cache writes raised: {errors}"
    assert len(rag._CACHE) == 50
    rag._CACHE.clear()


def test_cache_lock_exists():
    """Verify _CACHE_LOCK is a threading.Lock."""
    assert hasattr(rag, "_CACHE_LOCK")
    assert isinstance(rag._CACHE_LOCK, type(threading.Lock()))


def test_concurrent_read_write():
    """Mixed concurrent reads and writes must not raise."""
    rag._CACHE.clear()
    for i in range(20):
        rag._CACHE[f"rkey-{i}"] = (time.time(), {"answer": f"val-{i}"})

    errors: list[Exception] = []

    def reader():
        for _ in range(50):
            try:
                with rag._CACHE_LOCK:
                    _ = rag._CACHE.get("rkey-0")
            except Exception as e:
                errors.append(e)

    def writer():
        for i in range(50):
            try:
                with rag._CACHE_LOCK:
                    rag._CACHE[f"wkey-{i}"] = (time.time(), {})
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(10)]
    threads += [threading.Thread(target=writer) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent read/write raised: {errors}"
    rag._CACHE.clear()
