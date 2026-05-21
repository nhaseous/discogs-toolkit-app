from flask import Blueprint, request, render_template, render_template_string, session, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import cloudscraper, time
import requests as _requests
from datetime import datetime
from helper import pricechecker, api as api_helper, firestore_db as _firestore_db
from web_common import is_price_checker_enabled, oauth_auth, get_pc_scraper

pricechecker_bp = Blueprint('pricechecker', __name__)


@pricechecker_bp.route("/pricechecker")
def pricecheckerpage():
    if not is_price_checker_enabled():
        return "Price Checker doesn't work when running on the cloud/web because webscraping gets blocked by Cloudflare. Contact curefortheitch if interested in a local solution."

    seller = request.args.get("seller", "")
    searched_at = ""
    show_platter = False
    inventory_count = 0
    pending_releases = []
    sort_active = request.args.get("sort", "") == "yes"
    error_output = ""

    if seller != "":
        # Only the inventory index is fetched server-side here (fast, a handful of
        # API calls). The marketplace scraping for each release is driven from the
        # browser via /scrape_batch so cards can stream in progressively.
        try:
            # Inventory is a REST API call (api.discogs.com) — use a plain
            # requests session, not cloudscraper. cloudscraper is only needed for
            # the marketplace HTML scrape, which runs later via /scrape_batch.
            scraper = api_helper.make_api_session()
            release_titles_ids = None
            for attempt in range(2):
                try:
                    release_titles_ids = pricechecker.get_inventory_ids(seller, scraper, auth=oauth_auth())
                    break
                except _requests.exceptions.RequestException:
                    if attempt == 1:
                        raise
                    time.sleep(1)
            inventory_count = len(release_titles_ids)
            pending_releases = [
                {"index": i, "title": r[0], "release_id": r[1], "thumbnail": r[2], "listing_ids": r[3]}
                for i, r in enumerate(release_titles_ids)
            ]
            show_platter = True
        except _requests.exceptions.RequestException:
            error_output = "Could not reach Discogs (network error). Please try again."
        except AttributeError:
            error_output = "No user found."

        searched_at = datetime.now().astimezone().strftime("%-I:%M %p %Z · %-d %b %y")

    return render_template('pricechecker.html',
        seller=seller,
        inventory_count=inventory_count,
        pending_releases=pending_releases,
        sort_active=sort_active,
        searched_at=searched_at,
        error_output=error_output,
        content_class='has-results' if seller else '',
        show_platter=show_platter,
        title='Price Checker'
    )


# Server-rendered Price Checker card, used by /scrape_batch so progressively
# streamed cards are byte-identical to the original synchronous render.
_PC_CARD_TEMPLATE = '{% from "macros.html" import pricechecker_card with context %}{{ pricechecker_card(entry, count) }}'


@pricechecker_bp.route("/scrape_batch", methods=["POST"])
def scrape_batch():
    if not is_price_checker_enabled():
        return jsonify({"error": "disabled"}), 403
    data = request.get_json() or {}
    seller = data.get("seller", "")
    releases = data.get("releases", [])
    if not seller or not releases:
        return jsonify({"error": "missing params"}), 400

    scraper = get_pc_scraper()

    # Scrape concurrently in worker threads, but render the card markup back on
    # the main thread — Flask's template context is thread-local and is not
    # available inside the executor workers.
    def scrape_one(r):
        idx = r.get("index", 0)
        release_id = str(r.get("release_id", ""))
        inventory_list = [None]
        sorted_inventory_list = [[] for _ in range(10)]
        try:
            pricechecker.get_listings(scraper, inventory_list, sorted_inventory_list, seller,
                                      r.get("title", ""), release_id, r.get("thumbnail", ""),
                                      r.get("listing_ids", []), 0)
        except pricechecker.CloudflareBlockedError:
            return {"index": idx, "release_id": release_id, "error": "cf_blocked"}
        except Exception:
            # Network error, timeout, parse failure — fail just this card so the
            # rest of the batch (and the page) keep loading.
            return {"index": idx, "release_id": release_id, "error": "scrape_failed"}
        entry = inventory_list[0]
        if entry is None:
            return {"index": idx, "release_id": release_id, "error": "scrape_failed"}
        return {"index": idx, "release_id": release_id, "entry": entry}

    scraped, cf_blocked = [], False
    with ThreadPoolExecutor(max_workers=5) as executor:
        for f in as_completed([executor.submit(scrape_one, r) for r in releases]):
            scraped.append(f.result())

    results = []
    for s in scraped:
        if s.get("error") == "cf_blocked":
            cf_blocked = True
            results.append({"index": s["index"], "release_id": s["release_id"], "error": "cf_blocked"})
            continue
        if s.get("error"):
            results.append({"index": s["index"], "release_id": s["release_id"], "error": s["error"]})
            continue
        entry = s["entry"]
        results.append({
            "index": s["index"],
            "release_id": s["release_id"],
            "place": entry.place,
            "badges": pricechecker._entry_badges(entry),
            "card_html": render_template_string(_PC_CARD_TEMPLATE, entry=entry, count=s["index"] + 1),
            "thumb": entry.imgUrl or "",
        })

    return jsonify({"results": results, "cf_blocked": cf_blocked})


@pricechecker_bp.route("/reprice", methods=["POST"])
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

    results = pricechecker.reprice_listings(data.get("listings", []), oauth_auth())
    return {"results": results}


@pricechecker_bp.route("/refresh_card", methods=["POST"])
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


@pricechecker_bp.route("/watchlist", methods=["GET"])
def get_watchlist():
    user = session.get('discogs_username', '')
    seller = request.args.get('seller', '')
    if not user or user.lower() != seller.lower():
        return {"watchlist": []}
    try:
        return {"watchlist": _firestore_db.get_watchlist(user)}
    except Exception as e:
        return {"watchlist": [], "error": str(e)}


@pricechecker_bp.route("/watchlist", methods=["POST"])
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
