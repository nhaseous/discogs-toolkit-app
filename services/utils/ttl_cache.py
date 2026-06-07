"""
Generic thread-safe in-memory cache with per-entry TTL and a bounded size.

Backs both the Lookup payload cache (`lookup_cache`) and the Recommendations
search-resolution cache (`services/logic/recommend.py`). In-memory and
per-process: on a multi-instance GAE deployment each instance warms its own
copy, and a miss simply falls back to a fresh fetch — so correctness never
depends on a hit.
"""
import threading
import time


class TTLCache:
    def __init__(self, ttl_seconds, max_entries):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._cache = {}
        self._lock = threading.Lock()

    def put(self, key, value):
        expiry = time.time() + self._ttl
        with self._lock:
            self._cache[key] = (expiry, value)
            if len(self._cache) > self._max:
                # Drop the soonest-to-expire entries first to keep the dict bounded.
                for k, _ in sorted(self._cache.items(), key=lambda kv: kv[1][0])[:len(self._cache) - self._max]:
                    self._cache.pop(k, None)

    def get(self, key):
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            expiry, value = entry
            if time.time() > expiry:
                self._cache.pop(key, None)
                return None
            return value
