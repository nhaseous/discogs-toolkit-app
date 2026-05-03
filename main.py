from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, render_template, session, redirect
from helper import pricechecker, matcher, lookup as lookup_helper, records as records_helper
from concurrent.futures import ThreadPoolExecutor, as_completed
import cloudscraper, time, html as _html, os, requests as _requests
from datetime import datetime
from requests_oauthlib import OAuth1 as _OAuth1
import discogs_client as _discogs_client
import assets

_CONSUMER_KEY    = os.environ.get('DISCOGS_CONSUMER_KEY', '')
_CONSUMER_SECRET = os.environ.get('DISCOGS_CONSUMER_SECRET', '')
_CALLBACK_URL    = os.environ.get('DISCOGS_CALLBACK_URL', 'http://127.0.0.1:8080/callback')

app = Flask(__name__)
app.config['SECRET_KEY']              = os.environ.get('FLASK_SECRET_KEY', '')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = os.environ.get('GAE_ENV', '').startswith('standard')

try:
    _records_data = records_helper.load_all()
except Exception:
    _records_data = records_helper.empty_data()

def _oauth_auth():
    if session.get('discogs_access_token'):
        return _OAuth1(_CONSUMER_KEY, _CONSUMER_SECRET,
                       session['discogs_access_token'],
                       session['discogs_access_secret'])
    return None

@app.context_processor
def _inject_globals():
    return {
        'logo_svg': assets.LOGO_SVG,
        'discogs_logo_svg': assets.DISCOGS_LOGO_SVG,
        'session_user': session.get('discogs_username'),
        'session_avatar': session.get('discogs_avatar', ''),
    }

# Routes

## Auth ##

@app.route('/login')
def login():
    d = _discogs_client.Client('DiscogsToolkit/1.0',
        consumer_key=_CONSUMER_KEY, consumer_secret=_CONSUMER_SECRET)
    token, secret, url = d.get_authorize_url(callback_url=_CALLBACK_URL)
    session['oauth_token']  = token
    session['oauth_secret'] = secret
    return redirect(url)

@app.route('/callback')
def oauth_callback():
    oauth_verifier = request.args.get('oauth_verifier')
    if not oauth_verifier:
        return redirect('/')
    d = _discogs_client.Client('DiscogsToolkit/1.0',
        consumer_key=_CONSUMER_KEY, consumer_secret=_CONSUMER_SECRET)
    d.set_token(session.pop('oauth_token', ''), session.pop('oauth_secret', ''))
    try:
        access_token, access_secret = d.get_access_token(oauth_verifier)
        me = d.identity()
        username = me.username
        try:
            avatar_url = d.user(username).data.get('avatar_url', '') or ''
        except Exception:
            avatar_url = ''
        session['discogs_access_token']  = access_token
        session['discogs_access_secret'] = access_secret
        session['discogs_username']      = username
        session['discogs_avatar']        = avatar_url
    except Exception:
        pass
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(request.referrer or '/')

## Landing Page ##

@app.route("/")
def landingpage():
    if not session.get('discogs_username'):
        login_card = (
            '<a href="/login" class="tool-card tool-card--login">'
            '<div class="tool-card-label">Account</div>'
            '<h3 class="tool-card-title">Login with Discogs</h3>'
            '<p class="tool-card-desc">Connect your Discogs account to unlock the Reprice feature and authenticated API access.</p>'
            '</a>'
        )
    else:
        login_card = ''
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
        + login_card +
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
            release_titles_ids = pricechecker.get_inventory_ids(seller, scraper, auth=_oauth_auth())
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
    session_user = session.get('discogs_username', '')
    if not session_user:
        return {"error": "not_logged_in", "message": "Log in to use REPRICE"}, 401

    data = request.get_json()
    if not data:
        return {"error": "No JSON body"}, 400

    seller = data.get("seller", "")
    if seller and seller.lower() != session_user.lower():
        return {
            "error": "wrong_user",
            "message": "You can only reprice your own listings. Signed in as: " + session_user
        }, 403

    listings = data.get("listings", [])
    results = []
    headers = {"User-Agent": "DiscogsToolkitApp/1.0"}
    auth = _OAuth1(_CONSUMER_KEY, _CONSUMER_SECRET,
                   session['discogs_access_token'],
                   session['discogs_access_secret'])

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

        get_resp = _requests.get(base_url, headers=headers, auth=auth)
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

        post_resp = _requests.post(base_url, headers=headers, auth=auth, json=post_body)
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
            auth = _oauth_auth()

            collection = matcher.get_collection(collection_user, scraper, auth=auth)
            wantlist = matcher.get_wantlist(wantlist_user, scraper, auth=auth)

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

            grid = lookup_helper.render_lookup_grid(matches) if matches else '<p class="match-empty">No matches found.</p>'
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

@app.route("/lookup")
def lookuppage():

    username = request.args.get("username", "")
    list_id = request.args.get("list_id", "")
    output, loadtime, searched_at, user_meta, active_count_text = "", "", "", "", ""
    has_results = bool(username)

    if username:
        start_time = time.time()
        scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
        auth = _oauth_auth()

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
                collection = lookup_helper.get_collection(username, scraper, auth=auth)
            except lookup_helper.UserNotFoundError:
                user_not_found = True
            except lookup_helper.CollectionPrivateError:
                collection_error = "This user's collection is not public."

            if not user_not_found:
                try:
                    wantlist = lookup_helper.get_wantlist(username, scraper, auth=auth)
                except lookup_helper.UserNotFoundError:
                    user_not_found = True
                except lookup_helper.WantlistPrivateError:
                    wantlist_error = "This user's wantlist is not public."

            if not user_not_found:
                try:
                    lists = lookup_helper.get_lists(username, scraper, auth=auth)
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
                col_content = lookup_helper.render_lookup_grid(collection, show_stats=False)
            else:
                col_content = '<p class="match-empty">This collection is empty.</p>'

            if wantlist_error:
                want_content = '<div class="lookup-notice">' + _html.escape(wantlist_error) + '</div>'
            elif wantlist:
                want_content = lookup_helper.render_lookup_grid(wantlist, show_stats=True)
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
                    lists_content = lookup_helper.render_lookup_grid(list_releases, prepend_card=back_card_html)
                else:
                    lists_content = lookup_helper.render_lookup_grid([], prepend_card=back_card_html) + '<p class="match-empty">This list is empty.</p>'
            elif lists_error:
                lists_content = '<div class="lookup-notice">' + _html.escape(lists_error) + '</div>'
            else:
                lists_content = lookup_helper.render_list_index(lists or [], username)

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


@app.route("/records")
def recordspage():
    stats = _records_data['stats']
    collection = _records_data['collection']
    inventory  = _records_data['inventory']
    sold       = _records_data['sold']

    col_count = stats['col_count']
    inv_count = stats['inv_count']
    sol_count = stats['sold_count']

    dashboard = records_helper.render_records_dashboard(stats)

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
        + '<div id="rec-panel-collection" class="rec-panel">' + records_helper.render_col_table(collection) + '</div>'
        + '<div id="rec-panel-inventory" class="rec-panel" style="display:none">' + records_helper.render_inv_table(inventory) + '</div>'
        + '<div id="rec-panel-sold" class="rec-panel" style="display:none">' + records_helper.render_sold_table(sold) + '</div>'
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
