from flask import Blueprint, request, render_template
import time
from datetime import datetime
from helper import matcher, discogs_client as api_helper
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
