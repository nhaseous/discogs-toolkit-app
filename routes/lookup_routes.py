from flask import Blueprint, request, render_template, session, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from services.logic import lookup as lookup_helper, insights as insights_helper
from services.clients import discogs_client as api_helper
from services.utils import lookup_cache
from web_common import oauth_auth

lookup_bp = Blueprint('lookup', __name__)

# Items inlined per tab on initial HTML render. Anything beyond this is fetched
# lazily from /lookup/data after first paint. Matches the JS default PAGE_SIZE
# so the first page of cards can render without waiting on hydration.
_INLINE_PAGE_SIZE = 50


@lookup_bp.route("/lookup")
def lookuppage():
    username = request.args.get("username", "")
    list_id = request.args.get("list_id", "")

    collection, wantlist, lists, list_releases = [], [], [], []
    user_not_found, rate_limited, cf_blocked_list = False, False, False
    cap_exceeded = False
    collection_total, wantlist_total = 0, 0
    collection_error, wantlist_error, lists_error = "", "", ""
    collection_partial, wantlist_partial = "", ""
    loadtime, searched_at = "", ""
    list_name = ""
    list_url = ""
    has_results = bool(username)
    insights = None

    # When opening a specific list, defer collection + wantlist fetches until
    # the user actually clicks those tabs. Saves several API calls (and the
    # insights aggregation) per list view.
    defer_collection_wantlist = bool(list_id)

    if username:
        start_time = time.time()
        # collection, wantlist, lists and value are all REST API calls — use a
        # plain requests session. List detail (get_list_releases) manages its own
        # session since it may scrape www.discogs.com locally.
        scraper = api_helper.make_api_session()
        auth = oauth_auth()

        # Signed-out lookups (app auth) share a single 60-request budget across the
        # collection/wantlist/lists fetches to stay under Discogs' 60/60s limit.
        # Signed-in viewers fetch their own data without a budget. NB: oauth_auth()
        # now always returns an auth object (app auth when signed out), so detect
        # sign-in via the session token rather than `auth is None`.
        budget = api_helper.RequestBudget(60) if not session.get('discogs_access_token') else None

        _fetch_tasks = {
            'lists':      lambda: lookup_helper.get_lists(username, scraper, auth=auth, budget=budget),
        }
        if not defer_collection_wantlist:
            _fetch_tasks['collection'] = lambda: lookup_helper.get_collection(username, scraper, auth=auth, budget=budget)
            _fetch_tasks['wantlist']   = lambda: lookup_helper.get_wantlist(username, scraper, auth=auth, budget=budget)

        # New: If looking at self, fetch collection value (1 extra call). Skip
        # when deferring — value is only used by collection insights.
        total_value = None
        if not defer_collection_wantlist and session.get('discogs_username') and session['discogs_username'].lower() == username.lower():
            _fetch_tasks['value'] = lambda: api_helper.get_collection_value(username, scraper, auth=auth)

        with ThreadPoolExecutor(max_workers=4) as _ex:
            _futures = {_ex.submit(fn): name for name, fn in _fetch_tasks.items()}
            for _future in as_completed(_futures):
                _name = _futures[_future]
                try:
                    _result = _future.result()
                    if _name == 'collection':
                        collection, collection_partial, collection_total = _result
                    elif _name == 'wantlist':
                        wantlist, wantlist_partial, wantlist_total = _result
                    elif _name == 'lists':      lists      = _result
                    elif _name == 'value':      total_value = _result
                except lookup_helper.UserNotFoundError:
                    user_not_found = True
                except lookup_helper.CollectionPrivateError:
                    collection_error = "This user's collection is not public or could not be accessed."
                except lookup_helper.WantlistPrivateError:
                    wantlist_error = "This user's wantlist is not public or could not be accessed."
                except lookup_helper.ListPrivateError:
                    lists_error = "This user's lists are not public."
                except lookup_helper.RateLimitError:
                    rate_limited = True

        # The shared budget runs out only when the user's collection + wantlist need
        # more than the 60 app-auth requests allow. Results would be truncated,
        # so block the lookup and tell the viewer to sign in (showing the real sizes).
        cap_exceeded = budget is not None and budget.exhausted

        if collection and not user_not_found and not cap_exceeded:
            insights = insights_helper.get_collection_insights(collection, total_value=total_value)

        # Wantlist insights are rendered lazily on first wantlist tab click via the
        # /lookup/insights endpoint, so a viewer who never opens that tab pays no
        # cost for aggregating + rendering them. The wantlist JSON is already on
        # the page (the lookup-data script block), so the lazy fetch sends that
        # back rather than refetching the wantlist from Discogs.

        if list_id and not user_not_found and not rate_limited and not cap_exceeded:
            try:
                list_releases = lookup_helper.get_list_releases(list_id, auth=auth)
            except lookup_helper.RateLimitError:
                rate_limited = True
            except lookup_helper.CloudflareBlockedError:
                cf_blocked_list = True

        list_name = next((l['name'] for l in lists if str(l['id']) == str(list_id)), "") if list_id else ""
        list_url = next((l['url'] for l in lists if str(l['id']) == str(list_id)), "") if list_id else ""

        end_time = time.time()
        loadtime = round(end_time - start_time, 2)
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

        # Stash the full result for /lookup/data to serve to the client once it
        # finishes first paint. Only cache if we actually have something useful
        # to hand back — failed/empty lookups can re-fetch from Discogs if needed.
        if not user_not_found and not cap_exceeded and not rate_limited:
            lookup_cache.put(
                (username.lower(), str(list_id)),
                {'collection': collection, 'wantlist': wantlist, 'list_releases': list_releases},
            )
            # Share the collection with the Recommendations tool so a follow-up
            # /recommend for this user reuses it instead of re-paging. Only when
            # complete (a partial/truncated fetch would skew the taste profile).
            if collection and not collection_partial:
                lookup_cache.put(("collection", username.lower()), {'items': collection})

    # Inline only the first page of items per tab — the rest is hydrated lazily.
    # The full lists are still passed in for the mosaic (collection) and the tab
    # count labels; only the heavy lookup-data JSON blocks read the *_inline view.
    collection_inline = collection[:_INLINE_PAGE_SIZE]
    wantlist_inline = wantlist[:_INLINE_PAGE_SIZE]
    list_releases_inline = list_releases[:_INLINE_PAGE_SIZE]
    needs_hydration = {
        'collection': len(collection) > _INLINE_PAGE_SIZE,
        'wantlist':   len(wantlist) > _INLINE_PAGE_SIZE,
        'list':       len(list_releases) > _INLINE_PAGE_SIZE,
    }

    return render_template('lookup.html',
        username=username,
        list_id=list_id,
        list_name=list_name,
        list_url=list_url,
        collection=collection,
        wantlist=wantlist,
        lists=lists,
        list_releases=list_releases,
        collection_inline=collection_inline,
        wantlist_inline=wantlist_inline,
        list_releases_inline=list_releases_inline,
        needs_hydration=needs_hydration,
        defer_collection_wantlist=defer_collection_wantlist,
        user_not_found=user_not_found,
        rate_limited=rate_limited,
        cap_exceeded=cap_exceeded,
        collection_total=collection_total,
        wantlist_total=wantlist_total,
        cf_blocked_list=cf_blocked_list,
        collection_error=collection_error,
        wantlist_error=wantlist_error,
        lists_error=lists_error,
        collection_partial=collection_partial,
        wantlist_partial=wantlist_partial,
        loadtime=loadtime,
        searched_at=searched_at,
        has_results=has_results,
        insights=insights,
        insights_kind='collection',
        content_class='has-results' if has_results else '',
        show_platter=has_results,
        show_player=has_results,
        title='User Lookup'
    )


@lookup_bp.route("/lookup/insights", methods=["POST"])
def lookup_insights():
    # Lazy-render endpoint for wantlist insights — the page POSTs back the
    # already-shipped wantlist items (from the lookup-data script block) and
    # gets HTML in return. Avoids re-fetching the wantlist from Discogs.
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    kind = data.get("kind", "wantlist")
    if not items:
        return jsonify({"html": ""})
    insights = insights_helper.get_collection_insights(items)
    html = render_template('_insights_fragment.html', insights=insights, kind=kind)
    return jsonify({"html": html})


@lookup_bp.route("/lookup/data")
def lookup_data():
    """
    Lazy-hydration endpoint. Returns the full items array for a given tab from
    the in-memory cache populated by /lookup. Lets the page ship only the first
    pagination window inline and fetch the rest after first paint.

    On a cache miss (TTL expired or different process instance), returns 410 so
    the client can fall back to its inline subset rather than block the user.
    """
    username = request.args.get("username", "").lower()
    tab = request.args.get("tab", "")
    list_id = request.args.get("list_id", "")
    if not username or tab not in ("collection", "wantlist", "list"):
        return jsonify({"error": "bad_request"}), 400
    cached = lookup_cache.get((username, str(list_id)))
    if not cached:
        return jsonify({"error": "expired"}), 410
    key_map = {"collection": "collection", "wantlist": "wantlist", "list": "list_releases"}
    return jsonify({"items": cached.get(key_map[tab], [])})


@lookup_bp.route("/lookup/load-tab")
def lookup_load_tab():
    """
    Lazy-load endpoint for the collection or wantlist tabs when the page was
    initially rendered with a list_id (which defers those fetches). Returns
    the items array plus the rendered insights dashboard HTML so the client
    can populate cards + inject the dashboard in one round trip.
    """
    username = request.args.get("username", "")
    tab = request.args.get("tab", "")
    if not username or tab not in ("collection", "wantlist"):
        return jsonify({"error": "bad_request"}), 400

    scraper = api_helper.make_api_session()
    auth = oauth_auth()
    # Signed out uses app auth (60/min); budget that burst. Signed in: no budget.
    budget = api_helper.RequestBudget(60) if not session.get('discogs_access_token') else None

    try:
        if tab == "collection":
            items, partial, _total = lookup_helper.get_collection(username, scraper, auth=auth, budget=budget)
        else:
            items, partial, _total = lookup_helper.get_wantlist(username, scraper, auth=auth, budget=budget)
    except lookup_helper.UserNotFoundError:
        return jsonify({"error": "user_not_found"}), 404
    except lookup_helper.CollectionPrivateError:
        return jsonify({"error": "collection_private"}), 403
    except lookup_helper.WantlistPrivateError:
        return jsonify({"error": "wantlist_private"}), 403
    except lookup_helper.RateLimitError:
        return jsonify({"error": "rate_limited"}), 429

    total_value = None
    if tab == "collection" and session.get('discogs_username') and session['discogs_username'].lower() == username.lower():
        try:
            total_value = api_helper.get_collection_value(username, scraper, auth=auth)
        except Exception:
            total_value = None

    insights_html = ""
    if items:
        insights = insights_helper.get_collection_insights(items, total_value=total_value)
        insights_html = render_template('_insights_fragment.html', insights=insights, kind=tab)

    return jsonify({
        "items": items,
        "partial": partial or "",
        "insights_html": insights_html,
    })


@lookup_bp.route("/lookup/folders")
def lookup_folders():
    """Return the viewed user's collection folders (id/name/count) so the Lookup
    page can build per-folder subtabs client-side, without a page refresh. Only
    the collection owner (when signed in) sees their named folders; for everyone
    else Discogs returns just the 'All' folder and the page adds no subtabs."""
    username = request.args.get("username", "")
    if not username:
        return jsonify({"error": "bad_request"}), 400
    scraper = api_helper.make_api_session()
    auth = oauth_auth()
    try:
        folders = lookup_helper.get_collection_folders(username, scraper, auth=auth)
    except lookup_helper.RateLimitError:
        return jsonify({"error": "rate_limited"}), 429
    return jsonify({"folders": folders})


@lookup_bp.route("/lookup/list")
def lookup_list_data():
    list_id = request.args.get("list_id", "")
    if not list_id:
        return jsonify({"error": "Missing list_id"}), 400
    auth = oauth_auth()
    try:
        releases = lookup_helper.get_list_releases(list_id, auth=auth)
    except lookup_helper.RateLimitError:
        return jsonify({"error": "rate_limited"}), 429
    except lookup_helper.CloudflareBlockedError:
        return jsonify({"error": "cf_blocked"}), 503
    except Exception:
        return jsonify({"error": "failed"}), 500
    return jsonify({"releases": releases})
