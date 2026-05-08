import collections
collections.Callable = collections.abc.Callable

from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import html as _html, json, math, re

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


def get_collection(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/collection/folders/0/releases".format(username)
    params = {"sort": "artist", "sort_order": "asc", "per_page": 100}

    first_resp = scraper.get(url, params=dict(params, page=1), headers=_API_HEADERS, auth=auth)
    if first_resp.status_code == 404:
        raise UserNotFoundError(username)
    if first_resp.status_code in (401, 403):
        raise CollectionPrivateError(username)
    if first_resp.status_code == 429:
        raise RateLimitError()
    if first_resp.status_code != 200:
        return []

    first_data = _safe_json(first_resp)
    if first_data is None:
        return []

    result = []
    for r in _fetch_all_pages(url, "releases", scraper, first_data, params, auth=auth):
        info = r["basic_information"]
        artist = _clean_artist(info["artists"][0]) if info.get("artists") else ""
        title = info.get("title", "")
        fmt_info = info["formats"][0] if info.get("formats") else {}
        fmt = fmt_info.get("name", "")
        fmt_descriptions = ", ".join(fmt_info.get("descriptions") or [])
        fmt_text = fmt_info.get("text", "")
        release_id = info.get("id", "")
        result.append({
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
    return result


def get_wantlist(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/wants".format(username)
    params = {"sort": "artist", "sort_order": "asc", "per_page": 100}

    first_resp = scraper.get(url, params=dict(params, page=1), headers=_API_HEADERS, auth=auth)
    if first_resp.status_code == 404:
        raise UserNotFoundError(username)
    if first_resp.status_code in (401, 403):
        raise WantlistPrivateError(username)
    if first_resp.status_code == 429:
        raise RateLimitError()
    if first_resp.status_code != 200:
        return []

    first_data = _safe_json(first_resp)
    if first_data is None:
        return []

    result = []
    for w in _fetch_all_pages(url, "wants", scraper, first_data, params, auth=auth):
        info = w["basic_information"]
        artist = _clean_artist(info["artists"][0]) if info.get("artists") else ""
        title = info.get("title", "")
        fmt_info = info["formats"][0] if info.get("formats") else {}
        fmt = fmt_info.get("name", "")
        fmt_descriptions = ", ".join(fmt_info.get("descriptions") or [])
        fmt_text = fmt_info.get("text", "")
        release_id = info.get("id", "")
        result.append({
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

    return result


def get_lists(username, scraper, auth=None):
    url = "https://api.discogs.com/users/{0}/lists".format(username)
    params = {"per_page": 100}

    first_resp = scraper.get(url, params=dict(params, page=1), headers=_API_HEADERS, auth=auth)
    if first_resp.status_code == 404:
        raise UserNotFoundError(username)
    if first_resp.status_code in (401, 403):
        raise ListPrivateError(username)
    if first_resp.status_code == 429:
        raise RateLimitError()
    if first_resp.status_code != 200:
        return []

    first_data = _safe_json(first_resp)
    if first_data is None:
        return []

    result = []
    for lst in _fetch_all_pages(url, "lists", scraper, first_data, params, auth=auth):
        if not lst.get("public", True):
            continue
        result.append({
            "id": lst.get("id", ""),
            "name": lst.get("name", ""),
            "description": lst.get("description", ""),
        })
    return result


def get_list_releases(list_id, scraper):
    base_url = "https://www.discogs.com/lists/{0}".format(list_id)

    cache, total_pages = _scrape_list_page(base_url, scraper, page=1)
    if cache is None:
        return []

    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {
                executor.submit(_scrape_list_page, base_url, scraper, p): p
                for p in range(2, total_pages + 1)
            }
            for future in as_completed(futures):
                try:
                    page_cache, _ = future.result()
                except Exception:
                    continue
                if page_cache:
                    cache.update(page_cache)

    return _extract_list_items(cache)


def _scrape_list_page(base_url, scraper, page):
    url = "{0}?page={1}".format(base_url, page) if page > 1 else base_url
    try:
        resp = scraper.get(url)
    except Exception:
        return None, 1
    if resp.status_code == 429:
        raise RateLimitError()
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


def _fetch_all_pages(url, items_key, scraper, first_page_data, params, auth=None):
    total_pages = first_page_data.get("pagination", {}).get("pages", 1)
    pages_data = {1: first_page_data}

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
                data = _safe_json(resp)
                if data is not None:
                    pages_data[page_num] = data

    items = []
    for p in range(1, total_pages + 1):
        items.extend(pages_data.get(p, {}).get(items_key, []))
    return items


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None

def _clean_artist(artist_info):
    name = artist_info.get("anv") or artist_info.get("name", "")
    return re.sub(r'\s*\(\d+\)$', '', name).strip()


# ── Render helpers ────────────────────────────────────────────────────────────

import assets as _assets

def render_lookup_grid(items, show_stats=False, prepend_card=""):
    cards = prepend_card
    for m in items:
        img_src = m.get("cover_image") or m.get("thumb")
        if img_src:
            art = '<img src="{0}" alt="" class="match-card-img">'.format(img_src)
        else:
            art = '<div class="match-card-placeholder">' + _assets.VINYL_PLACEHOLDER_SVG + '</div>'
        fmt_desc_html = ('<div class="match-card-format-desc">' + _html.escape(m.get("format_descriptions", "")) + '</div>') if m.get("format_descriptions") else ""
        fmt_text_html = ('<div class="match-card-format-text">' + _html.escape(m.get("format_text", "")) + '</div>') if m.get("format_text") else ""
        comment_html = ('<div class="match-card-comment">' + _html.escape(m.get("comment", "")) + '</div>') if m.get("comment") else ""
        stats_html = ('<div class="match-card-stats">' + _html.escape(m.get("stats", "")) + '</div>') if show_stats and m.get("stats") else ""
        for_sale_text = m.get("for_sale", "")
        for_sale_url = m.get("for_sale_url", "")
        for_sale_html = (
            '<div class="match-card-forsale" data-href="' + _html.escape(for_sale_url) + '"'
            ' onclick="event.stopPropagation();event.preventDefault();window.open(this.dataset.href,\'_blank\',\'noopener,noreferrer\')">'
            + _html.escape(for_sale_text) + '</div>'
        ) if for_sale_text and for_sale_url else ""
        href = m.get("url") or "#"
        cards += (
            '<a href="' + href + '" class="match-card" target="_blank" rel="noopener noreferrer">'
            '<div class="match-card-art">' + art + '</div>'
            '<div class="match-card-body">'
            '<div class="match-card-title">' + _html.escape(m.get("title", "")) + '</div>'
            '<div class="match-card-artist">' + _html.escape(m.get("artist", "")) + '</div>'
            + ('<div class="match-card-format">' + _html.escape(m.get("format", "")) + '</div>' if m.get("format") else "")
            + fmt_desc_html
            + fmt_text_html
            + for_sale_html
            + comment_html
            + stats_html +
            '</div>'
            '</a>'
        )
    return '<div class="match-grid">' + cards + '</div>'


def render_list_index(lists, username):
    if not lists:
        return '<p class="match-empty">This user has no public lists.</p>'
    cards = ""
    for lst in lists:
        href = '/lookup?username=' + _html.escape(username) + '&list_id=' + _html.escape(str(lst["id"]))
        description_html = ('<div class="match-card-comment">' + _html.escape(lst["description"]) + '</div>') if lst.get("description") else ""
        cards += (
            '<a href="' + href + '" class="match-card">'
            '<div class="match-card-art">'
            '<div class="match-card-placeholder">' + _assets.VINYL_PLACEHOLDER_SVG + '</div>'
            '<div class="match-card-art-label">' + _html.escape(lst["name"]) + '</div>'
            '</div>'
            '<div class="match-card-body">'
            '<div class="match-card-title">' + _html.escape(lst["name"]) + '</div>'
            + description_html +
            '</div>'
            '</a>'
        )
    return '<div class="match-grid">' + cards + '</div>'
