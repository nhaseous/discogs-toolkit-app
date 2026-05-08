import collections
collections.Callable = collections.abc.Callable

from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# Discogs Collection Matcher Module
# Compares a user's collection against another user's wantlist via the Discogs REST API.

from helper.common import API_HEADERS as _API_HEADERS
_MAX_WORKERS = 5


class RateLimitError(Exception):
    pass

## Get ##

def _strict_key(artist, title, fmt, fmt_descriptions, fmt_text):
    return "{0} - {1} | {2} | {3} | {4}".format(artist, title, fmt, fmt_descriptions, fmt_text)

def _easy_key(artist, title, fmt):
    return "{0} - {1} | {2}".format(artist, title, fmt)

def get_collection(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/collection/folders/0/releases".format(username)
    result = []
    for r in _fetch_all_pages(url, "releases", scraper, auth=auth):
        info = r["basic_information"]
        artist = _clean_artist(info["artists"][0]) if info.get("artists") else ""
        title = info.get("title", "")
        fmt_info = info["formats"][0] if info.get("formats") else {}
        fmt = fmt_info.get("name", "")
        fmt_descriptions = ", ".join(fmt_info.get("descriptions") or [])
        fmt_text = fmt_info.get("text", "")
        release_id = info.get("id", "")
        result.append({
            "key":              _strict_key(artist, title, fmt, fmt_descriptions, fmt_text),
            "easy_key":         _easy_key(artist, title, fmt),
            "artist":           artist,
            "title":            title,
            "format":           fmt,
            "format_descriptions": fmt_descriptions,
            "format_text":      fmt_text,
            "thumb":            info.get("thumb", ""),
            "cover_image":      info.get("cover_image", ""),
            "url":              "https://www.discogs.com/release/{0}".format(release_id) if release_id else "",
        })
    return result

def get_wantlist(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/wants".format(username)
    result = []
    for w in _fetch_all_pages(url, "wants", scraper, auth=auth):
        info = w["basic_information"]
        artist = _clean_artist(info["artists"][0]) if info.get("artists") else ""
        title = info.get("title", "")
        fmt_info = info["formats"][0] if info.get("formats") else {}
        fmt = fmt_info.get("name", "")
        fmt_descriptions = ", ".join(fmt_info.get("descriptions") or [])
        fmt_text = fmt_info.get("text", "")
        result.append({
            "strict": _strict_key(artist, title, fmt, fmt_descriptions, fmt_text),
            "easy":   _easy_key(artist, title, fmt),
        })
    return result

## Helper Functions ##

def _fetch_all_pages(url, items_key, scraper, auth=None):
    params = {"sort": "artist", "sort_order": "asc", "per_page": 100}

    try:
        first_resp = scraper.get(url, params=dict(params, page=1), headers=_API_HEADERS, auth=auth)
    except Exception:
        return []
    if first_resp.status_code == 429:
        raise RateLimitError()
    try:
        first = first_resp.json()
    except Exception:
        return []
    total_pages = first.get("pagination", {}).get("pages", 1)

    pages_data = {1: first}

    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {
                executor.submit(scraper.get, url, params=dict(params, page=p), headers=_API_HEADERS, auth=auth): p
                for p in range(2, total_pages + 1)
            }
            for future in as_completed(futures):
                page_num = futures[future]
                try:
                    resp = future.result()
                except Exception:
                    continue
                if resp.status_code == 429:
                    raise RateLimitError()
                try:
                    data = resp.json()
                except Exception:
                    data = None
                if data is not None:
                    pages_data[page_num] = data

    items = []
    for p in range(1, total_pages + 1):
        items.extend(pages_data.get(p, {}).get(items_key, []))
    return items

def _clean_artist(artist_info):
    name = artist_info.get("anv") or artist_info.get("name", "")
    return re.sub(r'\s*\(\d+\)$', '', name).strip()
