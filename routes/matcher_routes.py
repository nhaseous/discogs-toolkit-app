from flask import Blueprint, request, render_template
import time
from datetime import datetime
from services.logic import matcher
from services.clients import discogs_client as api_helper
from web_common import oauth_auth
import assets

matcher_bp = Blueprint('matcher', __name__)


@matcher_bp.route("/matcher")
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
    exact_count = 0
    nonexact_count = 0

    if collection_user and wantlist_user:
        start_time = time.time()
        try:
            # Matcher only hits the REST API (collection + wantlist) — no
            # scraping — so use a plain requests session.
            scraper = api_helper.make_api_session()
            auth = oauth_auth()

            collection = matcher.get_collection(collection_user, scraper, auth=auth)
            wantlist = matcher.get_wantlist(wantlist_user, scraper, auth=auth)
            counts = {"collection": len(collection), "wantlist": len(wantlist)}

            # Compute the non-exact (easy-key) match set as the baseline; mark
            # each entry with is_exact so the client can switch between exact
            # and non-exact views without a server round-trip. Exact matches
            # are a subset of easy matches (stricter key includes everything
            # the easy key does), so one render covers both views.
            wantlist_easy = {w["easy"] for w in wantlist}
            wantlist_strict = {w["strict"] for w in wantlist}
            collection_by_easy = {}
            for item in collection:
                collection_by_easy.setdefault(item["easy_key"], item)
            matches = []
            for ek, item in collection_by_easy.items():
                if ek in wantlist_easy:
                    m = dict(item)
                    m["is_exact"] = item["key"] in wantlist_strict
                    matches.append(m)
            matches.sort(key=lambda x: x["artist"].lower())
            exact_count = sum(1 for m in matches if m["is_exact"])
            nonexact_count = len(matches)
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
        exact_count=exact_count,
        nonexact_count=nonexact_count,
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
