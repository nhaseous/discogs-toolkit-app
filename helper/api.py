import time
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from helper.common import API_HEADERS as _API_HEADERS

_MAX_WORKERS = 5

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

def request_with_retry(scraper, method, url, max_retries=3, **kwargs):
    """
    Executes a request with exponential backoff on 429 Rate Limit.
    """
    retries = 0
    while retries <= max_retries:
        try:
            resp = scraper.request(method, url, **kwargs)
            _throttle(resp)
            
            if resp.status_code == 429:
                wait_time = (2 ** retries) + random.random()
                time.sleep(wait_time)
                retries += 1
                continue
                
            return resp
        except Exception:
            if retries == max_retries:
                raise
            wait_time = (2 ** retries) + random.random()
            time.sleep(wait_time)
            retries += 1
    return None

def fetch_all_pages(url, items_key, scraper, params=None, auth=None, return_total=False):
    """
    Fetches all pages of a paginated Discogs API endpoint concurrently.
    If return_total=True, returns (results, total_items) instead of just results.
    """
    if params is None:
        params = {}
    params = dict(params, per_page=100)

    first_resp = request_with_retry(scraper, "GET", url, params=dict(params, page=1), headers=_API_HEADERS, auth=auth)

    if first_resp and first_resp.status_code == 404:
        raise UserNotFoundError()
    if first_resp and first_resp.status_code in (401, 403):
        if "collection" in url: raise CollectionPrivateError()
        if "wants" in url: raise WantlistPrivateError()
        if "lists" in url: raise ListPrivateError()

    if not first_resp or first_resp.status_code != 200:
        return ([], 0) if return_total else []

    first_data = _safe_json(first_resp)
    if not first_data:
        return ([], 0) if return_total else []

    results = first_data.get(items_key, [])
    pagination = first_data.get("pagination", {})
    total_pages = pagination.get("pages", 1)
    total_items = pagination.get("items", 0)

    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {
                executor.submit(request_with_retry, scraper, "GET", url, params=dict(params, page=p), headers=_API_HEADERS, auth=auth): p
                for p in range(2, total_pages + 1)
            }
            for future in as_completed(futures):
                try:
                    resp = future.result()
                    if resp and resp.status_code == 200:
                        data = _safe_json(resp)
                        if data:
                            results.extend(data.get(items_key, []))
                except Exception:
                    continue

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

def clean_artist(artist_info):
    name = artist_info.get("anv") or artist_info.get("name", "")
    return re.sub(r'\s*\(\d+\)$', '', name).strip()
