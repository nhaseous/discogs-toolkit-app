import collections
collections.Callable = collections.abc.Callable

from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import html as _html, json, math, re

from helper.api import (
    fetch_all_pages, clean_artist, 
    UserNotFoundError, CollectionPrivateError, WantlistPrivateError, ListPrivateError, 
    RateLimitError, CloudflareBlockedError
)

def get_collection(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/collection/folders/0/releases".format(username)
    params = {"sort": "artist", "sort_order": "asc"}

    results = []
    try:
        releases = fetch_all_pages(url, "releases", scraper, params=params, auth=auth)
    except UserNotFoundError: raise UserNotFoundError(username)
    except CollectionPrivateError: raise CollectionPrivateError(username)
    
    for r in releases:
        info = r["basic_information"]
        artist = clean_artist(info["artists"][0]) if info.get("artists") else ""
        title = info.get("title", "")
        fmt_info = info["formats"][0] if info.get("formats") else {}
        fmt = fmt_info.get("name", "")
        fmt_descriptions = ", ".join(fmt_info.get("descriptions") or [])
        fmt_text = fmt_info.get("text", "")
        release_id = info.get("id", "")
        
        # New: include community stats and metadata for aggregation
        community = r.get("community", {})
        results.append({
            "artist": artist,
            "title": title,
            "format": fmt,
            "format_descriptions": fmt_descriptions,
            "format_text": fmt_text,
            "thumb": info.get("thumb", ""),
            "cover_image": info.get("cover_image", ""),
            "url": "https://www.discogs.com/release/{0}".format(release_id) if release_id else "",
            "stats": "",
            "genres": info.get("genres") or [],
            "styles": info.get("styles") or [],
            "year": info.get("year", 0),
            "have": community.get("have", 0),
            "want": community.get("want", 0),
        })
    return results

def get_wantlist(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/wants".format(username)
    params = {"sort": "artist", "sort_order": "asc"}

    results = []
    try:
        wants = fetch_all_pages(url, "wants", scraper, params=params, auth=auth)
    except UserNotFoundError: raise UserNotFoundError(username)
    except WantlistPrivateError: raise WantlistPrivateError(username)

    for w in wants:
        info = w["basic_information"]
        artist = clean_artist(info["artists"][0]) if info.get("artists") else ""
        title = info.get("title", "")
        fmt_info = info["formats"][0] if info.get("formats") else {}
        fmt = fmt_info.get("name", "")
        fmt_descriptions = ", ".join(fmt_info.get("descriptions") or [])
        fmt_text = fmt_info.get("text", "")
        release_id = info.get("id", "")
        results.append({
            "artist": artist,
            "title": title,
            "format": fmt,
            "format_descriptions": fmt_descriptions,
            "format_text": fmt_text,
            "thumb": info.get("thumb", ""),
            "cover_image": info.get("cover_image", ""),
            "url": "https://www.discogs.com/release/{0}".format(release_id) if release_id else "",
            "stats": "",
        })
    return results

def get_lists(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/lists".format(username)
    
    results = []
    try:
        lists = fetch_all_pages(url, "lists", scraper, auth=auth)
    except UserNotFoundError: raise UserNotFoundError(username)
    except ListPrivateError: raise ListPrivateError(username)

    for lst in lists:
        if not lst.get("public", True):
            continue
        results.append({
            "id": lst.get("id", ""),
            "name": lst.get("name", ""),
            "description": lst.get("description", ""),
        })
    return results

def get_list_releases(list_id, scraper):
    # This stays mostly as is because it's scraping-based
    base_url = "https://www.discogs.com/lists/{0}".format(list_id)

    cache, total_pages = _scrape_list_page(base_url, scraper, page=1)
    if cache is None:
        return []

    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(_scrape_list_page, base_url, scraper, p): p
                for p in range(2, total_pages + 1)
            }
            for future in as_completed(futures):
                try:
                    page_cache, _ = future.result()
                except CloudflareBlockedError:
                    raise
                except Exception:
                    continue
                if page_cache:
                    cache.update(page_cache)

    return _extract_list_items(cache)

def _is_cf_blocked(resp):
    if resp.status_code in (403, 503):
        return 'cloudflare' in resp.text.lower()
    if resp.status_code == 200:
        text = resp.text.lower()
        return 'cloudflare' in text and any(m in text for m in ('cf-browser-verification', 'just a moment', 'sorry, you have been blocked'))
    return False

def _scrape_list_page(base_url, scraper, page):
    url = "{0}?page={1}".format(base_url, page) if page > 1 else base_url
    try:
        resp = scraper.get(url)
    except Exception:
        return None, 1
    if resp.status_code == 429:
        raise RateLimitError()
    if _is_cf_blocked(resp):
        raise CloudflareBlockedError()
    if resp.status_code != 200:
        return None, 1

    soup = BeautifulSoup(resp.text, 'html.parser')
    dsdata = soup.find(id='dsdata')
    if not dsdata:
        return None, 1
    try:
        data = json.loads(dsdata.get_text())['data']
    except Exception:
        return None, 1

    total_pages = 1
    for key, val in data.items():
        if key.startswith('CuratedList:'):
            for k, v in val.items():
                if 'offsetItems' in k:
                    total_count = v.get('totalCount', 0)
                    items_on_page = len(v.get('listItems', []))
                    if total_count and items_on_page:
                        total_pages = math.ceil(total_count / items_on_page)
            break

    return data, total_pages

def _extract_list_items(cache):
    results = []
    for key, val in cache.items():
        if not key.startswith('ListItem:'):
            continue

        comment_obj = val.get('comment') or {}
        comment = comment_obj.get('markup', '')
        position = val.get('position', 0)

        entity_ref = (val.get('entity') or {}).get('__ref', '')
        release = cache.get(entity_ref) or {}

        title = release.get('title', '')
        site_url = 'https://www.discogs.com' + release.get('siteUrl', '') if release.get('siteUrl') else ''

        primary_artists = release.get('primaryArtists') or []
        artist = ''
        if primary_artists:
            raw = primary_artists[0].get('displayName') or ''
            artist = re.sub(r'\s*\(\d+\)$', '', raw).strip()

        thumb = ''
        images_conn = release.get('images({"first":1})') or {}
        edges = images_conn.get('edges') or []
        if edges:
            img_ref = (edges[0].get('node') or {}).get('__ref', '')
            image = cache.get(img_ref) or {}
            imginfo_ref = (image.get('thumbnail') or {}).get('__ref', '')
            imginfo = cache.get(imginfo_ref) or {}
            thumb = imginfo.get('sourceUrl', '')

        release_id = release.get('discogsId', '')
        copies_for_sale = release.get('copiesForSale') or 0
        for_sale_text = ''
        for_sale_url = ''
        if copies_for_sale and release_id:
            for_sale_url = 'https://www.discogs.com/sell/release/{0}'.format(release_id)
            noun = 'copy' if copies_for_sale == 1 else 'copies'
            price_str = ''
            lowest_price_obj = release.get('lowestPrice') or {}
            for k, v in lowest_price_obj.items():
                if k.startswith('converted(') and isinstance(v, dict):
                    amount = v.get('amount')
                    currency = v.get('currency', '')
                    if amount is not None:
                        _symbols = {'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CAD': 'CA$', 'AUD': 'A$'}
                        sym = _symbols.get(currency, currency + ' ')
                        price_str = 'from {0}{1:.2f}'.format(sym, float(amount))
                    break
            for_sale_text = '{0} {1} {2}'.format(copies_for_sale, noun, price_str if price_str else 'for sale')

        results.append({
            'artist': artist,
            'title': title,
            'format': '',
            'format_descriptions': '',
            'format_text': '',
            'thumb': thumb,
            'url': site_url,
            'comment': comment,
            'for_sale': for_sale_text,
            'for_sale_url': for_sale_url,
            'stats': '',
            '_position': position,
        })

    results.sort(key=lambda x: x.pop('_position'))
    return results

# Render helpers are now handled by Jinja2 templates and macros in templates/macros.html
