from flask import Blueprint, request, render_template, session, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from helper import lookup as lookup_helper, api as api_helper, insights as insights_helper
from web_common import oauth_auth

lookup_bp = Blueprint('lookup', __name__)


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
    has_results = bool(username)
    insights_html = ""
    wantlist_insights_html = ""

    if username:
        start_time = time.time()
        # collection, wantlist, lists and value are all REST API calls — use a
        # plain requests session. List detail (get_list_releases) manages its own
        # session since it may scrape www.discogs.com locally.
        scraper = api_helper.make_api_session()
        auth = oauth_auth()

        # Unauthenticated lookups share a single 25-request budget across the
        # collection/wantlist/lists fetches to stay under Discogs' 25/60s limit.
        # Signed-in viewers have a higher limit, so they fetch without a budget.
        budget = api_helper.RequestBudget(25) if auth is None else None

        _fetch_tasks = {
            'collection': lambda: lookup_helper.get_collection(username, scraper, auth=auth, budget=budget),
            'wantlist':   lambda: lookup_helper.get_wantlist(username, scraper, auth=auth, budget=budget),
            'lists':      lambda: lookup_helper.get_lists(username, scraper, auth=auth, budget=budget),
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
        # more than the 25 unauthenticated requests allow. Results would be truncated,
        # so block the lookup and tell the viewer to sign in (showing the real sizes).
        cap_exceeded = budget is not None and budget.exhausted

        if collection and not user_not_found and not cap_exceeded:
            insights = insights_helper.get_collection_insights(collection, total_value=total_value)
            insights_html = insights_helper.render_insights_dashboard(insights)

        if wantlist and not user_not_found and not cap_exceeded:
            wantlist_insights = insights_helper.get_collection_insights(wantlist)
            wantlist_insights_html = insights_helper.render_insights_dashboard(wantlist_insights, kind='wantlist')

        if list_id and not user_not_found and not rate_limited and not cap_exceeded:
            try:
                list_releases = lookup_helper.get_list_releases(list_id)
            except lookup_helper.RateLimitError:
                rate_limited = True
            except lookup_helper.CloudflareBlockedError:
                cf_blocked_list = True

        list_name = next((l['name'] for l in lists if str(l['id']) == str(list_id)), "") if list_id else ""

        end_time = time.time()
        loadtime = round(end_time - start_time, 2)
        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

    return render_template('lookup.html',
        username=username,
        list_id=list_id,
        list_name=list_name,
        collection=collection,
        wantlist=wantlist,
        lists=lists,
        list_releases=list_releases,
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
        insights_html=insights_html,
        wantlist_insights_html=wantlist_insights_html,
        content_class='has-results' if has_results else '',
        show_platter=has_results,
        title='User Lookup'
    )


@lookup_bp.route("/lookup/list")
def lookup_list_data():
    list_id = request.args.get("list_id", "")
    if not list_id:
        return jsonify({"error": "Missing list_id"}), 400
    try:
        releases = lookup_helper.get_list_releases(list_id)
    except lookup_helper.RateLimitError:
        return jsonify({"error": "rate_limited"}), 429
    except lookup_helper.CloudflareBlockedError:
        return jsonify({"error": "cf_blocked"}), 503
    except Exception:
        return jsonify({"error": "failed"}), 500
    return jsonify({"releases": releases})
