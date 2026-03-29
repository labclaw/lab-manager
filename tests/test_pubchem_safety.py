"""Test PubChem thread safety: _LOCK protects cache and rate limiter."""

from __future__ import annotations

import threading

from lab_manager.services import pubchem


def test_lock_exists():
    """Module must expose a threading.Lock for thread safety."""
    assert isinstance(pubchem._LOCK, type(threading.Lock()))


def test_cache_put_is_thread_safe():
    """Concurrent _cache_put calls must not corrupt _CACHE."""
    pubchem.clear_cache()
    errors: list[Exception] = []

    def writer(i: int):
        try:
            pubchem._cache_put(f"key-{i}", {"cid": i})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(pubchem._CACHE) <= pubchem._CACHE_MAX
    pubchem.clear_cache()
