import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
import threading
import collections
import re
import json
import html as _html
collections.Callable = collections.abc.Callable

_list_lock = threading.Lock()
from helper.common import API_HEADERS as _HEADERS

# Discogs Price Checker Module
# Takes a public Discogs store inventory and returns pricing information on other listings on the market.

## Classes ##

class CloudflareBlockedError(Exception):
    pass

def _is_cf_blocked(resp):
    if resp.status_code in (403, 503):
        return 'cloudflare' in resp.text.lower()
    if resp.status_code == 200:
        text = resp.text.lower()
        return 'cloudflare' in text and any(m in text for m in ('cf-browser-verification', 'just a moment', 'sorry, you have been blocked'))
    return False

class FormattedEntry: # Formatted marketplace entry for a single release and its listings

    def __init__(self,title,url,imgUrl,listings,place,total,lastSold,daysAgo,yearsAgo=None,index=0,price_badges="",listing_ids=None,reprice_data=None):
        self.title = title
        self.url = url
        self.imgUrl = imgUrl
        self.listings = listings
        self.place = place
        self.total = total
        self.lastSold = lastSold
        self.daysAgo = daysAgo
        self.yearsAgo = yearsAgo
        self.index = index
        self.price_badges = price_badges
        self.listing_ids = listing_ids if listing_ids is not None else []
        self.reprice_data = reprice_data if reprice_data is not None else []

## Get ##

# Given a seller username, returns a list of the releases in their inventory and their item ids.
def get_inventory_ids(username, scraper, auth=None):

    API_URL = "https://api.discogs.com/users/{0}/inventory".format(username)

    new_list = []
    seen_ids = {}  # release_id -> index in new_list
    page = 1

    while True:
        resp = scraper.get(API_URL, headers=_HEADERS, params={"page": page, "per_page": 100, "sort": "price", "sort_order": "asc", "status": "For Sale"}, auth=auth, timeout=20)

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

# Given username and item_id, scrapes marketplace for listings and stores them in provided list.
def get_listings(scraper, inventory_list, sorted_inventory_list, username, release_title, item_id, thumbnail_url, listing_ids, index):

    count, your_place, total = 0, 0, 0
    listings = []

    URL = "https://www.discogs.com/sell/release/{0}?ships_from=United+States&sort=price%2Casc".format(item_id)
    _resp = scraper.get(URL, timeout=20)
    if _is_cf_blocked(_resp):
        raise CloudflareBlockedError()
    html = _resp.content
    soup = BeautifulSoup(html, 'html.parser')

    last_sold, days_ago, years_ago = "", None, None
    last_ul = soup.find("ul", class_="last")
    if last_ul:
        a = last_ul.find("a")
        if a:
            last_sold = a.text.strip()
            try:
                delta = (date.today() - datetime.strptime(last_sold, "%d %b %y").date()).days
                if 0 <= delta <= 10:
                    days_ago = delta
                elif delta >= 365:
                    years_ago = delta // 365
            except ValueError:
                pass

    if soup.find("table", class_="mpitems"):
        listings = soup.find("table", class_="mpitems").find_all("tr", class_="shortcut_navigable")
        total = (soup.find("strong", class_="pagination_total").text.split(" of "))[-1]
    elif soup.find("title").text.find("Page is Unavailable"):
        print("get_listings_error: page_unavailable: {0}".format(release_title))
    else:
        print("get_listings_error: {0}: {1}".format(release_title,html))

    if not thumbnail_url:
        tc = soup.find(class_="thumbnail_center")
        if tc:
            img = tc.find("img")
            if img:
                thumbnail_url = img.get("src", "")

    # First pass: build formatted listings and collect user copies (condition -> [price, ...])
    user_copies = {}  # condition_key -> [price_float, ...]
    user_listing_details = []  # (listing_id, price_float, condition_key) for reprice data
    formatted_listings = ""
    for listing in listings:
        count += 1
        if is_user(username, listing):
            ckey = _get_condition_key(listing)
            pfloat = _parse_price_float(listing)
            if ckey and pfloat is not None:
                user_copies.setdefault(ckey, []).append(pfloat)
            if your_place == 0:
                your_place = count
            scraped_listing_id = ""
            a_title = listing.find("a", class_="item_description_title")
            if a_title:
                m = re.search(r'/sell/item/(\d+)', a_title.get("href", ""))
                if m:
                    scraped_listing_id = m.group(1)
            if scraped_listing_id and ckey and pfloat is not None:
                user_listing_details.append((scraped_listing_id, pfloat, ckey))
            if scraped_listing_id:
                formatted_listings += '<mark><a href="https://www.discogs.com/sell/item/{0}" target="_blank">{1} (You)</a></mark><br>'.format(scraped_listing_id, get_price(listing))
            else:
                formatted_listings += "<mark>{0} (You)</mark><br>".format(get_price(listing))
        elif check_scam(listing):
            formatted_listings += "{0} (SCAM)<br>".format(get_price(listing))
        else:
            formatted_listings += "{0}<br>".format(get_price(listing))

    # Second pass: find the minimum price per condition pair across all listings
    condition_cheapest = {}  # condition_key -> (min_price, is_user_listing)
    if user_copies:
        for listing in listings:
            ckey = _get_condition_key(listing)
            if ckey not in user_copies:
                continue
            pfloat = _parse_price_float(listing)
            if pfloat is None:
                continue
            current = condition_cheapest.get(ckey)
            if current is None or pfloat < current[0]:
                condition_cheapest[ckey] = (pfloat, bool(is_user(username, listing)))

    # Compute CHEAPEST / OVERPRICED badges for each user condition pair
    price_badges_html = ""
    for ckey, user_prices in user_copies.items():
        user_min = min(user_prices)
        if ckey not in condition_cheapest:
            price_badges_html += '<span class="card-cheapest-badge">{0} CHEAPEST</span>'.format(ckey)
            continue
        cheapest_price, cheapest_is_user = condition_cheapest[ckey]
        if cheapest_is_user or user_min <= cheapest_price:
            price_badges_html += '<span class="card-cheapest-badge">{0} CHEAPEST</span>'.format(ckey)
        else:
            pct = (user_min - cheapest_price) / cheapest_price * 100
            if pct > 0:
                price_badges_html += (
                    '<span class="card-overpriced-pct">+{1:.0f}%</span>'
                    '<span class="card-overpriced-badge">{0} OVERPRICED</span>'
                ).format(ckey, pct)

    reprice_data = []
    for lid, sprice, ckey in user_listing_details:
        if ckey not in condition_cheapest:
            continue
        cheapest_price, cheapest_is_user = condition_cheapest[ckey]
        if cheapest_is_user or sprice <= cheapest_price:
            continue
        reprice_data.append({
            "id": lid,
            "seller_price": round(sprice, 2),
            "cheapest_price": round(cheapest_price, 2),
            "condition": ckey
        })

    entry = FormattedEntry(release_title,URL,thumbnail_url,formatted_listings,your_place,total,last_sold,days_ago,years_ago,index,price_badges_html,listing_ids,reprice_data)
    inventory_list[index] = entry
    with _list_lock:
        if your_place > 0:
            if your_place < 10:
                (sorted_inventory_list[your_place - 1]).append(entry)
            else:
                sorted_inventory_list[9].append(entry)

    return

# Gets the price of a provided listing.
def get_price(listing):

    try:
        item_condition = listing.find("p", class_="item_condition").text
        formatted_condition = format_condition(item_condition)

        if listing.find(string="New seller"):
            return "{0} {1} (New)".format(listing.find("span", class_="converted_price").text.strip(), formatted_condition)
        else:
            return "{0} {1}".format(listing.find("span", class_="converted_price").text.strip(), formatted_condition)

    except AttributeError:
        return "n/a"


## Helper ##

def _entry_badges(entry):
    badges = []
    if entry.daysAgo is not None:
        badges.append('recent')
    if getattr(entry, 'yearsAgo', None) is not None:
        badges.append('old')
    try:
        t = int(str(entry.total).replace(',', '').strip())
        if t == 1:
            badges.extend(['lowest', 'low'])
        elif t < 4:
            badges.append('low')
        elif t > 9:
            badges.extend(['highest', 'high'])
        elif t > 4:
            badges.append('high')
    except (ValueError, TypeError):
        pass
    pb = getattr(entry, 'price_badges', '')
    if 'card-cheapest-badge' in pb:
        badges.append('cheapest')
    if 'card-overpriced-badge' in pb:
        badges.append('overpriced')
    return ' '.join(badges)

def ordinal(n):
    if 11 <= (n % 100) <= 13:
        return '{0}th'.format(n)
    return '{0}{1}'.format(n, {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th'))

## Helper Functions ##

# format_condition
# is_user
# check_scam

# Formats the item condition to (Media/Sleeve).
def format_condition(item_condition):

    media = (item_condition.split("("))[1].split(")")[0]
    try:
        sleeve = (item_condition.split("("))[2].split(")")[0]

    except IndexError:
        return "({0})".format(media.split(" or")[0])

    media = media.split(" or")[0]
    sleeve = sleeve.split(" or")[0]

    return "({0}/{1})".format(media, sleeve)

# Checks if a marketplace listing matches the provided username.
def is_user(username, listing):

    return listing.find(string=username)

# Checks if a listing is a scam (has 0.0% seller rating).
def check_scam(listing):

    return listing.find(string="0.0%")

# Parses condition key (e.g. "(VG+/VG+)") from a listing without side effects.
def _get_condition_key(listing):
    try:
        text = listing.find("p", class_="item_condition").text
        parts = text.split("(")
        media = parts[1].split(")")[0].split(" or")[0].strip()
        try:
            sleeve = parts[2].split(")")[0].split(" or")[0].strip()
            return "({0}/{1})".format(media, sleeve)
        except IndexError:
            return "({0})".format(media)
    except (AttributeError, IndexError):
        return None

# Parses the converted price as a float from a listing.
def _parse_price_float(listing):
    try:
        price_text = listing.find("span", class_="converted_price").text.strip()
        return float(re.sub(r'[^\d.]', '', price_text))
    except (AttributeError, ValueError):
        return None


## Reprice ##

def reprice_listings(listings, auth):
    """Reprice a batch of the signed-in user's marketplace listings.

    For each listing: fetch its current data, compute the new price (an explicit
    ``custom_price`` if supplied, otherwise undercut the cheapest competitor),
    then POST the update. Returns a per-listing result list. ``auth`` is the
    caller's OAuth1 object; the route is responsible for authenticating the user.
    """
    results = []
    headers = {"User-Agent": "DiscogsToolkitApp/1.0"}

    def _throttle(resp):
        try:
            remaining = int(resp.headers.get("X-Discogs-Ratelimit-Remaining", 20))
            if remaining < 10:
                time.sleep(2)
        except (ValueError, TypeError):
            pass

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

        get_resp = requests.get(base_url, headers=headers, auth=auth)
        _throttle(get_resp)

        if get_resp.status_code != 200:
            results.append({"id": lid, "status": "error", "message": "GET failed: HTTP {}".format(get_resp.status_code)})
            continue

        ld = get_resp.json()
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

        post_resp = requests.post(base_url, headers=headers, auth=auth, json=post_body)
        _throttle(post_resp)

        if post_resp.status_code in (200, 204):
            results.append({"id": lid, "status": "success", "old_price": old_price, "new_price": final_price, "shipping": shipping})
        else:
            results.append({"id": lid, "status": "error", "message": "POST failed: HTTP {} — {}".format(post_resp.status_code, post_resp.text[:200])})

    return results
