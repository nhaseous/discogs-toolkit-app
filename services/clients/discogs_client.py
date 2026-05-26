import time
import random
import re
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.utils.common import API_HEADERS as _API_HEADERS

# Given a seller username, returns a list of the releases in their inventory and their item ids.
def get_inventory_ids(username, scraper, auth=None):

    API_URL = "https://api.discogs.com/users/{0}/inventory".format(username)

    new_list = []
    seen_ids = {}  # release_id -> index in new_list
    page = 1

    while True:
        resp = scraper.get(API_URL, headers=_API_HEADERS, params={"page": page, "per_page": 100, "sort": "price", "sort_order": "asc", "status": "For Sale"}, auth=auth, timeout=20)

        if resp.status_code in (401, 403):
            print("get_inventory_ids: API access blocked (HTTP {0})".format(resp.status_code))
            return new_list

        data = resp.json()

        for listing in data.get("listings", []):
            release = listing.get("release", {})
            release_id = str(release.get("id", ""))
            listing_id = str(listing.get("id", ""))
            title = release.get("title", "")
            artist = release.get("artist", "")
            fmt = release.get("format", "")
            thumbnail_url = release.get("thumbnail", "")

            if artist and fmt:
                display_title = "{0} - {1} ({2})".format(artist, title, fmt)
            elif artist:
                display_title = "{0} - {1}".format(artist, title)
            elif fmt:
                display_title = "{0} ({1})".format(title, fmt)
            else:
                display_title = title

            if release_id:
                if release_id not in seen_ids:
                    seen_ids[release_id] = len(new_list)
                    new_list.append([display_title, release_id, thumbnail_url, [listing_id]])
                else:
                    new_list[seen_ids[release_id]][3].append(listing_id)

        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 1):
            break
        page += 1

    return new_list


_MAX_WORKERS = 5


class RequestBudget:
    """Thread-safe cap on how many Discogs requests a single lookup may fire.

    Used to keep an unauthenticated lookup under Discogs' 25-requests/60s limit:
    one budget is shared across the concurrent collection/wantlist/lists fetches,
    so the combined burst can never exceed the cap regardless of how the pages
    split between them. `exhausted` records whether the cap was ever hit, letting
    the caller tell a truncated (capped) result apart from a complete one.
    """
    def __init__(self, limit):
        self._remaining = limit
        self._lock = threading.Lock()
        self.exhausted = False

    def take(self):
        """Reserve one request. Returns False (and flags exhausted) if none left."""
        with self._lock:
            if self._remaining <= 0:
                self.exhausted = True
                return False
            self._remaining -= 1
            return True

def _build_api_session():
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

# Module-level session shared across all REST API callers. requests.Session is
# safe for concurrent reads from its connection pool; we never set per-user state
# on it (auth is passed per-call via OAuth1 tuples, and Discogs's API doesn't
# use cookies). Sharing one session across requests keeps TLS/TCP connections
# warm between lookups so subsequent lookups skip the handshake.
_API_SESSION = _build_api_session()


def make_api_session():
    """
    Returns the shared requests.Session for Discogs REST API calls (api.discogs.com).

    The REST API is NOT behind Cloudflare, so there's no reason to route these
    calls through cloudscraper: it only adds Cloudflare challenge-solving overhead
    (and an extra TLS fingerprinting layer) for endpoints that never challenge.
    cloudscraper is reserved for the HTML-scraping endpoints on www.discogs.com,
    which is the only place a Cloudflare interstitial actually appears.

    The HTTPAdapter caps the connection pool at 20. A lookup fans out 4 top-level
    fetches, each with its own 5-worker pool — combined burst exceeds the default
    10, so urllib3 would discard sockets and force fresh TLS handshakes. The
    pool is now also long-lived across requests, so the second-and-later lookup
    by a given process reuses already-established connections.
    """
    return _API_SESSION

class UserNotFoundError(Exception):
    pass

class CollectionPrivateError(Exception):
    pass

class WantlistPrivateError(Exception):
    pass

class ListPrivateError(Exception):
    pass

class RateLimitError(Exception):
    pass

class CloudflareBlockedError(Exception):
    pass

def is_cf_blocked(resp):
    """Detect a Cloudflare interstitial in a marketplace HTML response.

    Cloudflare returns 403/503 with a cloudflare-branded page when the request
    is challenged, and occasionally a 200 with the challenge body inline; both
    cases need to abort the scrape so the loader can retry rather than parse
    a useless body.
    """
    if resp.status_code in (403, 503):
        return 'cloudflare' in resp.text.lower()
    if resp.status_code == 200:
        text = resp.text.lower()
        return 'cloudflare' in text and any(m in text for m in ('cf-browser-verification', 'just a moment', 'sorry, you have been blocked'))
    return False

def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def _throttle(resp):
    """
    Checks Discogs rate limit headers and sleeps if we are getting close.
    """
    remaining = resp.headers.get('X-Discogs-Ratelimit-Remaining')
    if remaining is not None and int(remaining) < 5:
        time.sleep(2)

def request_with_retry(scraper, method, url, max_retries=3, max_429_retries=1, **kwargs):
    """
    Executes a request with exponential backoff.
    Network errors retry up to max_retries times.
    HTTP 429 (Discogs rate limit) retries up to max_429_retries times before
    raising RateLimitError — Discogs uses a sliding 60s window, so additional
    retries within the same call rarely succeed and just delay the user.
    """
    rate_limit_hits = 0
    for attempt in range(max_retries + 1):
        is_last = (attempt == max_retries)
        try:
            resp = scraper.request(method, url, **kwargs)
        except Exception:
            if is_last:
                raise
            time.sleep((2 ** attempt) + random.random())
            continue

        _throttle(resp)

        if resp.status_code == 429:
            if rate_limit_hits >= max_429_retries:
                raise RateLimitError()
            rate_limit_hits += 1
            time.sleep((2 ** attempt) + random.random())
            continue

        return resp
    return None  # unreachable

def fetch_all_pages(url, items_key, scraper, params=None, auth=None, return_total=False, budget=None):
    """
    Fetches all pages of a paginated Discogs API endpoint concurrently.
    If return_total=True, returns (results, total_items) instead of just results.

    If a RequestBudget is passed, every page request reserves a token first and
    page scheduling stops once the budget is spent. Skipped pages leave the result
    short of total_items — callers detect that mismatch to surface a rate-limit cap.
    """
    if params is None:
        params = {}
    params = dict(params, per_page=100)

    if budget is not None and not budget.take():
        return ([], 0) if return_total else []

    first_resp = request_with_retry(scraper, "GET", url, params=dict(params, page=1), headers=_API_HEADERS, auth=auth)

    # NB: test `first_resp is not None`, not `if first_resp` — requests.Response
    # is falsy for any 4xx/5xx (its __bool__ returns .ok), so a plain `if first_resp`
    # silently skips these checks for exactly the error responses we care about
    # (404 / 401 / 403), making private and missing users look like empty results.
    if first_resp is not None and first_resp.status_code == 404:
        raise UserNotFoundError()
    if first_resp is not None and first_resp.status_code in (401, 403):
        if "collection" in url: raise CollectionPrivateError()
        if "wants" in url: raise WantlistPrivateError()
        if "lists" in url: raise ListPrivateError()

    if first_resp is None or first_resp.status_code != 200:
        # Non-standard status: check if Discogs sent an error body anyway
        if first_resp is not None:
            _err = _safe_json(first_resp)
            if _err and "message" in _err:
                if "collection" in url: raise CollectionPrivateError()
                if "wants" in url: raise WantlistPrivateError()
                if "lists" in url: raise ListPrivateError()
        return ([], 0) if return_total else []

    first_data = _safe_json(first_resp)
    if not first_data:
        return ([], 0) if return_total else []

    # 200 OK but body is an error message (no items key) — treat as inaccessible
    if "message" in first_data and items_key not in first_data:
        if "collection" in url: raise CollectionPrivateError()
        if "wants" in url: raise WantlistPrivateError()
        if "lists" in url: raise ListPrivateError()

    results = first_data.get(items_key, [])
    pagination = first_data.get("pagination", {})
    total_pages = pagination.get("pages", 1)
    total_items = pagination.get("items", 0)

    if total_pages > 1:
        rate_limited = False
        # Reserve a budget token per extra page up front, stopping once the shared
        # budget is spent so the burst stays within the rate limit. Pages left
        # unscheduled make the result fall short of total_items (the cap signal).
        pages = []
        for p in range(2, total_pages + 1):
            if budget is not None and not budget.take():
                break
            pages.append(p)
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {
                executor.submit(request_with_retry, scraper, "GET", url, params=dict(params, page=p), headers=_API_HEADERS, auth=auth): p
                for p in pages
            }
            for future in as_completed(futures):
                try:
                    resp = future.result()
                    if resp and resp.status_code == 200:
                        data = _safe_json(resp)
                        if data:
                            results.extend(data.get(items_key, []))
                except RateLimitError:
                    rate_limited = True
                except Exception:
                    continue
        if rate_limited:
            raise RateLimitError()

    return (results, total_items) if return_total else results

def get_collection_value(username, scraper, auth=None):
    """
    Fetches the minimum, median, and maximum value of a user's collection.
    Requires authentication as the owner.
    """
    url = "https://api.discogs.com/users/{0}/collection/value".format(username)
    resp = request_with_retry(scraper, "GET", url, headers=_API_HEADERS, auth=auth)
    if resp and resp.status_code == 200:
        return _safe_json(resp)
    return None

def get_user_profile(username, scraper, auth=None):
    """
    Fetches a user's public profile. Used to read counts like num_wantlist and
    num_collection, which Discogs exposes even when the underlying list is set
    to private — useful for telling a private list apart from an empty one.
    Returns {} if the profile can't be fetched.
    """
    url = "https://api.discogs.com/users/{0}".format(username)
    resp = request_with_retry(scraper, "GET", url, headers=_API_HEADERS, auth=auth)
    if resp and resp.status_code == 200:
        return _safe_json(resp) or {}
    return {}

def reprice_listings(listings, auth):
    """Reprice a batch of the signed-in user's marketplace listings.

    For each listing: fetch its current data, compute the new price (an explicit
    ``custom_price`` if supplied, otherwise undercut the cheapest competitor),
    then POST the update. Returns a per-listing result list. ``auth`` is the
    caller's OAuth1 object; the route is responsible for authenticating the user.
    """
    results = []
    scraper = make_api_session()

    for item in listings:
        lid = str(item.get("id", ""))
        seller_price = float(item.get("seller_price", 0))
        cheapest_price = float(item.get("cheapest_price", 0))

        if not lid:
            results.append({"id": lid, "status": "error", "message": "Missing listing id"})
            continue

        custom_price_raw = item.get("custom_price")
        if custom_price_raw is not None:
            new_price = round(float(custom_price_raw), 2)
        else:
            pct = (seller_price - cheapest_price) / cheapest_price * 100 if cheapest_price > 0 else 0
            new_price = seller_price * 0.9 if pct > 10 else cheapest_price - 0.5
            new_price = round(new_price, 2)

        base_url = "https://api.discogs.com/marketplace/listings/{}".format(lid)

        get_resp = request_with_retry(scraper, "GET", base_url, headers=_API_HEADERS, auth=auth)
        if get_resp is None or get_resp.status_code != 200:
            status = "HTTP {}".format(get_resp.status_code) if get_resp is not None else "no response"
            results.append({"id": lid, "status": "error", "message": "GET failed: {}".format(status)})
            continue

        ld = _safe_json(get_resp) or {}
        shipping = float((ld.get("shipping_price") or {}).get("value") or 0)
        old_price = float((ld.get("price") or {}).get("value") or 0)

        final_price = round(new_price - shipping, 2)
        if final_price <= 0:
            results.append({"id": lid, "status": "error", "message": "Price after shipping would be ${:.2f}".format(final_price)})
            continue

        release_id = (ld.get("release") or {}).get("id")
        condition = ld.get("condition", "")
        sleeve_condition = ld.get("sleeve_condition", "")
        status = ld.get("status", "For Sale")
        comments = ld.get("comments", "")
        allow_offers = ld.get("allow_offers")
        external_id = ld.get("external_id", "")
        location = ld.get("location", "")

        if not release_id or not condition:
            results.append({"id": lid, "status": "error", "message": "Could not read listing fields"})
            continue

        post_body = {"release_id": release_id, "condition": condition, "price": final_price, "status": status}
        if sleeve_condition:
            post_body["sleeve_condition"] = sleeve_condition
        if comments:
            post_body["comments"] = comments
        if allow_offers is not None:
            post_body["allow_offers"] = allow_offers
        if external_id:
            post_body["external_id"] = external_id
        if location:
            post_body["location"] = location

        post_resp = request_with_retry(scraper, "POST", base_url, headers=_API_HEADERS, auth=auth, json=post_body)
        if post_resp is not None and post_resp.status_code in (200, 204):
            results.append({"id": lid, "status": "success", "old_price": old_price, "new_price": final_price, "shipping": shipping})
        else:
            status = "HTTP {} — {}".format(post_resp.status_code, post_resp.text[:200]) if post_resp is not None else "no response"
            results.append({"id": lid, "status": "error", "message": "POST failed: {}".format(status)})

    return results

def clean_artist(artist_info):
    name = artist_info.get("anv") or artist_info.get("name", "")
    return re.sub(r'\s*\(\d+\)$', '', name).strip()

# Format descriptors that add noise rather than identify a release; dropped when
# we render an item's format-desc.
_FORMAT_DESC_OMIT = {"mono", "stereo"}

# Display-only abbreviations for verbose descriptors, keyed by the lower-cased
# descriptor. These shorten the string shown on match-cards only — the raw
# descriptions (format_tags) keep their full text so the Insights Dashboard still
# aggregates and filters on e.g. "Limited Edition".
_FORMAT_DESC_ABBREV = {
    "limited edition": "Ltd",
    "special edition": "S/Edition",
    "white label":     "W/Lbl",
    "picture disc":    "Pic Disc",
    "deluxe edition":  "Deluxe",
}

def clean_format_descriptions(descriptions):
    """Join a release's format descriptions for match-card display: omit noise
    tags like "Mono"/"Stereo" and abbreviate verbose descriptors. Display only —
    the source list is left untouched for Insights/filtering."""
    out = []
    for d in (descriptions or []):
        key = d.strip().lower()
        if key in _FORMAT_DESC_OMIT:
            continue
        out.append(_FORMAT_DESC_ABBREV.get(key, d))
    return ", ".join(out)
