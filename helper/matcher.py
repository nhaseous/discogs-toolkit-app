import collections
collections.Callable = collections.abc.Callable

from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# Discogs Collection Matcher Module
# Compares a user's collection against another user's wantlist via the Discogs REST API.

_API_HEADERS = {"User-Agent": "DiscogsToolkitApp/1.0"}
_MAX_WORKERS = 5

## Get ##

def get_collection(username, scraper):
    url = "https://api.discogs.com/users/{0}/collection/folders/0/releases".format(username)
    result = []
    for r in _fetch_all_pages(url, "releases", scraper):
        info = r["basic_information"]
        artist = _clean_artist(info["artists"][0]) if info.get("artists") else ""
        title = info.get("title", "")
        fmt_info = info["formats"][0] if info.get("formats") else {}
        fmt = fmt_info.get("name", "")
        fmt_descriptions = ", ".join(fmt_info.get("descriptions", []))
        fmt_text = fmt_info.get("text", "")
        release_id = info.get("id", "")
        result.append({
            "key":              "{0} - {1}".format(artist, title),
            "artist":           artist,
            "title":            title,
            "format":           fmt,
            "format_descriptions": fmt_descriptions,
            "format_text":      fmt_text,
            "thumb":            info.get("thumb", ""),
            "url":              "https://www.discogs.com/release/{0}".format(release_id) if release_id else "",
        })
    return result

def get_wantlist(username, scraper):
    url = "https://api.discogs.com/users/{0}/wants".format(username)
    result = []
    for w in _fetch_all_pages(url, "wants", scraper):
        info = w["basic_information"]
        artist = _clean_artist(info["artists"][0]) if info.get("artists") else ""
        title = info.get("title", "")
        result.append("{0} - {1}".format(artist, title))
    return result

## Helper Functions ##

def _fetch_all_pages(url, items_key, scraper):
    params = {"sort": "artist", "sort_order": "asc", "per_page": 100}

    first = scraper.get(url, params=dict(params, page=1), headers=_API_HEADERS).json()
    total_pages = first.get("pagination", {}).get("pages", 1)

    pages_data = {1: first}

    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {
                executor.submit(scraper.get, url, params=dict(params, page=p), headers=_API_HEADERS): p
                for p in range(2, total_pages + 1)
            }
            for future in as_completed(futures):
                pages_data[futures[future]] = future.result().json()

    items = []
    for p in range(1, total_pages + 1):
        items.extend(pages_data[p].get(items_key, []))
    return items

def _clean_artist(artist_info):
    name = artist_info.get("anv") or artist_info.get("name", "")
    return re.sub(r'\s*\(\d+\)$', '', name).strip()
