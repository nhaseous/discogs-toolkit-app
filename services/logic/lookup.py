from concurrent.futures import ThreadPoolExecutor, as_completed
import html as _html, json, re

from services.clients.discogs_client import (
    fetch_all_pages, request_with_retry, get_user_profile, make_api_session, clean_artist,
    clean_format_descriptions,
    UserNotFoundError, CollectionPrivateError, WantlistPrivateError, ListPrivateError,
    RateLimitError, CloudflareBlockedError
)
from services.utils.common import API_HEADERS as _API_HEADERS


def _extract_artists(artists_list):
    result = []
    for a in (artists_list or []):
        name = clean_artist(a)
        if name and name != "Various" and name not in result:
            result.append(name)
    return result

def _extract_formats(formats_list):
    seen, result = set(), []
    for f in (formats_list or []):
        name = f.get("name")
        if not name or name == "All Media":
            continue
        if name in ("CD", "CDr"):
            name = "CD(r)"
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result

def _release_dict(info, date_added=None, folder_id=None):
    """Build the match-grid release dict from a Discogs `basic_information` block.
    date_added is collection-only; pass None to omit it (used for wantlist/list).
    folder_id is collection-only too: the user folder the item lives in (used by
    the Lookup page to split the collection into per-folder subtabs)."""
    fmt_info = info["formats"][0] if info.get("formats") else {}
    release_id = info.get("id", "")
    out = {
        "artist": _extract_artists(info.get("artists")),
        "title": info.get("title", ""),
        "format": _extract_formats(info.get("formats")),
        "format_descriptions": clean_format_descriptions(fmt_info.get("descriptions")),
        "format_text": fmt_info.get("text", ""),
        "format_tags": fmt_info.get("descriptions") or [],
        "thumb": info.get("thumb", ""),
        "cover_image": info.get("cover_image", ""),
        "url": "https://www.discogs.com/release/{0}".format(release_id) if release_id else "",
        "stats": "",
        "genres": info.get("genres") or [],
        "styles": info.get("styles") or [],
        "year": info.get("year", 0),
        "labels": [l.get("name", "") for l in (info.get("labels") or []) if l.get("name")],
    }
    if date_added is not None:
        out["date_added"] = date_added
    if folder_id is not None:
        out["folder_id"] = folder_id
    return out

def get_collection(username, scraper, auth=None, budget=None):
    url = "https://api.discogs.com/users/{0}/collection/folders/0/releases".format(username)
    params = {"sort": "artist", "sort_order": "asc"}

    results = []
    try:
        releases, expected_total = fetch_all_pages(url, "releases", scraper, params=params, auth=auth, return_total=True, budget=budget)
    except UserNotFoundError: raise UserNotFoundError(username)
    except CollectionPrivateError: raise CollectionPrivateError(username)

    # Like get_wantlist: a private collection can come back as an empty 200,
    # indistinguishable from a genuinely empty one. num_collection is reported in
    # the profile even when the collection is private, so use it to tell them
    # apart and show the correct "not public" notice.
    if not releases and (get_user_profile(username, scraper, auth=auth).get("num_collection") or 0) > 0:
        raise CollectionPrivateError(username)

    for r in releases:
        results.append(_release_dict(r["basic_information"], date_added=r.get("date_added", ""), folder_id=r.get("folder_id")))

    partial_warning = ""
    if expected_total and len(results) < expected_total:
        partial_warning = "Partial results: fetched {0} of {1} collection items. Some records may be missing due to a connection issue.".format(len(results), expected_total)

    return results, partial_warning, expected_total

def get_collection_folders(username, scraper, auth=None):
    """Return the user's collection folders as [{id, name, count}, ...].

    Discogs only exposes the user's named/custom folders (Jazz, To Sell, …) to
    the authenticated owner of the collection. For anyone else the endpoint
    returns just the catch-all "All" folder (id 0), so the Lookup page simply
    shows no per-folder subtabs in that case."""
    url = "https://api.discogs.com/users/{0}/collection/folders".format(username)
    try:
        resp = request_with_retry(scraper, "GET", url, headers=_API_HEADERS, auth=auth)
    except Exception:
        return []
    if resp is None or resp.status_code != 200:
        return []
    try:
        folders = resp.json().get("folders", [])
    except Exception:
        return []
    return [
        {"id": f.get("id"), "name": f.get("name", ""), "count": f.get("count", 0)}
        for f in folders if f.get("id") is not None
    ]

def get_wantlist(username, scraper, auth=None, budget=None):
    url = "https://api.discogs.com/users/{0}/wants".format(username)
    params = {"sort": "artist", "sort_order": "asc"}

    results = []
    try:
        wants, expected_total = fetch_all_pages(url, "wants", scraper, params=params, auth=auth, return_total=True, budget=budget)
    except UserNotFoundError: raise UserNotFoundError(username)
    except WantlistPrivateError: raise WantlistPrivateError(username)

    # A private wantlist returns 200 with an empty list (Discogs hides the
    # contents rather than returning 403), so it's indistinguishable from a
    # genuinely empty one at this point. Cross-check the profile's num_wantlist,
    # which Discogs reports even when the list is private, so we can show the
    # correct "not public" notice instead of "This wantlist is empty."
    if not wants and (get_user_profile(username, scraper, auth=auth).get("num_wantlist") or 0) > 0:
        raise WantlistPrivateError(username)

    for w in wants:
        results.append(_release_dict(w["basic_information"]))

    partial_warning = ""
    if expected_total and len(results) < expected_total:
        partial_warning = "Partial results: fetched {0} of {1} wantlist items. Some records may be missing due to a connection issue.".format(len(results), expected_total)

    return results, partial_warning, expected_total

def get_lists(username, scraper, auth=None, budget=None):
    url = "https://api.discogs.com/users/{0}/lists".format(username)

    results = []
    try:
        lists = fetch_all_pages(url, "lists", scraper, auth=auth, budget=budget)
    except UserNotFoundError: raise UserNotFoundError(username)
    except ListPrivateError: raise ListPrivateError(username)

    # Lists are fetched with a single call. A private lists set that returns 401/403
    # is still caught above; we deliberately skip the extra get_user_profile call that
    # would only distinguish a private-but-empty-200 set from a genuinely empty one —
    # it's a low-value distinction and the extra request risks the 25/min rate limit.
    for lst in lists:
        results.append({
            "id": lst.get("id", ""),
            "name": lst.get("name", ""),
            "description": lst.get("description", ""),
            "url": lst.get("uri", ""),
        })
    return results

def get_list_releases(list_id, auth=None):
    return _get_list_releases_api(list_id, make_api_session(), auth=auth)

def _get_list_releases_api(list_id, scraper, auth=None):
    url = "https://api.discogs.com/lists/{0}".format(list_id)
    try:
        items = fetch_all_pages(url, "items", scraper, auth=auth)
    except (UserNotFoundError, ListPrivateError, RateLimitError):
        raise
    except Exception:
        return []

    base = []
    for item in items:
        if item.get("type") not in ("release", "master"):
            continue

        display_title = item.get("display_title", "")
        # Discogs uses an en dash as the artist/title separator in display_title
        if " – " in display_title:
            artist, _, title = display_title.partition(" – ")
        elif " - " in display_title:
            artist, _, title = display_title.partition(" - ")
        else:
            artist, title = "", display_title

        base.append({
            "artist":              artist.strip(),
            "title":               title.strip(),
            "format":              "",
            "format_descriptions": "",
            "format_text":         "",
            "thumb":               "",
            "url":                 item.get("uri", ""),
            "comment":             item.get("comment", ""),
            "for_sale":            "",
            "for_sale_url":        "",
            "stats":               "",
            "_release_id":         item.get("id"),
            "_resource_url":       item.get("resource_url", ""),
        })

    def _enrich(idx, item):
        resource_url = item.pop("_resource_url", "")
        release_id = item.pop("_release_id", None)
        if not resource_url:
            return idx, item
        try:
            # max_429_retries=0: don't retry on rate limit — fail fast so other
            # concurrent calls aren't blocked, and fall back to no thumb/sales info.
            resp = request_with_retry(scraper, "GET", resource_url, headers=_API_HEADERS, auth=auth, max_429_retries=0)
            if resp is not None and resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = None
                if data:
                    thumb = data.get("thumb", "")
                    if not thumb:
                        images = data.get("images") or []
                        if images:
                            thumb = images[0].get("uri150", "")
                    item["thumb"] = thumb

                    num_for_sale = data.get("num_for_sale") or 0
                    lowest_price = data.get("lowest_price")
                    if num_for_sale and release_id:
                        noun = "copy" if num_for_sale == 1 else "copies"
                        price_str = "from ${0:.2f}".format(float(lowest_price)) if lowest_price is not None else ""
                        item["for_sale"] = "{0} {1} {2}".format(
                            num_for_sale, noun, price_str if price_str else "for sale"
                        )
                        item["for_sale_url"] = "https://www.discogs.com/sell/release/{0}".format(release_id)
        except Exception:
            pass
        return idx, item

    enriched = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_enrich, i, item): i for i, item in enumerate(base)}
        for future in as_completed(futures):
            try:
                idx, item = future.result()
                enriched[idx] = item
            except Exception:
                i = futures[future]
                base[i].pop("_release_id", None)
                base[i].pop("_resource_url", None)
                enriched[i] = base[i]

    return [enriched[i] for i in range(len(base))]

# Render helpers are now handled by Jinja2 templates and macros in templates/macros.html
