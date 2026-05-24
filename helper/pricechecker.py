from bs4 import BeautifulSoup
from datetime import date, datetime
import threading
import collections
import re
collections.Callable = collections.abc.Callable

_list_lock = threading.Lock()

# Discogs Price Checker Module
# Takes a public Discogs store inventory and returns pricing information on other listings on the market.

## Classes ##

from helper.models import FormattedEntry
from helper.discogs_client import get_inventory_ids, reprice_listings, CloudflareBlockedError, is_cf_blocked as _is_cf_blocked

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
