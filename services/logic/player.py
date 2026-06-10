"""
Resolve a Discogs release (artist + album title) to a streamable Apple Music
album, for the Lookup page's in-app preview player.

Apple Music is the single source of truth. Resolution uses the public **iTunes
Search API** (https://itunes.apple.com/search) — no API key, no OAuth, no token
of any kind — so it works identically on GAE, local dev, and the macOS desktop
build with nothing to configure. The returned `collectionId` drives Apple's
native embedded player (embed.music.apple.com), which streams ~30-90s previews
for anonymous visitors (full playback only for signed-in Apple Music users).

A search can return unrelated albums, so every candidate is verified by fuzzy
token-coverage match against the iTunes `artistName`/`collectionName` before it's
accepted — the same matching idea used to resolve Recommendations, but applied to
iTunes' separate artist/album fields rather than a combined "Artist - Album"
title. Positive resolutions are memoized in a long-TTL in-memory cache, since the
same popular albums recur across collections and Apple's catalog is stable.
"""
import re

import requests

from services.utils.ttl_cache import TTLCache

_SEARCH_URL = "https://itunes.apple.com/search"
# storefront only affects the embed page's locale/pricing chrome; "us" is a safe
# default and the album itself resolves by id regardless.
_EMBED_URL = "https://embed.music.apple.com/us/album/{0}"

# Resolutions are cheap to recompute but the same albums recur across collectors,
# so cache positive hits for a day (Apple's catalog is stable). Keyed by the
# normalized artist|album. Only successful matches are cached: a miss may be a
# transient network/HTTP failure, not "Apple doesn't have it", so caching None
# would wrongly suppress later retries. In-memory and per-process.
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE_MAX_ENTRIES = 4096
_cache = TTLCache(_CACHE_TTL_SECONDS, _CACHE_MAX_ENTRIES)

_HTTP_TIMEOUT = 6


def _norm(s):
    s = (s or "").lower().strip()
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _key(artist, album):
    return _norm(artist) + "|" + _norm(album)


def _tokens(s):
    """Lowercased alphanumeric word tokens, dropping a leading 'the'."""
    s = re.sub(r"^the\s+", "", (s or "").lower().strip())
    return {t for t in re.split(r"[^a-z0-9]+", s) if t}


def _coverage(needle, haystack_tokens):
    """Fraction of `needle`'s tokens present in `haystack_tokens` (0.0-1.0)."""
    nt = _tokens(needle)
    if not nt:
        return 0.0
    return len(nt & haystack_tokens) / len(nt)


def _result_matches(artist, album, result, artist_min=0.5, album_min=0.6):
    """True if an iTunes album result plausibly is the requested release. iTunes
    returns `artistName` and `collectionName` separately, so each is matched
    against its own field by token coverage — tolerating featured artists, extra
    qualifiers ("(Deluxe Edition)", "Remastered"), and word reordering."""
    album_tokens = _tokens(result.get("collectionName", ""))
    artist_tokens = _tokens(result.get("artistName", ""))
    if not _tokens(album):
        return False
    return (_coverage(album, album_tokens) >= album_min
            and _coverage(artist, artist_tokens) >= artist_min)


def _hi_res_artwork(url):
    """iTunes returns a 100x100 artwork URL; the mzstatic CDN serves arbitrary
    sizes by swapping the `{w}x{h}bb` segment, so request a large square for the
    sidebar now-playing cover. Returns "" when there's no artwork."""
    if not url:
        return ""
    return re.sub(r"/\d+x\d+bb\.(jpg|png)", r"/600x600bb.\1", url)


def _build(result):
    """Shape an accepted iTunes album result into the payload the client needs."""
    collection_id = result.get("collectionId")
    if not collection_id:
        return None
    return {
        "embed_url": _EMBED_URL.format(collection_id),
        "artwork": _hi_res_artwork(result.get("artworkUrl100", "")),
        "name": result.get("collectionName", ""),
        "artist": result.get("artistName", ""),
        "apple_url": result.get("collectionViewUrl", ""),
    }


def resolve_apple_album(artist, album):
    """Resolve `artist`/`album` to an Apple Music album for the embed player.

    Returns a dict {embed_url, artwork, name, artist, apple_url} on a verified
    match, or None when Apple has no confident match (or the lookup failed). A
    previously-resolved match is served from cache without any network call.
    """
    artist = (artist or "").strip()
    album = (album or "").strip()
    if not album:
        return None

    cache_key = _key(artist, album)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        "term": ("{0} {1}".format(artist, album)).strip(),
        "entity": "album",
        "media": "music",
        "limit": 10,
    }
    try:
        resp = requests.get(_SEARCH_URL, params=params, timeout=_HTTP_TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        results = resp.json().get("results", []) or []
    except ValueError:
        return None

    for result in results:
        if _result_matches(artist, album, result):
            payload = _build(result)
            if payload:
                _cache.put(cache_key, payload)
                return payload
    return None
