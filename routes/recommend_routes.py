import os

from flask import Blueprint, request, render_template, session, jsonify

from services.logic import recommend as recommend_helper, lookup as lookup_helper
from services.clients import discogs_client as api_helper, firestore_db
from services.utils import lookup_cache
from web_common import oauth_auth

recommend_bp = Blueprint('recommend', __name__)

# Per-IP daily cap, counted per Gemini ROUND (not per search). At up to 3 rounds
# per search (_MAX_ROUNDS), 50 rounds/day is ~16 full searches/day. Override via env.
_IP_DAILY_ROUND_LIMIT = int(os.environ.get("RECOMMEND_IP_DAILY_ROUND_LIMIT", "50"))

# Streaming targets: keep asking for rounds until this many releases are found
# or the round cap is hit. Each round is one Gemini call streamed to the client.
_TARGET_RESULTS = 10
_MAX_ROUNDS = 3

# Manual "get more" refreshes (a single round each) ask Gemini for more candidates
# than the initial streaming rounds, so one round nets enough cards despite ~half
# being lost to the owned filter / no-vinyl-match — the initial rounds stay leaner
# since they stack up across the run toward _TARGET_RESULTS.
_REFRESH_CANDIDATES = 10


@recommend_bp.route("/recommend")
def recommendpage():
    """Render the page shell only. The actual recommendation rounds are streamed
    in by recommend.js via POST /recommend/batch, so the first batch can paint as
    soon as one Gemini round resolves instead of blocking on the whole pipeline."""
    username = request.args.get("user", "").strip()
    new_artists = request.args.get("new_artists", "") == "yes"
    has_results = bool(username)

    return render_template('recommend.html',
        username=username,
        new_artists=new_artists,
        has_results=has_results,
        content_class='has-results' if has_results else '',
        show_platter=has_results,
        title='Recommendations',
    )


@recommend_bp.route("/recommend/batch", methods=["POST"])
def recommend_batch():
    """Run a single Gemini round and return its resolved cards as HTML.

    Stateless across rounds: the client round-trips `considered` (already-suggested
    {artist, album} pairs) and `seen_ids` (rendered release IDs) so each call avoids
    repeats without server-side per-session state. The viewed user's collection is
    fetched once and cached so rounds 2-3 don't re-page it or burn the rate budget.
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("user") or "").strip()
    new_artists = bool(data.get("new_artists"))
    considered = data.get("considered") or []
    seen_ids = data.get("seen_ids") or []
    have = int(data.get("have") or 0)
    round_idx = int(data.get("round") or 0)
    # Manual "get more" refreshes over-ask Gemini; initial streaming rounds don't.
    manual = bool(data.get("manual"))
    if not username:
        return jsonify({"error": "bad_request"}), 400

    # Per-IP daily cost guard — counted per Gemini round (every batch call), so a
    # full 3-round search consumes 3 of the day's allowance. On GAE the client IP is
    # the first X-Forwarded-For entry. A mid-search cap hit returns done with an
    # error, but the client keeps the cards already found; only a round-0 hit (no
    # cards yet) surfaces the notice.
    client_ip = (request.headers.get('X-Forwarded-For', request.remote_addr or '') or '').split(',')[0].strip()
    if not firestore_db.allow_ip_request(client_ip, _IP_DAILY_ROUND_LIMIT):
        return jsonify({"done": True, "error": "daily_limit",
                        "message": "Daily recommendation limit reached for your network. Please try again tomorrow."})

    scraper = api_helper.make_api_session()
    auth = oauth_auth()
    # Signed out uses app auth (60/min); budget each round's burst. Signed in: none.
    budget = api_helper.RequestBudget(60) if not session.get('discogs_access_token') else None

    # Collection: shared across this recommendation's rounds AND with the Lookup
    # tool (key ("collection", username)), so the common Lookup -> Recommend flow
    # doesn't re-page the same collection. The taste profile is cached alongside
    # the items so it isn't re-aggregated from the whole collection each round.
    cache_key = ("collection", username.lower())
    items, profile_text = None, None
    cached = lookup_cache.get(cache_key)
    if cached and cached.get("items"):
        items = cached["items"]
        profile_text = cached.get("profile")

    if items is None:
        try:
            items, _partial, _total = lookup_helper.get_collection(username, scraper, auth=auth, budget=budget)
        except lookup_helper.UserNotFoundError:
            return jsonify({"done": True, "error": "user_not_found", "message": "User “{0}” not found.".format(username)})
        except lookup_helper.CollectionPrivateError:
            return jsonify({"done": True, "error": "collection_private", "message": "This user’s collection is private or unavailable."})
        except lookup_helper.RateLimitError:
            return jsonify({"done": True, "error": "rate_limited", "message": "Discogs rate limit hit — try again in a minute."})
        if not items:
            return jsonify({"done": True, "error": "no_collection", "message": "No public collection found for this user."})

    # Build the profile once and cache it with the items (a Lookup-written entry
    # has no profile yet, so compute it on first recommendation use).
    if not profile_text:
        profile_text = recommend_helper.build_taste_profile(items)
    lookup_cache.put(cache_key, {"items": items, "profile": profile_text})

    try:
        res = recommend_helper.run_recommendation_round(
            items, scraper, auth=auth, budget=budget,
            considered=considered, seen_ids=seen_ids, new_artists=new_artists,
            want_bio=(round_idx == 0),
            n_candidates=_REFRESH_CANDIDATES if manual else None,
            profile_text=profile_text)
    except recommend_helper.VertexConfigError as e:
        return jsonify({"done": True, "error": "vertex_config", "message": "Vertex AI is not configured: {0}".format(e)})
    except Exception:
        return jsonify({"done": True, "error": "failed", "message": "Something went wrong generating recommendations."})

    # Monthly cap reached: if nothing has been shown yet, surface the paused
    # notice; otherwise just stop and keep what's already on the page.
    if res["capped"]:
        return jsonify({
            "done": True, "capped": True,
            "error": "capped" if have == 0 else None,
            "message": "Recommendations are temporarily paused — the monthly budget cap was reached. They’ll be back next month." if have == 0 else None,
        })

    total = have + len(res["cards"])
    done = total >= _TARGET_RESULTS or round_idx + 1 >= _MAX_ROUNDS or res["exhausted"]

    return jsonify({
        "cards_html": render_template("_recommend_cards.html", cards=res["cards"]),
        "lines_html": render_template("_recommend_lines.html", cards=res["cards"]),
        "bio": res["bio"],
        "considered": res["considered"],
        "seen_ids": res["seen_ids"],
        "done": done,
        # Nothing found at all across the run — let the client show an empty state.
        "empty": done and total == 0,
    })
