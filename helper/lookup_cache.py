"""
Short-TTL in-memory cache of full Lookup payloads.

The /lookup page render trims the items it inlines into the HTML to a single
pagination window; the rest of the items are stashed here so the client can
hydrate them asynchronously from /lookup/data without re-hitting Discogs.

Keyed by (username_lower, list_id_or_empty); lookups are public so no auth
data is part of the key. In-memory only — a stale miss on a multi-instance
deployment falls back to a fresh Discogs fetch in the /lookup/data handler.
"""
import threading
import time

_TTL_SECONDS = 300
_MAX_ENTRIES = 32

_CACHE = {}
_LOCK = threading.Lock()


def put(key, payload):
    expiry = time.time() + _TTL_SECONDS
    with _LOCK:
        _CACHE[key] = (expiry, payload)
        if len(_CACHE) > _MAX_ENTRIES:
            # Drop oldest expiries first to keep the dict bounded.
            for k, _ in sorted(_CACHE.items(), key=lambda kv: kv[1][0])[:len(_CACHE) - _MAX_ENTRIES]:
                _CACHE.pop(k, None)


def get(key):
    with _LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        expiry, payload = entry
        if time.time() > expiry:
            _CACHE.pop(key, None)
            return None
        return payload
