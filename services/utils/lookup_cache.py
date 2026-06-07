"""
Short-TTL in-memory cache of full Lookup payloads.

The /lookup page render trims the items it inlines into the HTML to a single
pagination window; the rest of the items are stashed here so the client can
hydrate them asynchronously from /lookup/data without re-hitting Discogs.

Keyed by (username_lower, list_id_or_empty); lookups are public so no auth
data is part of the key. The Recommendations tool also shares a collection
entry through this cache (key ("collection", username_lower)) so the common
Lookup -> Recommend flow doesn't re-page the same collection.

In-memory only — a stale miss on a multi-instance deployment falls back to a
fresh Discogs fetch in the /lookup/data handler. Backed by the shared TTLCache.
"""
from services.utils.ttl_cache import TTLCache

_TTL_SECONDS = 300
_MAX_ENTRIES = 32

_cache = TTLCache(_TTL_SECONDS, _MAX_ENTRIES)


def put(key, payload):
    _cache.put(key, payload)


def get(key):
    return _cache.get(key)
