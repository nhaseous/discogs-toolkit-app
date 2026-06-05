import os
import time
from datetime import datetime

from flask import Blueprint, request, render_template, session

from services.logic import recommend as recommend_helper, lookup as lookup_helper
from services.clients import discogs_client as api_helper, firestore_db
from web_common import oauth_auth

recommend_bp = Blueprint('recommend', __name__)

# Per-IP daily request cap (abuse guard). Override via env.
_IP_DAILY_LIMIT = int(os.environ.get("RECOMMEND_IP_DAILY_LIMIT", "50"))


@recommend_bp.route("/recommend")
def recommendpage():
    username = request.args.get("user", "").strip()
    new_artists = request.args.get("new_artists", "") == "yes"

    cards = []
    error_output = ""
    loadtime, searched_at = "", ""
    has_results = bool(username)

    if username:
        # Per-IP daily abuse guard — count before doing any work. On GAE the
        # real client IP is the first entry of X-Forwarded-For.
        client_ip = (request.headers.get('X-Forwarded-For', request.remote_addr or '') or '').split(',')[0].strip()
        if not firestore_db.allow_ip_request(client_ip, _IP_DAILY_LIMIT):
            error_output = "Daily recommendation limit reached for your network ({0}/day). Please try again tomorrow.".format(_IP_DAILY_LIMIT)
        else:
            start = time.time()
            scraper = api_helper.make_api_session()
            auth = oauth_auth()
            # Signed out uses app auth (60/min); budget the collection fetch + the
            # per-candidate searches (up to 3 rounds × 10) so the burst stays under it.
            budget = api_helper.RequestBudget(60) if not session.get('discogs_access_token') else None

            try:
                items, _partial, _total = lookup_helper.get_collection(username, scraper, auth=auth, budget=budget)
                if not items:
                    error_output = "No public collection found for this user."
                else:
                    cards = recommend_helper.get_recommendation_cards(items, scraper, auth=auth, budget=budget, new_artists=new_artists)
                    if not cards:
                        error_output = "Couldn’t find any new vinyl recommendations — try again."
            except lookup_helper.UserNotFoundError:
                error_output = "User “{0}” not found.".format(username)
            except lookup_helper.CollectionPrivateError:
                error_output = "This user’s collection is private or unavailable."
            except lookup_helper.RateLimitError:
                error_output = "Discogs rate limit hit — try again in a minute."
            except recommend_helper.CapReachedError:
                error_output = "Recommendations are temporarily paused — the monthly budget cap was reached. They’ll be back next month."
            except recommend_helper.VertexConfigError as e:
                # Verbose on purpose so a misconfigured Vertex setup is obvious.
                error_output = "Vertex AI is not configured: {0}".format(e)
            except Exception:
                error_output = "Something went wrong generating recommendations."

            loadtime = round(time.time() - start, 2)
            searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

    return render_template('recommend.html',
        username=username,
        new_artists=new_artists,
        cards=cards,
        error_output=error_output,
        loadtime=loadtime,
        searched_at=searched_at,
        has_results=has_results,
        content_class='has-results' if has_results else '',
        show_platter=bool(cards),
        title='Recommendations',
    )
