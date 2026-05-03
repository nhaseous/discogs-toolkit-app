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

    def __str__(self):
        if self.imgUrl:
            img_html = (
                '<a href="{0}" class="card-thumb-link">'
                '<img class="card-thumb" src="{1}" alt="">'
                '</a>'
            ).format(self.url, self.imgUrl)
        else:
            img_html = (
                '<a href="{0}" class="card-thumb-link card-thumb-link--placeholder" '
                'aria-label="No cover image">'
                '<svg class="card-thumb-placeholder-icon" viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="1.2">'
                '<circle cx="12" cy="12" r="10"/>'
                '<circle cx="12" cy="12" r="3.5"/>'
                '<circle cx="12" cy="12" r="0.8" fill="currentColor" stroke="none"/>'
                '</svg>'
                '</a>'
            ).format(self.url)
        if self.daysAgo is not None:
            label = "{0} day ago".format(self.daysAgo) if self.daysAgo == 1 else "{0} days ago".format(self.daysAgo)
            recency = '<span class="isrecent-badge">RECENT</span> <span class="card-recency-badge">{0}</span> &middot; '.format(label)
        elif self.yearsAgo is not None:
            label = "{0} year ago".format(self.yearsAgo) if self.yearsAgo == 1 else "{0} years ago".format(self.yearsAgo)
            recency = '<span class="card-old-badge">OLD</span> <span class="card-recency-badge">{0}</span> &middot; '.format(label)
        else:
            recency = ""
        last_sold_text = 'Last sold: {0}'.format(self.lastSold) if self.lastSold else 'Last sold: ---'
        last_sold_html = '{0}{1}'.format(recency, last_sold_text)
        badges = set(_entry_badges(self).split())
        if 'lowest' in badges:
            low_badge = ' &middot; <span class="card-low-badge card-low-badge--lowest">LOWEST</span>'
        elif 'low' in badges:
            low_badge = ' &middot; <span class="card-low-badge">LOW</span>'
        elif 'highest' in badges:
            low_badge = ' &middot; <span class="card-high-badge card-high-badge--highest">HIGHEST</span>'
        elif 'high' in badges:
            low_badge = ' &middot; <span class="card-high-badge">HIGH</span>'
        else:
            low_badge = ''
        return (
            '<div class="card-inner">'
            '<div class="card-title"><a href="{0}">{1}</a></div>'
            '<div class="card-listings">{2}</div>'
            '<div class="card-total">'
            '<span>Total listings: {3}{6}</span>'
            '<span class="card-last-sold">{5}</span>'
            '</div>'
            '</div>'
            '{4}'
        ).format(self.url, self.title, self.listings, self.total, img_html, last_sold_html, low_badge)

## Get ##

# Given a seller username, returns a list of the releases in their inventory and their item ids.
def get_inventory_ids(username, scraper, auth=None):

    API_URL = "https://api.discogs.com/users/{0}/inventory".format(username)

    new_list = []
    seen_ids = {}  # release_id -> index in new_list
    page = 1

    while True:
        resp = scraper.get(API_URL, headers=_HEADERS, params={"page": page, "per_page": 100, "sort": "price", "sort_order": "asc", "status": "For Sale"}, auth=auth)

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
    html = scraper.get(URL).content
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


## Print ##

def _item_id(entry):
    return entry.url.split('/sell/release/')[1].split('?')[0]

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

# Prints unsorted inventory list.
def print_list(unsorted_inventory_list):

    output = ""
    for count, entry in enumerate(unsorted_inventory_list, 1):
        item_id = _item_id(entry)
        place_html = '<span>({0})</span>'.format(entry.place) if entry.place else ''
        price_badges = getattr(entry, 'price_badges', '')
        reprice_data = getattr(entry, 'reprice_data', [])
        reprice_attr = ' data-reprice="{0}"'.format(_html.escape(json.dumps(reprice_data))) if reprice_data else ''
        listing_ids = getattr(entry, 'listing_ids', [])
        listing_ids_attr = ' data-listing-ids="{0}"'.format(_html.escape(json.dumps(listing_ids))) if listing_ids else ''
        title_attr = ' data-title="{0}"'.format(_html.escape(entry.title)) if entry.title else ''
        thumb_attr = ' data-thumb="{0}"'.format(_html.escape(entry.imgUrl)) if entry.imgUrl else ''
        output += (
            '<div class="result-card" id="card-{0}" data-badges="{3}"{6}{7}{8}{9}>'
            '<div class="card-number"><span>#{1}</span><div class="card-number-right">{4}{5}</div></div>'
            '{2}'
            '</div>'
        ).format(item_id, count, entry, _entry_badges(entry), price_badges, place_html, reprice_attr, listing_ids_attr, title_attr, thumb_attr)
    return output

# Prints a sorted inventory list.
def print_sorted_list(sorted_inventory_list):

    active_indices = [i for i in range(len(sorted_inventory_list)) if sorted_inventory_list[i]]

    summary_rows = ""
    for index in active_indices:
        count = len(sorted_inventory_list[index])
        summary_rows += '<a href="#place-{0}" class="place-summary-link">{1}</a>: {2}<br>'.format(index + 1, ordinal(index + 1), count)
    summary = (
        '<div class="place-summary">'
        '<div class="place-summary-title">Place Summary</div>'
        '{0}'
        '</div>'
    ).format(summary_rows) if summary_rows else ""

    cards = ""
    item_count = 0
    for pos, index in enumerate(active_indices):
        place_num = index + 1
        entry_count = len(sorted_inventory_list[index])

        prev_btn = (
            '<a href="#place-{0}" class="place-nav-btn">&#8592; Prev</a>'.format(active_indices[pos - 1] + 1)
            if pos > 0 else ""
        )
        next_btn = (
            '<a href="#place-{0}" class="place-nav-btn">Next &#8594;</a>'.format(active_indices[pos + 1] + 1)
            if pos < len(active_indices) - 1 else ""
        )

        cards += (
            '<div class="sort-group-header" id="place-{0}">'
            '<span>{1} Place &mdash; {2} listing{3}</span>'
            '<span class="place-nav-buttons">{4}{5}</span>'
            '</div>'
        ).format(place_num, ordinal(place_num), entry_count, "s" if entry_count != 1 else "", prev_btn, next_btn)

        for entry in sorted(sorted_inventory_list[index], key=lambda e: e.index):
            item_count += 1
            item_id = _item_id(entry)
            place_html = '<span>({0})</span>'.format(entry.place) if entry.place else ''
            price_badges = getattr(entry, 'price_badges', '')
            reprice_data = getattr(entry, 'reprice_data', [])
            reprice_attr = ' data-reprice="{0}"'.format(_html.escape(json.dumps(reprice_data))) if reprice_data else ''
            listing_ids = getattr(entry, 'listing_ids', [])
            listing_ids_attr = ' data-listing-ids="{0}"'.format(_html.escape(json.dumps(listing_ids))) if listing_ids else ''
            title_attr = ' data-title="{0}"'.format(_html.escape(entry.title)) if entry.title else ''
            thumb_attr = ' data-thumb="{0}"'.format(_html.escape(entry.imgUrl)) if entry.imgUrl else ''
            cards += (
                '<div class="result-card" id="card-{0}" data-badges="{3}"{6}{7}{8}{9}>'
                '<div class="card-number"><span>#{1}</span><div class="card-number-right">{4}{5}</div></div>'
                '{2}'
                '</div>'
            ).format(item_id, item_count, entry, _entry_badges(entry), price_badges, place_html, reprice_attr, listing_ids_attr, title_attr, thumb_attr)

    scroll_script = (
        '<script>'
        'document.querySelectorAll(".place-nav-btn, .place-summary-link").forEach(function(link) {'
        '    link.addEventListener("click", function(e) {'
        '        e.preventDefault();'
        '        var id = this.getAttribute("href").slice(1);'
        '        var el = document.getElementById(id);'
        '        if (!el) return;'
        '        el.style.position = "static";'
        '        var top = el.getBoundingClientRect().top + window.scrollY;'
        '        el.style.position = "";'
        '        window.scrollTo({ top: top, behavior: "smooth" });'
        '    });'
        '});'
        'document.addEventListener("click", function(e) {'
        '    var item = e.target.closest("a.mosaic-item");'
        '    if (!item) return;'
        '    e.preventDefault();'
        '    var id = item.getAttribute("href").slice(1);'
        '    var el = document.getElementById(id);'
        '    if (!el) return;'
        '    var top = el.getBoundingClientRect().top + window.scrollY;'
        '    var hdr = document.querySelector(".sort-group-header");'
        '    var hdrOffset = hdr ? hdr.getBoundingClientRect().height : 0;'
        '    var mosaicEl = document.getElementById("results-mosaic");'
        '    var mosaicOffset = (mosaicEl && getComputedStyle(mosaicEl).display !== "none")'
        '        ? mosaicEl.getBoundingClientRect().height + 26 : 10;'
        '    window.scrollTo({ top: top - hdrOffset - mosaicOffset, behavior: "smooth" });'
        '});'
        '</script>'
    )

    return '<div class="sorted-results">' + summary + cards + '</div>' + scroll_script


# Prints a mosaic of all scraped thumbnails above results.
def print_mosaic(inventory_list):

    items = ""
    for entry in inventory_list:
        if not entry or not entry.imgUrl:
            continue
        item_id = _item_id(entry)
        items += (
            '<a href="#card-{0}" class="mosaic-item">'
            '<img src="{1}" alt="" class="mosaic-thumb">'
            '</a>'
        ).format(item_id, entry.imgUrl)

    def _total_int(e):
        try:
            return int(str(e.total).replace(',', '').strip())
        except (ValueError, TypeError):
            return None

    recent_count   = sum(1 for e in inventory_list if e and e.daysAgo is not None)
    old_count      = sum(1 for e in inventory_list if e and getattr(e, 'yearsAgo', None) is not None)
    low_count      = sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) < 4)
    lowest_count   = sum(1 for e in inventory_list if e and _total_int(e) == 1)
    high_count     = sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) > 4)
    highest_count  = sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) > 9)
    cheapest_count = sum(1 for e in inventory_list if e and 'card-cheapest-badge' in getattr(e, 'price_badges', ''))
    overpriced_count = sum(1 for e in inventory_list if e and 'card-overpriced-badge' in getattr(e, 'price_badges', ''))

    badge_summary = (
        '<span class="isrecent-badge inv-count-badge" data-filter="recent" data-tooltip="Last sold within the past 10 days">RECENT</span> {0}'
        ' &ensp;'
        '<span class="card-old-badge inv-count-badge" data-filter="old" data-tooltip="Last sold over a year ago">OLD</span> {1}'
        ' &ensp;'
        '<span class="card-low-badge card-low-badge--lowest inv-count-badge" data-filter="lowest" data-tooltip="Only listing on the market">LOWEST</span> {3}'
        ' &ensp;'
        '<span class="card-low-badge inv-count-badge" data-filter="low" data-tooltip="3 marketplace listings or less">LOW</span> {2}'
        ' &ensp;'
        '<span class="card-high-badge inv-count-badge" data-filter="high" data-tooltip="5 marketplace listings or more">HIGH</span> {4}'
        ' &ensp;'
        '<span class="card-high-badge card-high-badge--highest inv-count-badge" data-filter="highest" data-tooltip="10 marketplace listings or more">HIGHEST</span> {5}'
        ' &ensp;'
        '<span class="card-cheapest-badge inv-count-badge" data-filter="cheapest" data-tooltip="Cheapest listing for its condition">CHEAPEST</span> {6}'
        ' &ensp;'
        '<span class="card-overpriced-badge inv-count-badge" data-filter="overpriced" data-tooltip="More than 10% above cheapest for its condition">OVERPRICED</span> {7}'
    ).format(recent_count, old_count, low_count, lowest_count, high_count, highest_count, cheapest_count, overpriced_count)

    count_div = (
        '<div class="badge-count">'
        '<span>{0}</span>'
        '</div>'
    ).format(badge_summary)

    if not items:
        return count_div
    return '<div id="results-mosaic" class="mosaic">{0}</div>{1}'.format(items, count_div)


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


## State ##

# # Pickles an inventory list as a save state in a bin file.
# def save_state(inventory_list):

#     with open("state.bin", "wb") as f:
#         pickle.dump(inventory_list, f)

# # Loads a pickled inventory list from a bin file.
# def load_state():

#     with open("state.bin", "rb") as f:
#         try:
#             pickled_list = pickle.load(f)
#             return pickled_list
#         except pickle.UnpicklingError:
#             return []
