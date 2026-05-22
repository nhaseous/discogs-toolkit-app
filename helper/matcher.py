import collections
collections.Callable = collections.abc.Callable

from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# Discogs Collection Matcher Module
# Compares a user's collection against another user's wantlist via the Discogs REST API.

from helper.api import fetch_all_pages, clean_artist, clean_format_descriptions, RateLimitError

## Get ##

def _strict_key(artist, title, fmt, fmt_descriptions, fmt_text):
    return "{0} - {1} | {2} | {3} | {4}".format(artist, title, fmt, fmt_descriptions, fmt_text)

def _easy_key(artist, title, fmt):
    return "{0} - {1} | {2}".format(artist, title, fmt)

def get_collection(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/collection/folders/0/releases".format(username)
    params = {"sort": "artist", "sort_order": "asc"}
    
    releases = fetch_all_pages(url, "releases", scraper, params=params, auth=auth)
    
    result = []
    for r in releases:
        info = r["basic_information"]
        artist = clean_artist(info["artists"][0]) if info.get("artists") else ""
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
            "format_descriptions": clean_format_descriptions(fmt_info.get("descriptions")),
            "format_text":      fmt_text,
            "thumb":            info.get("thumb", ""),
            "cover_image":      info.get("cover_image", ""),
            "url":              "https://www.discogs.com/release/{0}".format(release_id) if release_id else "",
        })
    return result

def get_wantlist(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/wants".format(username)
    params = {"sort": "artist", "sort_order": "asc"}
    
    wants = fetch_all_pages(url, "wants", scraper, params=params, auth=auth)
    
    result = []
    for w in wants:
        info = w["basic_information"]
        artist = clean_artist(info["artists"][0]) if info.get("artists") else ""
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
