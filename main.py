from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, render_template
from helper import pricechecker, matcher, lookup as lookup_helper, records as records_helper
from concurrent.futures import ThreadPoolExecutor, as_completed
import cloudscraper, time, html as _html, re as _re, math as _math, requests as _requests
from datetime import datetime
import assets
# Main

app = Flask(__name__)

try:
    _records_data = records_helper.load_all()
except Exception:
    _records_data = records_helper.empty_data()

@app.context_processor
def _inject_globals():
    return {'logo_svg': assets.LOGO_SVG, 'discogs_logo_svg': assets.DISCOGS_LOGO_SVG}

# Routes

## Landing Page ##

@app.route("/")
def landingpage():
    return render_template('landing.html',
        content=(
        '<section class="hero">'
        '<div class="hero-eyebrow">Discogs Toolkit</div>'
        '<h1 class="hero-title">Tools for <em>crate diggers</em>, collectors, and sellers.</h1>'
        '<p class="hero-subtitle">A small set of utilities for marketplace research '
        'and collection matching for the Discogs platform. Dig through the shelves below.</p>'
        '<br><p class="hero-subtitle">\ Dev Notes \<br>'
        '01 &middot; Price Checker doesn\'t work when running on the cloud/web because webscraping gets blocked by Cloudflare. Works locally.<br>'
        '02 &middot; All good.<br>'
        '03 &middot; Displaying user lists doesn\'t work for the same issue with webscraping and Cloudflare.<br>'
        '( Report bugs to @curefortheitch on Instagram, Discogs, etc. )</p>'
        '</section>'
        '<div class="tool-grid-wrap">'
        '<div class="tool-grid">'
        '<a href="/pricechecker" class="tool-card">'
        '<div class="tool-card-label">01 &middot; Marketplace</div>'
        '<h3 class="tool-card-title">Price Checker</h3>'
        '<p class="tool-card-desc">See where a seller\'s listings rank against the rest of the marketplace.</p>'
        '</a>'
        '<a href="/matcher" class="tool-card">'
        '<div class="tool-card-label">02 &middot; Collections</div>'
        '<h3 class="tool-card-title">Collection Matcher</h3>'
        '<p class="tool-card-desc">Find overlap between one user\'s collection and another user\'s wantlist.</p>'
        '</a>'
        '<a href="/lookup" class="tool-card">'
        '<div class="tool-card-label">03 &middot; Collections</div>'
        '<h3 class="tool-card-title">User Lookup</h3>'
        '<p class="tool-card-desc">Browse any user\'s full collection and wantlist as well as any lists they have made.</p>'
        '</a>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '<div class="tool-slot"></div>'
        '</div>'
        '</div>'
        ),
    )

## Price Checker Module ##

@app.route("/pricechecker")
def pricecheckerpage():

    seller = request.args.get("seller", "")
    output,loadtime = "",""
    show_platter = False
    inventory_count = 0

    if seller != "":
        start_time = time.time()
        try:
            sorted_inventory_list = [ [] for _ in range(10) ]

            print("Loading inventory...")

            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
            release_titles_ids = pricechecker.get_inventory_ids(seller, scraper)
            inventory_count = len(release_titles_ids)
            inventory_list = [None] * inventory_count

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(pricechecker.get_listings, scraper, inventory_list,
                                    sorted_inventory_list, seller, release[0], release[1], release[2], release[3], i)
                    for i, release in enumerate(release_titles_ids)
                ]
                for f in as_completed(futures):
                    f.result()

            mosaic = pricechecker.print_mosaic(inventory_list)
            if request.args.get("sort","") == "yes":
                results = mosaic + pricechecker.print_sorted_list(sorted_inventory_list)
            else:
                results = mosaic + pricechecker.print_list(inventory_list)
            output = '<div id="results-area"><div id="results-main">' + results + '</div></div>'
            show_platter = True

        except AttributeError:
            output = "No user found."

        end_time = time.time()
        seller_meta = "Seller: " + seller
        loadtime = "Search time: {0} seconds".format(round(end_time-start_time,2))
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

    inv_noun = "release" if inventory_count == 1 else "releases"
    meta = '<div class="meta"><span><b>{0}</b> &nbsp;&middot;&nbsp; {1} {2}</span><span>{3} &nbsp;&#124;&nbsp; {4}</span></div>'.format(seller_meta, inventory_count, inv_noun, loadtime, searched_at) if loadtime else ""

    seller_val = seller.replace('"', '&quot;')
    sort_checked = ' checked' if request.args.get("sort","") == "yes" else ''

    pc_header = (
        '<div class="page-header">'
        '<div class="page-eyebrow">Marketplace</div>'
        '<h2>Price <em>Checker</em></h2>'
        '</div>'
    )
    pc_form = (
        '<form id="pc-form" class="search-bar" action="" method="get" role="search">'
        '<span class="search-bar-icon" aria-hidden="true">' + assets.SEARCH_ICON_SVG + '</span>'
        '<div class="search-bar-segment">'
        '<label class="search-bar-label" for="seller">Seller</label>'
        '<input type="text" id="seller" name="seller" placeholder="Discogs username" '
        'autocomplete="off" value="' + seller_val + '">'
        '</div>'
        '<div class="search-bar-divider"></div>'
        '<label class="search-bar-toggle" for="sort">'
        '<input type="checkbox" id="sort" name="sort" value="yes"' + sort_checked + '>'
        '<span>Sort by place</span>'
        '</label>'
        '<button type="submit" class="search-bar-submit">Search</button>'
        '</form>'
        '<div id="spinner"><span id="spinner-icon"></span>Pulling listings&hellip;</div>'
    )
    return render_template('pricechecker.html',
        content=(pc_form + pc_header + meta + output) if seller else (pc_header + pc_form),
        content_class='has-results' if seller else '',
        show_platter=show_platter,
        title='Price Checker'
    )

@app.route("/reprice", methods=["POST"])
def repricepage():
    from helper.common import API_HEADERS as _pc_headers
    data = request.get_json()
    if not data:
        return {"error": "No JSON body"}, 400

    listings = data.get("listings", [])
    results = []
    headers = dict(_pc_headers)

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

        pct = (seller_price - cheapest_price) / cheapest_price * 100 if cheapest_price > 0 else 0
        new_price = seller_price * 0.9 if pct > 10 else cheapest_price - 0.5
        new_price = round(new_price, 2)

        base_url = "https://api.discogs.com/marketplace/listings/{}".format(lid)

        get_resp = _requests.get(base_url, headers=headers)
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

        post_resp = _requests.post(base_url, headers=headers, json=post_body)
        _throttle(post_resp)

        if post_resp.status_code in (200, 204):
            results.append({"id": lid, "status": "success", "old_price": old_price, "new_price": final_price, "shipping": shipping})
        else:
            results.append({"id": lid, "status": "error", "message": "POST failed: HTTP {} — {}".format(post_resp.status_code, post_resp.text[:200])})

    return {"results": results}


@app.route("/refresh_card", methods=["POST"])
def refresh_card():
    data = request.get_json()
    seller = data.get("seller", "")
    release_id = str(data.get("release_id", ""))
    listing_ids = data.get("listing_ids", [])
    title = data.get("title", "")
    thumbnail = data.get("thumbnail", "")
    if not seller or not release_id:
        return {"error": "missing params"}, 400
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'android', 'desktop': False})
    inventory_list = [None]
    sorted_inventory_list = [[] for _ in range(10)]
    pricechecker.get_listings(scraper, inventory_list, sorted_inventory_list, seller, title, release_id, thumbnail, listing_ids, 0)
    entry = inventory_list[0]
    if entry is None:
        return {"error": "scrape failed"}, 500
    price_badges = getattr(entry, 'price_badges', '')
    reprice_data = getattr(entry, 'reprice_data', [])
    place_html = '<span>({0})</span>'.format(entry.place) if entry.place else ''
    return {
        "inner_html": str(entry),
        "price_badges": price_badges,
        "place_html": place_html,
        "data_badges": pricechecker._entry_badges(entry),
        "reprice_data": reprice_data,
    }


## Matcher Module ##

@app.route("/matcher")
def matcherpage():

    collection_user = request.args.get("collection", "")
    wantlist_user = request.args.get("wantlist", "")
    exact = request.args.get("exact", "") == "yes"
    output,loadtime = "",""

    if collection_user != "" and wantlist_user != "" :
        start_time = time.time()
        try:
            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})

            collection = matcher.get_collection(collection_user, scraper)
            wantlist = matcher.get_wantlist(wantlist_user, scraper)

            lookup_field = "key" if exact else "easy_key"
            wantlist_set = {w["strict"] if exact else w["easy"] for w in wantlist}
            collection_by_key = {item[lookup_field]: item for item in collection}
            matches = sorted(
                [collection_by_key[k] for k in collection_by_key if k in wantlist_set],
                key=lambda x: x["artist"].lower()
            )

            mosaic_items = ""
            match_lines = ""
            for m in matches:
                fmt_parts = ", ".join(p for p in [m.get("format_descriptions", ""), m.get("format_text", "")] if p)
                fmt_suffix = " ({0})".format(_html.escape(fmt_parts)) if fmt_parts else ""
                match_lines += "<b>" + _html.escape(m["artist"]) + "</b>" + " - " + _html.escape(m["title"]) + " &nbsp;&middot" + "<i>" + fmt_suffix + "</i>" + "<br>"
                if m.get("thumb"):
                    mosaic_items += '<span class="mosaic-item"><img src="{0}" alt="" class="mosaic-thumb"></span>'.format(m["thumb"])
            mosaic = '<div id="matcher-mosaic" class="mosaic">{0}</div>'.format(mosaic_items) if mosaic_items else ""

            matches_count = len(matches)
            matches_count_text = "Matches ({0})".format(matches_count)

            summary = (
                '<div class="result-card">'
                '<div class="card-title card-title--label">Results</div>'
                '<div class="card-listings">'
                'Collection: <b>{1}</b> ({0} items)<br>'
                'Wantlist: <b>{3}</b> ({2} items)<br>'
                '<br><b>Matches: {4} items</b><br>'
                + ('<br>' + match_lines if match_lines else '') +
                '</div>'
                '</div>'
            ).format(len(collection), collection_user, len(wantlist), wantlist_user, matches_count)

            tabs_html = (
                '<div class="lookup-tabs-row">'
                '<div class="lookup-tabs">'
                '<button class="lookup-tab active" data-tab="matches" data-count-text="' + _html.escape(matches_count_text) + '">' + _html.escape(matches_count_text) + '</button>'
                '</div>'
                '<div class="lookup-pagination" id="lookup-pagination">'
                '<button class="pag-expand-btn" id="pag-expand-btn" type="button" title="Expand all cards">'
                '<span class="pag-eye pag-eye--closed">' + assets.EYE_CLOSED_SVG + '</span>'
                '<span class="pag-eye pag-eye--open">' + assets.EYE_OPEN_SVG + '</span>'
                '</button>'
                '<div class="pag-select" id="pag-size-wrap">'
                '<button class="pag-select-btn" id="pag-size-btn" type="button">'
                '<span id="pag-size-val">50</span>'
                '<span class="pag-select-caret">&#9662;</span>'
                '</button>'
                '<div class="pag-select-menu" id="pag-size-menu">'
                '<button class="pag-select-opt" type="button" data-value="10">10</button>'
                '<button class="pag-select-opt" type="button" data-value="25">25</button>'
                '<button class="pag-select-opt pag-select-opt--active" type="button" data-value="50">50</button>'
                '<button class="pag-select-opt" type="button" data-value="100">100</button>'
                '</div>'
                '</div>'
                '<div class="pag-divider"></div>'
                '<button class="pag-btn" id="pag-prev">&#8249;</button>'
                '<span class="pag-label" id="pag-label">1 / 1</span>'
                '<button class="pag-btn" id="pag-next">&#8250;</button>'
                '</div>'
                '</div>'
            )

            grid = _render_lookup_grid(matches) if matches else '<p class="match-empty">No matches found.</p>'
            panel_html = '<div id="lookup-panel-matches" class="lookup-panel">' + grid + '</div>'

            output = mosaic + summary + tabs_html + panel_html

        except matcher.RateLimitError:
            output = assets.RATE_LIMIT_NOTICE
        except AttributeError:
            output = "Unable to find a match."

        end_time = time.time()
        loadtime = "Match time: {0} seconds".format(round(end_time-start_time,2))
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")
        collection_meta = "Collection: " + collection_user
        wantlist_meta = "Wantlist: " + wantlist_user

    meta = '<div class="meta"><span><b>{0}</b> &nbsp;&middot;&nbsp; <b>{1}</b></span><span>{2} &nbsp;&#124;&nbsp; {3}</span></div>'.format(collection_meta, wantlist_meta, loadtime, searched_at) if loadtime else ""

    collection_val = collection_user.replace('"', '&quot;')
    wantlist_val = wantlist_user.replace('"', '&quot;')
    exact_checked = ' checked' if exact else ''

    has_results = collection_user != "" and wantlist_user != ""
    matcher_header = (
        '<div class="page-header">'
        '<div class="page-eyebrow">Collections</div>'
        '<h2>Collection <em>Matcher</em></h2>'
        '</div>'
    )
    matcher_form = (
        '<form id="matcher-form" class="search-bar" action="" method="get" role="search">'
        '<span class="search-bar-icon" aria-hidden="true">' + assets.SEARCH_ICON_SVG + '</span>'
        '<div class="search-bar-segment">'
        '<label class="search-bar-label" for="collection">Collection</label>'
        '<input type="text" id="collection" name="collection" placeholder="username" '
        'autocomplete="off" value="' + collection_val + '">'
        '</div>'
        '<div class="search-bar-divider"></div>'
        '<div class="search-bar-segment">'
        '<label class="search-bar-label" for="wantlist">Wantlist</label>'
        '<input type="text" id="wantlist" name="wantlist" placeholder="username" '
        'autocomplete="off" value="' + wantlist_val + '">'
        '</div>'
        '<div class="search-bar-divider"></div>'
        '<label class="search-bar-toggle" for="exact">'
        '<input type="checkbox" id="exact" name="exact" value="yes"' + exact_checked + '>'
        '<span>Exact match</span>'
        '</label>'
        '<button type="submit" class="search-bar-submit">Search</button>'
        '</form>'
        '<div id="spinner"><span id="spinner-icon"></span>Matching&hellip;</div>'
    )
    return render_template('matcher.html',
        content=(matcher_form + matcher_header + meta + output) if has_results else (matcher_header + matcher_form),
        content_class='has-results' if has_results else '',
        show_platter=has_results,
        title='Collection Matcher'
    )

## Lookup Module ##

def _render_lookup_grid(items, show_stats=False, prepend_card=""):
    cards = prepend_card
    for m in items:
        img_src = m.get("cover_image") or m.get("thumb")
        if img_src:
            art = '<img src="{0}" alt="" class="match-card-img">'.format(img_src)
        else:
            art = '<div class="match-card-placeholder">' + assets.VINYL_PLACEHOLDER_SVG + '</div>'
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


def _render_list_index(lists, username):
    if not lists:
        return '<p class="match-empty">This user has no public lists.</p>'
    cards = ""
    for lst in lists:
        href = '/lookup?username=' + _html.escape(username) + '&list_id=' + _html.escape(str(lst["id"]))
        description_html = ('<div class="match-card-comment">' + _html.escape(lst["description"]) + '</div>') if lst.get("description") else ""
        cards += (
            '<a href="' + href + '" class="match-card">'
            '<div class="match-card-art">'
            '<div class="match-card-placeholder">' + assets.VINYL_PLACEHOLDER_SVG + '</div>'
            '<div class="match-card-art-label">' + _html.escape(lst["name"]) + '</div>'
            '</div>'
            '<div class="match-card-body">'
            '<div class="match-card-title">' + _html.escape(lst["name"]) + '</div>'
            + description_html +
            '</div>'
            '</a>'
        )
    return '<div class="match-grid">' + cards + '</div>'


@app.route("/lookup")
def lookuppage():

    username = request.args.get("username", "")
    list_id = request.args.get("list_id", "")
    output, loadtime, searched_at, user_meta, active_count_text = "", "", "", "", ""
    has_results = bool(username)

    if username:
        start_time = time.time()
        scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})

        collection = None
        wantlist = None
        lists = None
        list_releases = None
        user_not_found = False
        rate_limited = False
        collection_error = ""
        wantlist_error = ""
        lists_error = ""

        try:
            try:
                collection = lookup_helper.get_collection(username, scraper)
            except lookup_helper.UserNotFoundError:
                user_not_found = True
            except lookup_helper.CollectionPrivateError:
                collection_error = "This user's collection is not public."

            if not user_not_found:
                try:
                    wantlist = lookup_helper.get_wantlist(username, scraper)
                except lookup_helper.UserNotFoundError:
                    user_not_found = True
                except lookup_helper.WantlistPrivateError:
                    wantlist_error = "This user's wantlist is not public."

            if not user_not_found:
                try:
                    lists = lookup_helper.get_lists(username, scraper)
                except lookup_helper.UserNotFoundError:
                    user_not_found = True
                except lookup_helper.ListPrivateError:
                    lists_error = "This user's lists are not public."

            if list_id and not user_not_found:
                list_releases = lookup_helper.get_list_releases(list_id, scraper)

        except lookup_helper.RateLimitError:
            rate_limited = True

        end_time = time.time()
        loadtime = "Lookup time: {0} seconds".format(round(end_time - start_time, 2))
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")
        user_meta = "User: " + username

        if rate_limited:
            output = assets.RATE_LIMIT_NOTICE
        elif user_not_found:
            output = (
                '<div class="lookup-notice lookup-notice--error">'
                'User <b>' + _html.escape(username) + '</b> was not found on Discogs. '
                'Check the username and try again.'
                '</div>'
            )
        else:
            col_count = len(collection) if collection is not None else 0
            want_count = len(wantlist) if wantlist is not None else 0
            lists_count = len(lists) if lists is not None else 0
            active_tab = "lists" if list_id else "collection"

            def _count_text(n, noun):
                return "{0} {1}{2}".format(n, noun, "" if n == 1 else "s")

            col_count_text   = _count_text(col_count, "item")
            want_count_text  = _count_text(want_count, "item")
            if list_id:
                list_rel_count = len(list_releases) if list_releases else 0
                lists_count_text = _count_text(list_rel_count, "release")
            else:
                lists_count_text = _count_text(lists_count, "list")
            active_count_text = {"collection": col_count_text, "wantlist": want_count_text, "lists": lists_count_text}[active_tab]

            tabs_html = (
                '<div class="lookup-tabs-row">'
                '<div class="lookup-tabs">'
                '<button class="lookup-tab{0}" data-tab="collection" data-count-text="{5}">Collection ({1})</button>'
                '<button class="lookup-tab" data-tab="wantlist" data-count-text="{6}">Wantlist ({2})</button>'
                '<button class="lookup-tab{3}" data-tab="lists" data-count-text="{7}">Lists ({4})</button>'
                '</div>'
                '<div class="lookup-pagination" id="lookup-pagination">'
                '<button class="pag-expand-btn" id="pag-expand-btn" type="button" title="Expand all cards">'
                '<span class="pag-eye pag-eye--closed">' + assets.EYE_CLOSED_SVG + '</span>'
                '<span class="pag-eye pag-eye--open">' + assets.EYE_OPEN_SVG + '</span>'
                '</button>'
                '<div class="pag-select" id="pag-size-wrap">'
                '<button class="pag-select-btn" id="pag-size-btn" type="button">'
                '<span id="pag-size-val">50</span>'
                '<span class="pag-select-caret">&#9662;</span>'
                '</button>'
                '<div class="pag-select-menu" id="pag-size-menu">'
                '<button class="pag-select-opt" type="button" data-value="10">10</button>'
                '<button class="pag-select-opt" type="button" data-value="25">25</button>'
                '<button class="pag-select-opt pag-select-opt--active" type="button" data-value="50">50</button>'
                '<button class="pag-select-opt" type="button" data-value="100">100</button>'
                '</div>'
                '</div>'
                '<div class="pag-divider"></div>'
                '<button class="pag-btn" id="pag-prev">&#8249;</button>'
                '<span class="pag-label" id="pag-label">1 / 1</span>'
                '<button class="pag-btn" id="pag-next">&#8250;</button>'
                '</div>'
                '</div>'
            ).format(
                ' active' if active_tab == 'collection' else '',
                col_count,
                want_count,
                ' active' if active_tab == 'lists' else '',
                lists_count,
                _html.escape(col_count_text),
                _html.escape(want_count_text),
                _html.escape(lists_count_text),
            )

            if collection_error:
                col_content = '<div class="lookup-notice">' + _html.escape(collection_error) + '</div>'
            elif collection:
                col_content = _render_lookup_grid(collection, show_stats=False)
            else:
                col_content = '<p class="match-empty">This collection is empty.</p>'

            if wantlist_error:
                want_content = '<div class="lookup-notice">' + _html.escape(wantlist_error) + '</div>'
            elif wantlist:
                want_content = _render_lookup_grid(wantlist, show_stats=True)
            else:
                want_content = '<p class="match-empty">This wantlist is empty.</p>'

            if list_id:
                back_url = '/lookup?username=' + _html.escape(username)
                back_card_html = (
                    '<a href="' + back_url + '" class="match-card match-card--back">'
                    '<div class="match-card-art">'
                    '<div class="match-card-placeholder">' + assets.BACK_ARROW_SVG + '</div>'
                    '</div>'
                    '</a>'
                )
                if list_releases:
                    lists_content = _render_lookup_grid(list_releases, prepend_card=back_card_html)
                else:
                    lists_content = _render_lookup_grid([], prepend_card=back_card_html) + '<p class="match-empty">This list is empty.</p>'
            elif lists_error:
                lists_content = '<div class="lookup-notice">' + _html.escape(lists_error) + '</div>'
            else:
                lists_content = _render_list_index(lists or [], username)

            col_mosaic_items = "".join(
                '<a class="mosaic-item" href="{1}" target="_blank" rel="noopener noreferrer"><img src="{0}" alt="" class="mosaic-thumb"></a>'.format(m["thumb"], m.get("url", "#"))
                for m in (collection or []) if m.get("thumb")
            )
            want_mosaic_items = "".join(
                '<a class="mosaic-item" href="{1}" target="_blank" rel="noopener noreferrer"><img src="{0}" alt="" class="mosaic-thumb"></a>'.format(m["thumb"], m.get("url", "#"))
                for m in (wantlist or []) if m.get("thumb")
            )
            lists_mosaic_items = "".join(
                '<span class="mosaic-item"><img src="{0}" alt="" class="mosaic-thumb"></span>'.format(m["thumb"])
                for m in (list_releases or []) if m.get("thumb")
            ) if list_id else ""

            col_hidden = ' style="display:none"' if active_tab != 'collection' else ''
            want_hidden = ' style="display:none"'
            lists_hidden = ' style="display:none"' if active_tab != 'lists' else ''

            col_mosaic = '<div id="lookup-mosaic-collection" class="lookup-mosaic mosaic"{1}>{0}</div>'.format(col_mosaic_items, col_hidden) if col_mosaic_items else ""
            want_mosaic = '<div id="lookup-mosaic-wantlist" class="lookup-mosaic mosaic"{1}>{0}</div>'.format(want_mosaic_items, want_hidden) if want_mosaic_items else ""
            lists_mosaic = '<div id="lookup-mosaic-lists" class="lookup-mosaic mosaic"{1}>{0}</div>'.format(lists_mosaic_items, lists_hidden) if lists_mosaic_items else ""
            mosaics_html = '<div class="lookup-mosaic-wrap">' + col_mosaic + want_mosaic + lists_mosaic + '</div>' if (col_mosaic or want_mosaic or lists_mosaic) else ""

            output = (
                mosaics_html +
                tabs_html +
                '<div id="lookup-panel-collection" class="lookup-panel"{0}>'.format(col_hidden) + col_content + '</div>' +
                '<div id="lookup-panel-wantlist" class="lookup-panel"{0}>'.format(want_hidden) + want_content + '</div>' +
                '<div id="lookup-panel-lists" class="lookup-panel"{0}>'.format(lists_hidden) + lists_content + '</div>'
            )

    count_span = ' &nbsp;&middot;&nbsp; <span id="lookup-count">{0}</span>'.format(_html.escape(active_count_text)) if active_count_text else ''
    meta = '<div class="meta"><span><b>{0}</b>{1}</span><span>{2} &nbsp;&#124;&nbsp; {3}</span></div>'.format(user_meta, count_span, loadtime, searched_at) if loadtime else ""

    username_val = username.replace('"', '&quot;')

    lookup_header = (
        '<div class="page-header">'
        '<div class="page-eyebrow">Collections</div>'
        '<h2>User <em>Lookup</em></h2>'
        '</div>'
    )
    lookup_form = (
        '<form id="lookup-form" class="search-bar" action="" method="get" role="search">'
        '<span class="search-bar-icon" aria-hidden="true">' + assets.SEARCH_ICON_SVG + '</span>'
        '<div class="search-bar-segment">'
        '<label class="search-bar-label" for="username">Username</label>'
        '<input type="text" id="username" name="username" placeholder="Discogs username" '
        'autocomplete="off" value="' + username_val + '">'
        '</div>'
        '<button type="submit" class="search-bar-submit">Search</button>'
        '</form>'
        '<div id="spinner"><span id="spinner-icon"></span>Looking up user&hellip;</div>'
    )
    return render_template('lookup.html',
        content=(lookup_form + lookup_header + meta + output) if has_results else (lookup_header + lookup_form),
        content_class='has-results' if has_results else '',
        show_platter=has_results,
        title='User Lookup'
    )


## Records ##

def _fmt_money(val):
    if val is None:
        return ''
    return '${:,.2f}'.format(val)

def _fmt_cost(raw, val):
    if not raw or raw.strip() in ('', '---'):
        return '<span class="rec-free">Free</span>'
    if _re.match(r'^\[\d+(?:\.\d+)?\]$', raw.strip()):
        return _html.escape('${:,.2f}'.format(val)) if val is not None else _html.escape(raw)
    if val is not None:
        return _html.escape('${:,.2f}'.format(val))
    return _html.escape(raw)

_PIE_COLORS = [
    '#c47a50',  # rust
    '#708a50',  # olive
    '#5a7898',  # slate blue
    '#b89858',  # tan/gold
    '#886888',  # muted purple
    '#508888',  # teal
    '#c4a040',  # amber
    '#6a8a70',  # sage
]


def _pie_svg(segments, size=130):
    total = sum(s['value'] for s in segments)
    if not segments or total == 0:
        return ''
    cx = cy = size / 2
    r = size * 0.42
    paths = []
    angle = -_math.pi / 2
    for seg in segments:
        if seg['value'] <= 0:
            continue
        sweep = 2 * _math.pi * seg['value'] / total
        end_angle = angle + sweep
        x1 = cx + r * _math.cos(angle)
        y1 = cy + r * _math.sin(angle)
        x2 = cx + r * _math.cos(end_angle)
        y2 = cy + r * _math.sin(end_angle)
        large_arc = 1 if sweep > _math.pi else 0
        d = 'M {:.2f} {:.2f} L {:.2f} {:.2f} A {:.2f} {:.2f} 0 {} 1 {:.2f} {:.2f} Z'.format(
            cx, cy, x1, y1, r, r, large_arc, x2, y2)
        paths.append('<path d="{}" fill="{}" stroke="var(--bg)" stroke-width="2"/>'.format(
            d, seg['color']))
        angle = end_angle
    return ('<svg viewBox="0 0 {0} {0}" xmlns="http://www.w3.org/2000/svg"'
            ' class="rec-pie-svg">{1}</svg>'.format(size, ''.join(paths)))


def _pie_section(title, segments):
    total = sum(s['value'] for s in segments)
    if not segments or total == 0:
        return ''
    legend_items = ''.join(
        '<div class="rec-pie-legend-item">'
        '<span class="rec-pie-dot" style="background:{color}"></span>'
        '<span class="rec-pie-name">{name}</span>'
        '<span class="rec-pie-pct">{pct:.0f}%</span>'
        '</div>'.format(
            color=seg['color'],
            name=_html.escape(seg['name'] or '—'),
            pct=seg['value'] / total * 100,
        )
        for seg in segments if seg['value'] > 0
    )
    return (
        '<div class="rec-breakdown-section">'
        '<div class="rec-breakdown-title">' + title + '</div>'
        '<div class="rec-pie-wrap">'
        + _pie_svg(segments) +
        '<div class="rec-pie-legend">' + legend_items + '</div>'
        '</div>'
        '</div>'
    )


def _render_records_dashboard(stats):
    def stat_card(label, value, sub='', value_class=''):
        sub_html = '<div class="rec-stat-sub">' + sub + '</div>' if sub else ''
        val_cls = 'rec-stat-value' + (' ' + value_class if value_class else '')
        return (
            '<div class="rec-stat-card">'
            '<div class="rec-stat-label">' + label + '</div>'
            '<div class="' + val_cls + '">' + value + '</div>'
            + sub_html +
            '</div>'
        )

    def sf_row(name, count, primary_val, primary_label, secondary_val=None, secondary_label=None):
        secondary = ''
        if secondary_val is not None:
            secondary = ('<td class="rec-sf-money">' + _fmt_money(secondary_val) + '</td>'
                         '<td class="rec-sf-label">' + secondary_label + '</td>')
        return (
            '<tr>'
            '<td class="rec-sf-name">' + _html.escape(name or '—') + '</td>'
            '<td class="rec-sf-count">' + str(count) + '</td>'
            '<td class="rec-sf-money">' + _fmt_money(primary_val) + '</td>'
            '<td class="rec-sf-label">' + primary_label + '</td>'
            + secondary + '</tr>'
        )

    def breakdown_section(title, tbody_html, wide=False):
        cls = 'rec-breakdown-section' + (' rec-breakdown-section--wide' if wide else '')
        return (
            '<div class="' + cls + '">'
            '<div class="rec-breakdown-title">' + title + '</div>'
            '<table class="rec-breakdown-table"><tbody>' + tbody_html + '</tbody></table>'
            '</div>'
        )

    def dash_group(tab, cards_html, breakdown_html='', active=False):
        style = '' if active else ' style="display:none;opacity:0"'
        return (
            '<div class="rec-dash-group" data-tab-group="' + tab + '"' + style + '>'
            + ('<div class="rec-stat-grid">' + cards_html + '</div>' if cards_html else '')
            + ('<div class="rec-breakdown">' + breakdown_html + '</div>' if breakdown_html else '')
            + '</div>'
        )

    # ── Collection + Inventory group (shared stat grid, per-tab breakdown) ──────
    col_sf_active = [s for s in stats['col_sf_stats'] if s['count']]
    col_breakdown_rows = ''.join(
        sf_row(s['name'], s['count'], s['median_total'], 'median', s['cost_total'], 'spent')
        for s in col_sf_active
    )
    col_pie_segs = [
        {'name': s['name'], 'value': s['count'], 'color': _PIE_COLORS[i % len(_PIE_COLORS)]}
        for i, s in enumerate(col_sf_active)
    ]

    inv_sf_active = [s for s in stats['inv_sf_stats'] if s['count']]
    inv_breakdown_rows = ''.join(
        sf_row(s['name'], s['count'], s['total_total'], 'spent')
        for s in inv_sf_active
    )
    inv_pie_segs = [
        {'name': s['name'], 'value': s['count'], 'color': _PIE_COLORS[i % len(_PIE_COLORS)]}
        for i, s in enumerate(inv_sf_active)
    ]

    col_inv_group = (
        '<div class="rec-dash-group" data-tab-group="col-inv">'
        + '<div class="rec-stat-grid">'
        + stat_card('Collection Value', _fmt_money(stats['col_median_total']),
                    '{0} records'.format(stats['col_count']))
        + stat_card('Collection &middot; Spent', _fmt_money(stats['col_cost_total']),
                    '{0} records'.format(stats['col_count']))
        + stat_card('Inventory &middot; Spent', _fmt_money(stats['inv_total_total']),
                    '{0} records'.format(stats['inv_count']))
        + '</div>'
        + '<div class="rec-breakdown">'
        + '<div class="rec-breakdown-pane" data-breakdown-pane="collection">'
        + ((breakdown_section('Collection', col_breakdown_rows) + _pie_section('Breakdown', col_pie_segs)) if col_breakdown_rows else '')
        + '</div>'
        + '<div class="rec-breakdown-pane" data-breakdown-pane="inventory" style="display:none;opacity:0">'
        + ((breakdown_section('Inventory', inv_breakdown_rows) + _pie_section('Breakdown', inv_pie_segs)) if inv_breakdown_rows else '')
        + '</div>'
        + '</div>'
        + '</div>'
    )

    # ── Sold group ────────────────────────────────────────────────────────────
    net = stats['net']
    net_cls = 'rec-stat-value--pos' if net >= 0 else 'rec-stat-value--neg'
    sold_breakdown_rows = ''.join(
        (
            '<tr>'
            '<td class="rec-sf-name">' + _html.escape(s['name'] or '—') + '</td>'
            '<td class="rec-sf-count">' + str(s['count']) + '</td>'
            '<td class="rec-sf-money">' + _fmt_money(s['sold_for_total']) + '</td>'
            '<td class="rec-sf-label">made</td>'
            '<td class="rec-sf-money">' + _fmt_money(s['cost_total']) + '</td>'
            '<td class="rec-sf-label">spent</td>'
            '<td class="rec-sf-money ' + ('rec-stat-value--pos' if s['net'] >= 0 else 'rec-stat-value--neg') + '">'
            + _fmt_money(s['net']) + '</td>'
            '<td class="rec-sf-label">net</td>'
            '</tr>'
        )
        for s in stats['sold_sf_stats'] if s['count']
    )
    sold_group = dash_group(
        'sold',
        cards_html=(
            stat_card('Net Sales', _fmt_money(stats['sold_for_total']),
                      '{0} sold'.format(stats['sold_count']))
            + stat_card('Sold &middot; Gross', _fmt_money(net), value_class=net_cls)
            + stat_card('Sold &middot; Spent', _fmt_money(stats['sold_cost_total']),
                        '{0} records'.format(stats['sold_count']))
        ),
        breakdown_html=breakdown_section('Sold by Year', sold_breakdown_rows, wide=True) if sold_breakdown_rows else '',
    )

    return '<div class="rec-dashboard">' + col_inv_group + sold_group + '</div>'


def _render_col_table(collection):
    if not collection:
        return '<div class="rec-empty">No collection data found.</div>'

    sf_names = [sf['name'] for sf in collection if sf['records']]
    sf_tabs = (
        '<div class="rec-sf-tabs" id="rec-sf-tabs-collection">'
        '<button class="rec-sf-tab active" data-sf="__all__">All</button>'
        + ''.join('<button class="rec-sf-tab" data-sf="{0}">{0}</button>'.format(_html.escape(n)) for n in sf_names)
        + '</div>'
    )

    rows = ''
    idx = 0
    for sf in collection:
        if not sf['records']:
            continue
        sf_key = _html.escape(sf['name'])
        rows += (
            '<tr class="rec-sf-header" data-sf="{0}">'
            '<td colspan="9">{1}</td>'
            '</tr>'
        ).format(sf_key, sf_key or '—')
        for r in sf['records']:
            rows += (
                '<tr data-sf="{sf}" data-artist="{artist}" data-album="{album}"'
                ' data-cost="{cost_v}" data-median="{med_v}" data-acquired="{acquired_v}" data-idx="{idx}">'
                '<td>{artist_d}</td>'
                '<td>{album_d}</td>'
                '<td>{cost_d}</td>'
                '<td>{median_d}</td>'
                '<td>{acquired}</td>'
                '<td>{color}</td>'
                '<td>{type_}</td>'
                '<td>{number}</td>'
                '<td class="rec-comment">{comment}</td>'
                '</tr>'
            ).format(
                sf=sf_key,
                artist=_html.escape(r['artist'].lower()),
                album=_html.escape(r['album'].lower()),
                cost_v=r['cost_val'] if r['cost_val'] is not None else '',
                med_v=r['median_val'] if r['median_val'] is not None else '',
                acquired_v=_html.escape(r['acquired']),
                idx=idx,
                artist_d=_html.escape(r['artist']),
                album_d=_html.escape(r['album']),
                cost_d=_fmt_cost(r['cost'], r['cost_val']),
                median_d=_fmt_cost(r['median'], r['median_val']),
                acquired=_html.escape(r['acquired']),
                color=_html.escape(r['color']),
                type_=_html.escape(r['type']),
                number=_html.escape(r['number']),
                comment=_html.escape(r['comment']),
            )
            idx += 1

    table = (
        '<div class="rec-toolbar">'
        '<input type="text" class="rec-search" placeholder="Search artist or album&hellip;" '
        'id="rec-search-collection" autocomplete="off">'
        '<span class="rec-count" id="rec-count-collection"></span>'
        '</div>'
        '<div class="rec-table-wrap">'
        '<table class="rec-table" id="rec-table-collection">'
        '<thead><tr>'
        '<th class="sortable" data-col="artist">Artist</th>'
        '<th class="sortable" data-col="album">Album</th>'
        '<th class="sortable" data-col="cost">Cost</th>'
        '<th class="sortable" data-col="median">Median</th>'
        '<th class="sortable" data-col="acquired">Acquired</th>'
        '<th>Color</th>'
        '<th>Type</th>'
        '<th>#</th>'
        '<th>Note</th>'
        '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '</div>'
    )
    return sf_tabs + table


def _render_inv_table(inventory):
    if not inventory:
        return '<div class="rec-empty">No inventory data found.</div>'

    sf_names = [sf['name'] for sf in inventory if sf['records']]
    sf_tabs = (
        '<div class="rec-sf-tabs" id="rec-sf-tabs-inventory">'
        '<button class="rec-sf-tab active" data-sf="__all__">All</button>'
        + ''.join('<button class="rec-sf-tab" data-sf="{0}">{0}</button>'.format(_html.escape(n)) for n in sf_names)
        + '</div>'
    )

    rows = ''
    idx = 0
    for sf in inventory:
        if not sf['records']:
            continue
        sf_key = _html.escape(sf['name'])
        rows += (
            '<tr class="rec-sf-header" data-sf="{0}">'
            '<td colspan="8">{1}</td>'
            '</tr>'
        ).format(sf_key, sf_key or '—')
        for r in sf['records']:
            listed_badge = '<span class="rec-badge rec-badge--listed">Listed</span>' if r['listed'] else ''
            copies_raw = r['copies'].strip()
            if copies_raw.lower() == 'sealed':
                copies_disp = '<span class="rec-badge rec-badge--sealed">Sealed</span>'
            elif copies_raw:
                try:
                    n = int(copies_raw)
                    copies_disp = '&times;{0}'.format(n)
                except ValueError:
                    copies_disp = _html.escape(copies_raw)
            else:
                copies_disp = ''

            rows += (
                '<tr data-sf="{sf}" data-artist="{artist}" data-album="{album}"'
                ' data-cost="{cost_v}" data-total="{total_v}" data-idx="{idx}">'
                '<td>{artist_d}</td>'
                '<td>{album_d}</td>'
                '<td>{cost_d}</td>'
                '<td>{total_d}</td>'
                '<td>{type_}</td>'
                '<td>{copies}</td>'
                '<td>{listed}</td>'
                '<td class="rec-comment">{comment}</td>'
                '</tr>'
            ).format(
                sf=sf_key,
                artist=_html.escape(r['artist'].lower()),
                album=_html.escape(r['album'].lower()),
                cost_v=r['cost_val'] if r['cost_val'] is not None else '',
                total_v=r['total_val'] if r['total_val'] is not None else '',
                idx=idx,
                artist_d=_html.escape(r['artist']),
                album_d=_html.escape(r['album']),
                cost_d=_fmt_cost(r['cost'], r['cost_val']),
                total_d=_fmt_cost(r['total'], r['total_val']),
                type_=_html.escape(r['type']),
                copies=copies_disp,
                listed=listed_badge,
                comment=_html.escape(r['comment']),
            )
            idx += 1

    table = (
        '<div class="rec-toolbar">'
        '<input type="text" class="rec-search" placeholder="Search artist or album&hellip;" '
        'id="rec-search-inventory" autocomplete="off">'
        '<span class="rec-count" id="rec-count-inventory"></span>'
        '</div>'
        '<div class="rec-table-wrap">'
        '<table class="rec-table" id="rec-table-inventory">'
        '<thead><tr>'
        '<th class="sortable" data-col="artist">Artist</th>'
        '<th class="sortable" data-col="album">Album</th>'
        '<th class="sortable" data-col="cost">Cost</th>'
        '<th class="sortable" data-col="total">Total</th>'
        '<th>Type</th>'
        '<th>Copies</th>'
        '<th>Listed</th>'
        '<th>Note</th>'
        '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '</div>'
    )
    return sf_tabs + table


def _render_sold_table(sold):
    if not sold:
        return '<div class="rec-empty">No sold records found.</div>'

    sf_names = [sf['name'] for sf in sold if sf['records']]
    sf_tabs = (
        '<div class="rec-sf-tabs" id="rec-sf-tabs-sold">'
        '<button class="rec-sf-tab active" data-sf="__all__">All</button>'
        + ''.join('<button class="rec-sf-tab" data-sf="{0}">{0}</button>'.format(_html.escape(n)) for n in sf_names)
        + '</div>'
    )

    rows = ''
    idx = 0
    for sf in sold:
        if not sf['records']:
            continue
        sf_key = _html.escape(sf['name'])
        rows += (
            '<tr class="rec-sf-header" data-sf="{0}">'
            '<td colspan="7">{1}</td>'
            '</tr>'
        ).format(sf_key, sf_key or '—')
        for r in sf['records']:
            profit = None
            if r['sold_for_val'] is not None and r['cost_val'] is not None:
                profit = r['sold_for_val'] - r['cost_val']
            profit_class = 'rec-profit--pos' if (profit is not None and profit >= 0) else ('rec-profit--neg' if profit is not None else '')
            rows += (
                '<tr data-sf="{sf}" data-artist="{artist}" data-album="{album}"'
                ' data-cost="{cost_v}" data-sold-for="{sold_v}" data-date="{date_v}" data-idx="{idx}">'
                '<td>{artist_d}</td>'
                '<td>{album_d}</td>'
                '<td>{cost_d}</td>'
                '<td>{sold_d}</td>'
                '<td class="{profit_class}">{profit_d}</td>'
                '<td>{date}</td>'
                '<td>{loc}</td>'
                '</tr>'
            ).format(
                sf=sf_key,
                artist=_html.escape(r['artist'].lower()),
                album=_html.escape(r['album'].lower()),
                cost_v=r['cost_val'] if r['cost_val'] is not None else '',
                sold_v=r['sold_for_val'] if r['sold_for_val'] is not None else '',
                date_v=_html.escape(r['sold_date']),
                idx=idx,
                artist_d=_html.escape(r['artist']),
                album_d=_html.escape(r['album']),
                cost_d=_fmt_cost(r['cost'], r['cost_val']),
                sold_d=_fmt_cost(r['sold_for'], r['sold_for_val']),
                profit_class=profit_class,
                profit_d=_fmt_money(profit) if profit is not None else '',
                date=_html.escape(r['sold_date']),
                loc=_html.escape(r['sold_location']),
            )
            idx += 1

    return (
        sf_tabs +
        '<div class="rec-toolbar">'
        '<input type="text" class="rec-search" placeholder="Search artist or album&hellip;" '
        'id="rec-search-sold" autocomplete="off">'
        '<span class="rec-count" id="rec-count-sold"></span>'
        '</div>'
        '<div class="rec-table-wrap">'
        '<table class="rec-table" id="rec-table-sold">'
        '<thead><tr>'
        '<th class="sortable" data-col="artist">Artist</th>'
        '<th class="sortable" data-col="album">Album</th>'
        '<th class="sortable" data-col="cost">Bought For</th>'
        '<th class="sortable" data-col="sold-for">Sold For</th>'
        '<th class="sortable" data-col="sold-for">Profit</th>'
        '<th class="sortable" data-col="date">Date</th>'
        '<th>Location</th>'
        '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '</div>'
    )


_RECORDS_JS = '''
(function() {
    function parseDateKey(str) {
        if (!str) return 0;
        var parts = str.split(/[\/\-\.]/);
        if (parts.length !== 3) return 0;
        var a = parseInt(parts[0], 10), b = parseInt(parts[1], 10), c = parseInt(parts[2], 10);
        if (parts[0].length === 4) return a * 10000 + b * 100 + c;  // YYYY-first
        var y = c < 100 ? c + 2000 : c;
        return y * 10000 + a * 100 + b;  // M/D/YY or M/D/YYYY
    }

    var panels = { collection: null, inventory: null, sold: null };
    ['collection','inventory','sold'].forEach(function(id) {
        panels[id] = document.getElementById('rec-panel-' + id);
    });

    // Dashboard groups
    var dashGroups = {};
    document.querySelectorAll('.rec-dash-group').forEach(function(g) {
        dashGroups[g.dataset.tabGroup] = g;
    });

    // Breakdown panes within the col-inv group
    var breakdownPanes = {};
    document.querySelectorAll('.rec-breakdown-pane').forEach(function(p) {
        breakdownPanes[p.dataset.breakdownPane] = p;
    });

    var TAB_TO_GROUP = { collection: 'col-inv', inventory: 'col-inv', sold: 'sold' };

    function switchBreakdownPane(target) {
        var current = null;
        Object.keys(breakdownPanes).forEach(function(k) {
            if (breakdownPanes[k].style.display !== 'none') current = breakdownPanes[k];
        });
        var next = breakdownPanes[target];
        if (!next || next === current) return;

        if (current) {
            current.classList.add('rec-dash-leaving');
            setTimeout(function() {
                current.style.display = 'none';
                current.classList.remove('rec-dash-leaving');
            }, 180);
        }

        next.style.cssText = '';
        next.classList.add('rec-dash-entering');
        void next.offsetWidth;
        next.classList.remove('rec-dash-entering');
    }

    function switchDashGroup(target) {
        var groupKey = TAB_TO_GROUP[target] || target;
        var currentGroup = null;
        Object.keys(dashGroups).forEach(function(k) {
            if (dashGroups[k].style.display !== 'none') currentGroup = dashGroups[k];
        });
        var nextGroup = dashGroups[groupKey];

        if (breakdownPanes[target] !== undefined) {
            if (currentGroup === nextGroup) {
                // Same group (collection ↔ inventory): animate just the pane
                switchBreakdownPane(target);
            } else {
                // Different group: set the correct pane instantly while the group is hidden
                Object.keys(breakdownPanes).forEach(function(k) {
                    breakdownPanes[k].style.cssText = k === target ? '' : 'display:none;opacity:0';
                });
            }
        }

        if (!nextGroup || nextGroup === currentGroup) return;

        if (currentGroup) {
            currentGroup.classList.add('rec-dash-leaving');
            setTimeout(function() {
                currentGroup.style.display = 'none';
                currentGroup.classList.remove('rec-dash-leaving');
            }, 180);
        }

        nextGroup.style.cssText = '';
        nextGroup.classList.add('rec-dash-entering');
        void nextGroup.offsetWidth;
        nextGroup.classList.remove('rec-dash-entering');
    }

    // Main tab switching
    document.querySelectorAll('.rec-tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.rec-tab').forEach(function(t) { t.classList.remove('active'); });
            this.classList.add('active');
            var target = this.dataset.tab;
            Object.keys(panels).forEach(function(id) {
                panels[id].style.display = id === target ? '' : 'none';
            });
            switchDashGroup(target);
        });
    });

    // Per-panel setup
    ['collection','inventory','sold'].forEach(function(folder) {
        var panel = panels[folder];
        if (!panel) return;

        var table    = panel.querySelector('.rec-table');
        var tbody    = table ? table.querySelector('tbody') : null;
        var searchEl = panel.querySelector('.rec-search');
        var countEl  = panel.querySelector('.rec-count');
        var sfTabsEl = panel.querySelector('.rec-sf-tabs');

        if (!tbody) return;

        var currentSF  = '__all__';
        var sortCol    = null;
        var sortDir    = 1;
        var originalOrder = Array.from(tbody.querySelectorAll('tr'));

        function allRows()    { return Array.from(tbody.querySelectorAll('tr')); }
        function recordRows() { return Array.from(tbody.querySelectorAll('tr:not(.rec-sf-header)')); }
        function sfHeaders()  { return Array.from(tbody.querySelectorAll('tr.rec-sf-header')); }

        function applyFilters() {
            var q  = searchEl ? searchEl.value.toLowerCase().trim() : '';
            var sf = currentSF;

            recordRows().forEach(function(row) {
                var matchSF     = sf === '__all__' || row.dataset.sf === sf;
                var matchSearch = !q ||
                    (row.dataset.artist || '').includes(q) ||
                    (row.dataset.album  || '').includes(q);
                row.style.display = matchSF && matchSearch ? '' : 'none';
            });

            // Show SF headers only when sorting is not active and has visible children
            sfHeaders().forEach(function(hdr) {
                if (sortCol) { hdr.style.display = 'none'; return; }
                var hSF = hdr.dataset.sf;
                if (sf !== '__all__' && hSF !== sf) { hdr.style.display = 'none'; return; }
                var hasVisible = recordRows().some(function(r) {
                    return r.dataset.sf === hSF && r.style.display !== 'none';
                });
                hdr.style.display = hasVisible ? '' : 'none';
            });

            if (countEl) {
                var n = recordRows().filter(function(r) { return r.style.display !== 'none'; }).length;
                countEl.textContent = n + ' record' + (n === 1 ? '' : 's');
            }
        }

        function sortTable(col, dir) {
            var recs = recordRows();
            var numeric = ['cost','median','total','sold-for'].indexOf(col) !== -1;
            var isDate  = ['acquired','date'].indexOf(col) !== -1;
            recs.sort(function(a, b) {
                if (isDate)  return dir * (parseDateKey(a.dataset[col]) - parseDateKey(b.dataset[col]));
                var av = numeric ? (parseFloat(a.dataset[col]) || 0) : (a.dataset[col] || '');
                var bv = numeric ? (parseFloat(b.dataset[col]) || 0) : (b.dataset[col] || '');
                if (numeric) return dir * (av - bv);
                return dir * av.localeCompare(bv);
            });
            recs.forEach(function(r) { tbody.appendChild(r); });
            applyFilters();
        }

        function resetSort() {
            originalOrder.forEach(function(r) { tbody.appendChild(r); });
            sortCol = null; sortDir = 1;
            panel.querySelectorAll('th.sortable').forEach(function(th) {
                th.classList.remove('sort-asc','sort-desc');
            });
            applyFilters();
        }

        // Sort headers
        panel.querySelectorAll('th.sortable').forEach(function(th) {
            th.addEventListener('click', function() {
                var col = this.dataset.col;
                if (sortCol === col) {
                    if (sortDir === -1) { resetSort(); return; }
                    sortDir = -1;
                } else {
                    sortCol = col; sortDir = 1;
                }
                panel.querySelectorAll('th.sortable').forEach(function(t) {
                    t.classList.remove('sort-asc','sort-desc');
                });
                this.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
                sortTable(sortCol, sortDir);
            });
        });

        // Search
        if (searchEl) {
            searchEl.addEventListener('input', applyFilters);
        }

        // Sub-folder tabs
        if (sfTabsEl) {
            sfTabsEl.querySelectorAll('.rec-sf-tab').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    sfTabsEl.querySelectorAll('.rec-sf-tab').forEach(function(b) { b.classList.remove('active'); });
                    this.classList.add('active');
                    currentSF = this.dataset.sf;
                    if (sortCol) resetSort();
                    applyFilters();
                });
            });
        }

        // Initial count
        applyFilters();
    });
})();
'''

@app.route("/records")
def recordspage():
    stats = _records_data['stats']
    collection = _records_data['collection']
    inventory  = _records_data['inventory']
    sold       = _records_data['sold']

    col_count = stats['col_count']
    inv_count = stats['inv_count']
    sol_count = stats['sold_count']

    dashboard = _render_records_dashboard(stats)

    tabs = (
        '<div class="rec-tabs-row">'
        '<div class="rec-tabs">'
        '<button class="rec-tab active" data-tab="collection">Collection ({0})</button>'
        '<button class="rec-tab" data-tab="inventory">Inventory ({1})</button>'
        '<button class="rec-tab" data-tab="sold">Sold ({2})</button>'
        '</div>'
        '</div>'
    ).format(col_count, inv_count, sol_count)

    content = (
        dashboard
        + tabs
        + '<div id="rec-panel-collection" class="rec-panel">' + _render_col_table(collection) + '</div>'
        + '<div id="rec-panel-inventory" class="rec-panel" style="display:none">' + _render_inv_table(inventory) + '</div>'
        + '<div id="rec-panel-sold" class="rec-panel" style="display:none">' + _render_sold_table(sold) + '</div>'
        + '<script>' + _RECORDS_JS + '</script>'
    )

    records_header = (
        '<div class="page-header">'
        '<div class="page-eyebrow">Vault</div>'
        '<h2>My <em>Records</em></h2>'
        '</div>'
    )

    return render_template('records.html',
        content=records_header + content,
        content_class='has-results',
        show_platter=True,
        title='Records'
    )


## Local Testing ##

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True, threaded=True)
