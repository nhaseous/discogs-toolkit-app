from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, render_template, session, redirect, send_from_directory
from helper import pricechecker, matcher, lookup as lookup_helper, records as records_helper, firestore_db as _firestore_db, insights as insights_helper, api as api_helper
from concurrent.futures import ThreadPoolExecutor, as_completed
import cloudscraper, time, html as _html, os, requests as _requests, json as _json
from datetime import datetime, timedelta
from requests_oauthlib import OAuth1 as _OAuth1
import discogs_client as _discogs_client
import assets
from helper import auth as auth_persistence

_CONSUMER_KEY    = os.environ.get('DISCOGS_CONSUMER_KEY', '')
_CONSUMER_SECRET = os.environ.get('DISCOGS_CONSUMER_SECRET', '')
_CALLBACK_URL    = os.environ.get('DISCOGS_CALLBACK_URL', 'http://127.0.0.1:8080/callback')

import sys
if getattr(sys, 'frozen', False):
    app = Flask(__name__, template_folder=os.path.join(os.environ.get('RESOURCEPATH', os.getcwd()), 'templates'), static_folder=os.path.join(os.environ.get('RESOURCEPATH', os.getcwd()), 'static'))
else:
    app = Flask(__name__)
app.config['SECRET_KEY']              = os.environ.get('FLASK_SECRET_KEY', '')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = os.environ.get('GAE_ENV', '').startswith('standard')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=90)

_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
_STATIC_V = str(int(max(
    (os.path.getmtime(os.path.join(r, f)) for r, _, fs in os.walk(_static_dir) for f in fs),
    default=os.path.getmtime(os.path.abspath(__file__))
)))

try:
    _records_data = records_helper.load_all()
except Exception:
    _records_data = records_helper.empty_data()

@app.route('/static/v<version>/<path:filename>')
def versioned_static(version, filename):
    return send_from_directory(app.static_folder, filename)

@app.before_request
def _load_persistent_auth():
    if not session.get('discogs_username') and auth_persistence.is_macos_dist():
        data = auth_persistence.get_from_keychain()
        if data:
            session.permanent = True
            session['discogs_access_token']  = data.get('access_token')
            session['discogs_access_secret'] = data.get('access_secret')
            session['discogs_username']      = data.get('username')
            session['discogs_avatar']        = data.get('avatar_url', '')
    elif session.get('discogs_username') and not session.permanent:
        session.permanent = True

def _oauth_auth():
    if session.get('discogs_access_token'):
        return _OAuth1(_CONSUMER_KEY, _CONSUMER_SECRET,
                       session['discogs_access_token'],
                       session['discogs_access_secret'])
    return None

def _is_price_checker_enabled():
    is_gae = os.environ.get('GAE_ENV', '').startswith('standard')
    is_local = request.host.startswith('127.0.0.1') or request.host.startswith('localhost')
    is_frozen = getattr(sys, 'frozen', False)
    # Price Checker is disabled on GAE, enabled on local dev and macOS dist.
    if is_gae:
        return False
    return is_frozen or is_local

@app.context_processor
def _inject_globals():
    def _total_int(e):
        try: return int(str(e.total).replace(',', '').strip())
        except (ValueError, TypeError): return None

    def get_inventory_stats(inventory_list):
        return {
            'recent': sum(1 for e in inventory_list if e and e.daysAgo is not None),
            'old': sum(1 for e in inventory_list if e and getattr(e, 'yearsAgo', None) is not None),
            'low': sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) < 4),
            'lowest': sum(1 for e in inventory_list if e and _total_int(e) == 1),
            'high': sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) > 4),
            'highest': sum(1 for e in inventory_list if e and _total_int(e) is not None and (_total_int(e) or 0) > 9),
            'cheapest': sum(1 for e in inventory_list if e and 'card-cheapest-badge' in getattr(e, 'price_badges', '')),
            'overpriced': sum(1 for e in inventory_list if e and 'card-overpriced-badge' in getattr(e, 'price_badges', '')),
        }

    return {
        'logo_svg': assets.LOGO_SVG,
        'discogs_logo_svg': assets.DISCOGS_LOGO_SVG,
        'vinyl_placeholder_svg': assets.VINYL_PLACEHOLDER_SVG,
        'search_icon_svg': assets.SEARCH_ICON_SVG,
        'back_arrow_svg': assets.BACK_ARROW_SVG,
        'eye_closed_svg': assets.EYE_CLOSED_SVG,
        'eye_open_svg': assets.EYE_OPEN_SVG,
        'rate_limit_notice': assets.RATE_LIMIT_NOTICE,
        'cloudflare_notice': assets.CLOUDFLARE_NOTICE,
        'session_user': session.get('discogs_username'),
        'session_avatar': session.get('discogs_avatar', ''),
        'price_checker_enabled': _is_price_checker_enabled(),
        'is_frozen': getattr(sys, 'frozen', False),
        'static_v': _STATIC_V,
        'entry_badges': pricechecker._entry_badges,
        'get_inventory_stats': get_inventory_stats,
    }

@app.template_filter('ordinal')
def ordinal_filter(n):
    return pricechecker.ordinal(n)

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
        session.permanent = True
        if auth_persistence.is_macos_dist():
            auth_persistence.save_to_keychain(username, access_token, access_secret, avatar_url)
    except Exception:
        pass
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    if auth_persistence.is_macos_dist():
        auth_persistence.delete_from_keychain()
    return redirect(request.referrer or '/')

## Landing Page ##

@app.route("/")
def landingpage():
    return render_template('landing.html', 
                           price_checker_enabled=_is_price_checker_enabled())

## Price Checker Module ##

@app.route("/pricechecker")
def pricecheckerpage():
    if not _is_price_checker_enabled():
        return "Price Checker doesn't work when running on the cloud/web because webscraping gets blocked by Cloudflare. Contact curefortheitch if interested in a local solution."

    seller = request.args.get("seller", "")
    loadtime, searched_at = "", ""
    show_platter = False
    inventory_count = 0
    inventory_list = []
    sorted_inventory_list = [[] for _ in range(10)]
    sort_active = request.args.get("sort", "") == "yes"
    error_output = ""

    if seller != "":
        start_time = time.time()
        try:
            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
            release_titles_ids = pricechecker.get_inventory_ids(seller, scraper, auth=_oauth_auth())
            inventory_count = len(release_titles_ids)
            inventory_list = [None] * inventory_count

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(pricechecker.get_listings, scraper, inventory_list,
                                    sorted_inventory_list, seller, release[0], release[1], release[2], release[3], i)
                    for i, release in enumerate(release_titles_ids)
                ]
                for f in as_completed(futures):
                    f.result()

            show_platter = True

        except pricechecker.CloudflareBlockedError:
            error_output = assets.CLOUDFLARE_NOTICE
        except AttributeError:
            error_output = "No user found."

        end_time = time.time()
        loadtime = round(end_time - start_time, 2)
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

    return render_template('pricechecker.html',
        seller=seller,
        inventory_count=inventory_count,
        inventory_list=inventory_list,
        sorted_inventory_list=sorted_inventory_list,
        sort_active=sort_active,
        loadtime=loadtime,
        searched_at=searched_at,
        error_output=error_output,
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

        custom_price_raw = item.get("custom_price")
        if custom_price_raw is not None:
            new_price = round(float(custom_price_raw), 2)
        else:
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


## Watchlist ##

@app.route("/watchlist", methods=["GET"])
def get_watchlist():
    user = session.get('discogs_username', '')
    seller = request.args.get('seller', '')
    if not user or user.lower() != seller.lower():
        return {"watchlist": []}
    try:
        return {"watchlist": _firestore_db.get_watchlist(user)}
    except Exception as e:
        return {"watchlist": [], "error": str(e)}

@app.route("/watchlist", methods=["POST"])
def save_watchlist():
    user = session.get('discogs_username', '')
    if not user:
        return {"status": "error", "message": "Not authenticated"}, 401
    data = request.get_json(silent=True) or {}
    seller = data.get('seller', '')
    if user.lower() != seller.lower():
        return {"status": "error", "message": "Forbidden"}, 403
    release_ids = [str(rid) for rid in (data.get('watchlist') or [])]
    try:
        _firestore_db.save_watchlist(user, release_ids)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


## Matcher Module ##

@app.route("/matcher")
def matcherpage():
    collection_user = request.args.get("collection", "")
    wantlist_user = request.args.get("wantlist", "")
    exact = request.args.get("exact", "") == "yes"
    
    matches = []
    loadtime, searched_at = "", ""
    collection_meta, wantlist_meta = "", ""
    has_results = False
    error_output = ""
    counts = {"collection": 0, "wantlist": 0}

    if collection_user and wantlist_user:
        start_time = time.time()
        try:
            scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
            auth = _oauth_auth()

            collection = matcher.get_collection(collection_user, scraper, auth=auth)
            wantlist = matcher.get_wantlist(wantlist_user, scraper, auth=auth)
            counts = {"collection": len(collection), "wantlist": len(wantlist)}

            lookup_field = "key" if exact else "easy_key"
            wantlist_set = {w["strict"] if exact else w["easy"] for w in wantlist}
            collection_by_key = {item[lookup_field]: item for item in collection}
            matches = sorted(
                [collection_by_key[k] for k in collection_by_key if k in wantlist_set],
                key=lambda x: x["artist"].lower()
            )
            has_results = True

        except matcher.RateLimitError:
            error_output = assets.RATE_LIMIT_NOTICE
        except Exception:
            error_output = "Unable to find a match."

        end_time = time.time()
        loadtime = round(end_time - start_time, 2)
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")
        collection_meta = collection_user
        wantlist_meta = wantlist_user

    return render_template('matcher.html',
        collection_user=collection_user,
        wantlist_user=wantlist_user,
        exact=exact,
        matches=matches,
        counts=counts,
        loadtime=loadtime,
        searched_at=searched_at,
        collection_meta=collection_meta,
        wantlist_meta=wantlist_meta,
        has_results=has_results,
        error_output=error_output,
        content_class='has-results' if collection_user and wantlist_user else '',
        show_platter=has_results,
        title='Collection Matcher'
    )

## Lookup Module ##

@app.route("/lookup")
def lookuppage():
    username = request.args.get("username", "")
    list_id = request.args.get("list_id", "")
    
    collection, wantlist, lists, list_releases = [], [], [], []
    user_not_found, rate_limited, cf_blocked_list = False, False, False
    collection_error, wantlist_error, lists_error = "", "", ""
    collection_partial, wantlist_partial = "", ""
    loadtime, searched_at = "", ""
    has_results = bool(username)
    insights_html = ""

    if username:
        start_time = time.time()
        scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'android','desktop':False})
        auth = _oauth_auth()

        _fetch_tasks = {
            'collection': lambda: lookup_helper.get_collection(username, scraper, auth=auth),
            'wantlist':   lambda: lookup_helper.get_wantlist(username, scraper, auth=auth),
            'lists':      lambda: lookup_helper.get_lists(username, scraper, auth=auth),
        }
        
        # New: If looking at self, fetch collection value (1 extra call)
        total_value = None
        if session.get('discogs_username') and session['discogs_username'].lower() == username.lower():
            _fetch_tasks['value'] = lambda: api_helper.get_collection_value(username, scraper, auth=auth)

        with ThreadPoolExecutor(max_workers=4) as _ex:
            _futures = {_ex.submit(fn): name for name, fn in _fetch_tasks.items()}
            for _future in as_completed(_futures):
                _name = _futures[_future]
                try:
                    _result = _future.result()
                    if _name == 'collection':
                        collection, collection_partial = _result
                    elif _name == 'wantlist':
                        wantlist, wantlist_partial = _result
                    elif _name == 'lists':      lists      = _result
                    elif _name == 'value':      total_value = _result
                except lookup_helper.UserNotFoundError:
                    user_not_found = True
                except lookup_helper.CollectionPrivateError:
                    collection_error = "This user's collection is not public."
                except lookup_helper.WantlistPrivateError:
                    wantlist_error = "This user's wantlist is not public."
                except lookup_helper.ListPrivateError:
                    lists_error = "This user's lists are not public."
                except lookup_helper.RateLimitError:
                    rate_limited = True

        if collection and not user_not_found:
            insights = insights_helper.get_collection_insights(collection, total_value=total_value)
            insights_html = insights_helper.render_insights_dashboard(insights)

        if list_id and not user_not_found and not rate_limited:
            try:
                list_releases = lookup_helper.get_list_releases(list_id, scraper)
            except lookup_helper.RateLimitError:
                rate_limited = True
            except lookup_helper.CloudflareBlockedError:
                cf_blocked_list = True

        end_time = time.time()
        loadtime = round(end_time - start_time, 2)
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

    return render_template('lookup.html',
        username=username,
        list_id=list_id,
        collection=collection,
        wantlist=wantlist,
        lists=lists,
        list_releases=list_releases,
        user_not_found=user_not_found,
        rate_limited=rate_limited,
        cf_blocked_list=cf_blocked_list,
        collection_error=collection_error,
        wantlist_error=wantlist_error,
        lists_error=lists_error,
        collection_partial=collection_partial,
        wantlist_partial=wantlist_partial,
        loadtime=loadtime,
        searched_at=searched_at,
        has_results=has_results,
        insights_html=insights_html,
        content_class='has-results' if has_results else '',
        show_platter=has_results,
        title='User Lookup'
    )


## Records ##

@app.route("/records")
def recordspage():
    if session.get('discogs_username') != 'curefortheitch':
        return "Access Denied: You do not have permission to access this page. This feature is restricted to authorized users only.", 403

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
