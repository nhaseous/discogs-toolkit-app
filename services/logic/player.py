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
_LOOKUP_URL = "https://itunes.apple.com/lookup"
_STOREFRONT = "US"
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


def _get_json_results(url, params):
    """GET an iTunes API endpoint and return its `results` list ([] on failure)."""
    try:
        resp = requests.get(url, params=params, timeout=_HTTP_TIMEOUT)
    except requests.RequestException:
        return []
    if resp.status_code != 200:
        return []
    try:
        return resp.json().get("results", []) or []
    except ValueError:
        return []


def _search(term, entity, limit):
    """Run one iTunes Search API query; return its results ([] on any failure)."""
    return _get_json_results(_SEARCH_URL, {
        "term": term, "entity": entity, "media": "music",
        "limit": limit, "country": _STOREFRONT,
    })


def _resolve_via_discography(artist, album):
    """Fallback: enumerate the artist's albums and match by title.

    The iTunes /search endpoint's relevance ranking sometimes omits a catalog
    album for a text query even though it's present (e.g. "Dr. Dre - The Chronic",
    buried under unrelated "The Chronic - EP" indie releases). Resolving the
    artist's id and listing their discography via /lookup surfaces it. The artist
    is already pinned by the lookup, so only the album title is matched here.
    """
    artist_id, best = None, 0.0
    for a in _search(artist, "musicArtist", 5):
        if a.get("wrapperType") != "artist":
            continue
        cov = _coverage(artist, _tokens(a.get("artistName", "")))
        if cov > best and cov >= 0.5:
            artist_id, best = a.get("artistId"), cov
    if not artist_id:
        return None

    results = _get_json_results(_LOOKUP_URL, {
        "id": artist_id, "entity": "album", "limit": 200, "country": _STOREFRONT,
    })
    for result in results:
        if result.get("wrapperType") != "collection":
            continue
        if _coverage(album, _tokens(result.get("collectionName", ""))) >= 0.6:
            return _build(result)
    return None


def resolve_apple_album(artist, album):
    """Resolve `artist`/`album` to an Apple Music album for the embed player.

    Returns a dict {embed_url, artwork, name, artist, apple_url} on a verified
    match, or None when Apple has no confident match (or the lookup failed). A
    previously-resolved match is served from cache without any network call.

    Tries progressively broader searches so a release isn't lost to one rigid
    query, stopping at the first result that passes `_result_matches`. A SONG
    search backs up the album search because iTunes reliably attributes songs to
    the real performing artist even when it mis-tags the album-level artist (e.g.
    A Tribe Called Quest's "The Low End Theory", whose album entry is credited to
    a malformed "Low End Theory, The") — and each song result still carries its
    album's id/artwork/title, which is all the embed needs.
    """
    artist = (artist or "").strip()
    album = (album or "").strip()
    if not album:
        return None

    cache_key = _key(artist, album)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    term = ("{0} {1}".format(artist, album)).strip()
    strategies = (
        ("album", term, 10),     # well-tagged albums: fast path
        ("song", term, 25),      # rescue albums iTunes mis-tags at the album level
    )
    for entity, query, limit in strategies:
        for result in _search(query, entity, limit):
            if _result_matches(artist, album, result):
                payload = _build(result)
                if payload:
                    _cache.put(cache_key, payload)
                    return payload

    # Last resort: scan the artist's discography for albums /search omits.
    payload = _resolve_via_discography(artist, album)
    if payload:
        _cache.put(cache_key, payload)
        return payload
    return None
